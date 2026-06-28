"""
Hypothesis 2a – Dynamic Pipeline MAS
=====================================
Baseline:  fextract(row1) → fscoring(row1) → fextract(row2) → fscoring(row2) …
           (one agent always idles while the other runs)

This file: fextract(row1) starts
           → as soon as fextract(row1) finishes, fscoring(row1) AND fextract(row2) fire
             simultaneously, so the two API slots are always occupied.

The pattern is a two-stage pipeline:
  Stage A  fextract  ──►  queue  ──►  Stage B  fscoring
                            ▲
           next fextract fills in immediately when a slot opens

Implementation: ThreadPoolExecutor with max_workers=2.
  • One future is always an fextract call (for the next unprocessed row).
  • One future is always an fscoring call (for the row whose extraction just finished).
  • When fscoring finishes and no new fextract is pending, one thread goes idle —
    but that only happens on the very last row, which is unavoidable.

Rows are written to disk immediately as they complete — a crash mid-run
will not lose already-graded rows.  Use --start-row N to resume from row N.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import threading
import time
import urllib.error
import urllib.request
from collections import deque
from concurrent.futures import ThreadPoolExecutor, Future, as_completed
from pathlib import Path
from typing import Any
from datetime import datetime

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR    = Path(__file__).resolve().parent.parent
THIS_DIR    = Path(__file__).resolve().parent
INPUT_CSV   = BASE_DIR / "asap2_total_master.csv"
RUBRIC_FILE = BASE_DIR / "Criteria.txt"
OUTPUT_CSV  = THIS_DIR / "asap2MASgraded.csv"

DEFAULT_API_VERSION        = "2024-12-01-preview"
DEFAULT_TEMPERATURE        = 0.0
DEFAULT_MAX_TOKENS_EXTRACT = 5000
DEFAULT_MAX_TOKENS_SCORE   = 5000
MAX_ROW_RETRIES            = 3
BASE_RETRY_DELAY_SECONDS   = 2.0
MAX_RETRY_DELAY_SECONDS    = 16.0


# ---------------------------------------------------------------------------
# Environment helpers
# ---------------------------------------------------------------------------

def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key   = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


def get_env(name: str, default: str | None = None) -> str:
    value = os.getenv(name, default)
    if value is None or not value.strip():
        raise SystemExit(f"Missing required environment variable: {name}")
    return value.strip()


# ---------------------------------------------------------------------------
# Retryable error types
# ---------------------------------------------------------------------------

class AzureRetryableError(RuntimeError):
    def __init__(self, message: str, *, kind: str, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.kind        = kind
        self.retry_after = retry_after


class AzureThrottleError(AzureRetryableError):
    def __init__(self, message: str, *, retry_after: float | None = None) -> None:
        super().__init__(message, kind="throttle", retry_after=retry_after)


class AzureTransientError(AzureRetryableError):
    def __init__(self, message: str) -> None:
        super().__init__(message, kind="transient")


def parse_retry_after(header_value: str | None) -> float | None:
    if not header_value:
        return None
    try:
        return max(0.0, float(header_value))
    except ValueError:
        return None


def retry_delay(attempt: int, retry_after: float | None = None) -> float:
    if retry_after is not None and retry_after > 0:
        return min(retry_after, MAX_RETRY_DELAY_SECONDS)
    return min(BASE_RETRY_DELAY_SECONDS * (2 ** attempt), MAX_RETRY_DELAY_SECONDS)


# ---------------------------------------------------------------------------
# Azure OpenAI call
# ---------------------------------------------------------------------------

def call_azure_openai(
    messages:    list[dict[str, str]],
    endpoint:    str,
    api_key:     str,
    deployment:  str,
    api_version: str,
    max_tokens:  int,
) -> tuple[str | None, int, int]:
    """
    Returns (content, prompt_tokens, completion_tokens).
    Returns (None, 0, 0) on a content-filter hit.
    Raises AzureRetryableError on timeout / 429 / 5xx (caller retries).
    Raises RuntimeError on unrecoverable errors.
    """
    url = (
        f"{endpoint.rstrip('/')}/openai/deployments/{deployment}"
        f"/chat/completions?api-version={api_version}"
    )
    payload = {
        "messages":        messages,
        "temperature":     DEFAULT_TEMPERATURE,
        "max_tokens":      max_tokens,
        "response_format": {"type": "json_object"},
    }
    req = urllib.request.Request(
        url=url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "api-key": api_key},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            body = resp.read().decode("utf-8")
    except TimeoutError as exc:
        raise AzureTransientError(
            f"Azure OpenAI request timed out after 180 s: {exc}"
        ) from exc
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        if "content_filter" in error_body:
            print("  Content filter triggered. Skipping this row.")
            return None, 0, 0
        if exc.code == 429:
            raise AzureThrottleError(
                f"Azure OpenAI throttled: {exc.code} {exc.reason}",
                retry_after=parse_retry_after(exc.headers.get("Retry-After")),
            ) from exc
        if exc.code in {408, 500, 502, 503, 504}:
            raise AzureTransientError(
                f"Azure OpenAI transient error: {exc.code} {exc.reason}"
            ) from exc
        raise RuntimeError(
            f"Azure OpenAI request failed: {exc.code} {exc.reason}\n{error_body}"
        ) from exc

    response_json     = json.loads(body)
    usage             = response_json.get("usage", {})
    prompt_tokens     = usage.get("prompt_tokens", 0)
    completion_tokens = usage.get("completion_tokens", 0)

    choices = response_json.get("choices", [])
    if not choices:
        raise RuntimeError(f"Azure OpenAI returned no choices: {body}")
    content = choices[0].get("message", {}).get("content", "")
    if not content:
        raise RuntimeError(f"Azure OpenAI returned empty content: {body}")

    return content, prompt_tokens, completion_tokens


# ---------------------------------------------------------------------------
# Agent 1 – fextract
# ---------------------------------------------------------------------------

FEXTRACT_SYSTEM = "Follow the instructions."

FEXTRACT_OUTPUT_INSTRUCTIONS = (
    "Perform a rule-by-rule check of the student response against every rubric criterion. "
    "Return a single valid JSON object and nothing else. No markdown, no extra text. "
    "For EVERY rubric criterion include a key with: "
    '"requirement_met" (boolean), '
    '"evidence" (exact text span from the student response, empty string if none), '
    'and "count" (integer, only when the rubric requires counting). '
    "Use concise descriptive key names derived from each criterion "
    '(e.g. "defines_concept", "lists_two_advantages"). '
    'Also include a top-level "overall_notes" string for any ambiguities.'
)

FEXTRACT_USER_TEMPLATE = """\
Question: {question}

Rubric:
{rubric}

Student Response:
{student_answer}

Output Instructions: {output_instructions}
"""


def build_fextract_messages(
    question: str, student_answer: str, rubric: str, retry_note: str = ""
) -> list[dict[str, str]]:
    user_content = FEXTRACT_USER_TEMPLATE.format(
        question=question,
        rubric=rubric,
        student_answer=student_answer,
        output_instructions=FEXTRACT_OUTPUT_INSTRUCTIONS,
    )
    if retry_note:
        user_content += f"\n\nIMPORTANT: {retry_note}"
    return [
        {"role": "system", "content": FEXTRACT_SYSTEM},
        {"role": "user",   "content": user_content},
    ]


def run_fextract(
    question:       str,
    student_answer: str,
    rubric:         str,
    endpoint:       str,
    api_key:        str,
    deployment:     str,
    api_version:    str,
) -> tuple[dict[str, Any] | None, int, int, str | None]:
    """
    Returns (extracted_dict, prompt_tokens, completion_tokens, error_message).
    extracted_dict is None on content-filter hit or unrecoverable failure.
    error_message is set only on failure (None on success or content-filter skip).
    """
    retry_note: str              = ""
    last_error: Exception | None = None
    total_pt = total_ct = 0

    for attempt in range(MAX_ROW_RETRIES):
        messages = build_fextract_messages(question, student_answer, rubric, retry_note)
        try:
            raw, pt, ct = call_azure_openai(
                messages, endpoint, api_key, deployment, api_version,
                max_tokens=DEFAULT_MAX_TOKENS_EXTRACT,
            )
        except AzureRetryableError as exc:
            last_error = exc
            wait = retry_delay(attempt, exc.retry_after)
            print(f"  [fextract {exc.kind}] attempt {attempt + 1}/{MAX_ROW_RETRIES}, retrying in {wait:.1f}s...")
            if attempt < MAX_ROW_RETRIES - 1:
                time.sleep(wait)
            continue

        total_pt += pt
        total_ct += ct

        if raw is None:                          # content filter
            return None, total_pt, total_ct, None

        try:
            parsed = json.loads(raw)
            if not isinstance(parsed, dict):
                raise ValueError("fextract output must be a JSON object")
            return parsed, total_pt, total_ct, None
        except Exception as exc:
            last_error = exc
            retry_note = (
                "Your previous response was not valid JSON. "
                "Return only a valid JSON object with no markdown or extra text."
            )

    msg = f"fextract failed after {MAX_ROW_RETRIES} attempts: {last_error}"
    return None, total_pt, total_ct, msg


# ---------------------------------------------------------------------------
# Agent 2 – fscoring
# ---------------------------------------------------------------------------

FSCORING_SYSTEM = "Follow the instructions."

FSCORING_OUTPUT_INSTRUCTIONS = (
    "Use the boolean flags, evidence strings, and counts in the Extracted Evidence "
    "to determine the final score. "
    "If the Extracted Evidence contains inconsistencies, use the Student Response for verification. "
    "Resolve all ambiguities strictly in favour of the official rubric definitions. "
    "Return ONLY a valid JSON object with exactly two keys: "
    '"grade" (integer 1-6) and "reasoning" (one concise sentence). '
    "No markdown, no extra keys, no extra text."
)

FSCORING_USER_TEMPLATE = """\
Question: {question}

Official Rubric:
{rubric}

Student Response:
{student_answer}

Extracted Evidence:
{extracted_json}

Output Instructions: {output_instructions}
"""


def build_fscoring_messages(
    question:       str,
    student_answer: str,
    rubric:         str,
    extracted:      dict[str, Any],
    retry_note:     str = "",
) -> list[dict[str, str]]:
    user_content = FSCORING_USER_TEMPLATE.format(
        question=question,
        rubric=rubric,
        student_answer=student_answer,
        extracted_json=json.dumps(extracted, ensure_ascii=False, indent=2),
        output_instructions=FSCORING_OUTPUT_INSTRUCTIONS,
    )
    if retry_note:
        user_content += f"\n\nIMPORTANT: {retry_note}"
    return [
        {"role": "system", "content": FSCORING_SYSTEM},
        {"role": "user",   "content": user_content},
    ]


def parse_fscoring_output(raw: str) -> dict[str, Any]:
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError("fscoring output must be a JSON object")
    if "grade" not in parsed or "reasoning" not in parsed:
        raise ValueError("fscoring output must have 'grade' and 'reasoning'")
    grade = parsed["grade"]
    if not isinstance(grade, int) or not (1 <= grade <= 6):
        raise ValueError(f"grade must be an integer 1-6, got: {grade!r}")
    reasoning = parsed["reasoning"]
    if not isinstance(reasoning, str) or not reasoning.strip():
        raise ValueError("reasoning must be a non-empty string")
    return {"grade": grade, "reasoning": reasoning.strip()}


def run_fscoring(
    question:       str,
    student_answer: str,
    rubric:         str,
    extracted:      dict[str, Any],
    endpoint:       str,
    api_key:        str,
    deployment:     str,
    api_version:    str,
) -> tuple[dict[str, Any], int, int]:
    """
    Returns (scored_dict, prompt_tokens, completion_tokens).
    scored_dict always has 'grade' and 'reasoning'; grade == -1 signals failure.
    Never raises — errors are captured into the returned dict.
    """
    retry_note: str              = ""
    last_error: Exception | None = None
    total_pt = total_ct = 0

    for attempt in range(MAX_ROW_RETRIES):
        messages = build_fscoring_messages(
            question, student_answer, rubric, extracted, retry_note
        )
        try:
            raw, pt, ct = call_azure_openai(
                messages, endpoint, api_key, deployment, api_version,
                max_tokens=DEFAULT_MAX_TOKENS_SCORE,
            )
        except AzureRetryableError as exc:
            last_error = exc
            wait = retry_delay(attempt, exc.retry_after)
            print(f"  [fscoring {exc.kind}] attempt {attempt + 1}/{MAX_ROW_RETRIES}, retrying in {wait:.1f}s...")
            if attempt < MAX_ROW_RETRIES - 1:
                time.sleep(wait)
            continue

        total_pt += pt
        total_ct += ct

        if raw is None:                          # content filter
            return {"grade": -1, "reasoning": "Content filter triggered."}, total_pt, total_ct

        try:
            return parse_fscoring_output(raw), total_pt, total_ct
        except Exception as exc:
            last_error = exc
            retry_note = (
                "Your previous response was invalid. "
                "Return only valid JSON with exactly the keys 'grade' (int 1-6) "
                "and 'reasoning' (string)."
            )

    return (
        {"grade": -1, "reasoning": f"fscoring failed after {MAX_ROW_RETRIES} attempts: {last_error}"},
        total_pt, total_ct,
    )


# ---------------------------------------------------------------------------
# Pipeline core types
# ---------------------------------------------------------------------------

class ExtractResult:
    __slots__ = (
        "row_index", "row", "question", "student_answer",
        "extracted", "a1_pt", "a1_ct",
    )

    def __init__(
        self,
        row_index:      int,
        row:            dict,
        question:       str,
        student_answer: str,
        extracted:      dict[str, Any],
        a1_pt:          int,
        a1_ct:          int,
    ) -> None:
        self.row_index      = row_index
        self.row            = row
        self.question       = question
        self.student_answer = student_answer
        self.extracted      = extracted
        self.a1_pt          = a1_pt
        self.a1_ct          = a1_ct


def _make_result_row(
    original_row:  dict,
    grade:         int,
    reasoning:     str,
    extracted_str: str,
    a1_pt:         int,
    a1_ct:         int,
    a2_pt:         int,
    a2_ct:         int,
) -> dict:
    row = dict(original_row)
    row["AI_grade"]             = str(grade)
    row["AI_reasoning"]         = reasoning
    row["extracted_evidence"]   = extracted_str
    row["a1_prompt_tokens"]     = str(a1_pt)
    row["a1_completion_tokens"] = str(a1_ct)
    row["a2_prompt_tokens"]     = str(a2_pt)
    row["a2_completion_tokens"] = str(a2_ct)
    return row


# ---------------------------------------------------------------------------
# Dynamic pipeline
# ---------------------------------------------------------------------------

def run_pipeline(
    rows:        list[dict],
    rubric:      str,
    endpoint:    str,
    api_key:     str,
    deployment:  str,
    api_version: str,
    row_offset:  int = 0,
    writer:      "csv.DictWriter | None" = None,
    write_lock:  "threading.Lock | None" = None,
) -> list[dict]:
    """
    Two-worker pipeline so fextract and fscoring always run concurrently.
    Each completed row is written to `writer` immediately under `write_lock`.
    """
    n = len(rows)
    results: list[dict | None]         = [None] * n
    ready_scores: deque[ExtractResult] = deque()

    api = dict(
        endpoint=endpoint, api_key=api_key,
        deployment=deployment, api_version=api_version,
    )

    future_tags: dict[Future, tuple] = {}
    next_row_to_extract = 0

    def _flush(row: dict) -> None:
        """Write a completed row to disk immediately."""
        if writer is not None:
            lock = write_lock or threading.Lock()
            with lock:
                writer.writerow(row)

    def submit_extract(idx: int, executor: ThreadPoolExecutor) -> Future:
        r              = rows[idx]
        question       = (r.get("assignment") or "").strip()
        student_answer = (r.get("full_text")  or "").strip()
        f = executor.submit(run_fextract, question, student_answer, rubric, **api)
        future_tags[f] = ("extract", idx, r, question, student_answer)
        print(f"  → fextract submitted for row {row_offset + idx + 1}")
        return f

    def submit_score(er: ExtractResult, executor: ThreadPoolExecutor) -> Future:
        f = executor.submit(
            run_fscoring,
            er.question, er.student_answer, rubric, er.extracted, **api,
        )
        future_tags[f] = ("score", er)
        print(f"  → fscoring  submitted for row {row_offset + er.row_index + 1}")
        return f

    def refill(executor: ThreadPoolExecutor, active: set[Future]) -> None:
        nonlocal next_row_to_extract
        while len(active) < 2:
            if ready_scores:
                active.add(submit_score(ready_scores.popleft(), executor))
            elif next_row_to_extract < n:
                active.add(submit_extract(next_row_to_extract, executor))
                next_row_to_extract += 1
            else:
                break

    with ThreadPoolExecutor(max_workers=2) as executor:
        active: set[Future] = set()
        refill(executor, active)

        while active or ready_scores or next_row_to_extract < n:
            if not active:
                refill(executor, active)
                if not active:
                    break

            done_future = next(as_completed(active))
            active.discard(done_future)
            tag   = future_tags.pop(done_future)
            stage = tag[0]

            # ── Stage A: fextract completed ───────────────────────────────
            if stage == "extract":
                _, idx, row, question, student_answer = tag
                extracted, a1_pt, a1_ct, err = done_future.result()
                print(f"  ✓ fextract done  row {row_offset + idx + 1}  tokens in={a1_pt} out={a1_ct}")

                if extracted is None:
                    # content-filter hit OR unrecoverable extraction error
                    reason = err or "Content filter triggered (extraction)."
                    result_row = _make_result_row(row, -1, reason, "{}", a1_pt, a1_ct, 0, 0)
                    results[idx] = result_row
                    _flush(result_row)
                    print(f"  ✗ row {row_offset + idx + 1} SKIPPED – {reason}")
                else:
                    ready_scores.append(ExtractResult(
                        row_index=idx, row=row,
                        question=question, student_answer=student_answer,
                        extracted=extracted, a1_pt=a1_pt, a1_ct=a1_ct,
                    ))

            # ── Stage B: fscoring completed ───────────────────────────────
            elif stage == "score":
                _, er = tag
                scored, a2_pt, a2_ct = done_future.result()
                status = "SKIPPED (content filter)" if scored["grade"] == -1 else f"grade={scored['grade']}"
                print(
                    f"  ✓ fscoring done  row {row_offset + er.row_index + 1}  "
                    f"{status}  tokens in={a2_pt} out={a2_ct}"
                )
                result_row = _make_result_row(
                    er.row,
                    scored["grade"], scored["reasoning"],
                    json.dumps(er.extracted, ensure_ascii=False),
                    er.a1_pt, er.a1_ct, a2_pt, a2_ct,
                )
                results[er.row_index] = result_row
                _flush(result_row)

            refill(executor, active)

    if ready_scores:
        raise RuntimeError("Scheduler ended with unsubmitted scoring work remaining")

    return [r for r in results if r is not None]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--start-row", type=int, default=1,
        help="1-based row number in the input CSV to start from (rows before this are skipped).",
    )
    args       = parser.parse_args()
    start_row  = max(1, args.start_row)

    load_env_file(BASE_DIR / ".env")

    if not INPUT_CSV.exists():
        raise SystemExit(f"Input CSV not found: {INPUT_CSV}")
    if not RUBRIC_FILE.exists():
        raise SystemExit(f"Rubric file not found: {RUBRIC_FILE}")

    endpoint    = get_env("AZURE_OPENAI_ENDPOINT")
    api_key     = get_env("AZURE_OPENAI_API_KEY")
    deployment  = get_env("AZURE_OPENAI_DEPLOYMENT")
    api_version = get_env("AZURE_OPENAI_API_VERSION", DEFAULT_API_VERSION).strip()

    rubric = load_text(RUBRIC_FILE)

    run_start_time = datetime.now()
    start_log = OUTPUT_CSV.with_suffix(".starttime")
    start_log.write_text(run_start_time.strftime('%Y-%m-%d %H:%M:%S'), encoding="utf-8")

    # ── Read all rows ───────────────────────────────────────────────────────
    with INPUT_CSV.open("r", encoding="utf-8-sig", newline="") as infile:
        reader        = csv.DictReader(infile, delimiter=",")
        fieldnames_in = list(reader.fieldnames or [])
        all_rows      = list(reader)

    if not all_rows:
        raise SystemExit("Input CSV is empty.")

    for i, r in enumerate(all_rows, start=1):
        if not (r.get("assignment") or "").strip():
            raise SystemExit(f"Missing assignment in row {i}")
        if not (r.get("full_text") or "").strip():
            raise SystemExit(f"Missing full_text in row {i}")

    # ── Apply --start-row ───────────────────────────────────────────────────
    rows_to_skip = start_row - 1
    if rows_to_skip >= len(all_rows):
        raise SystemExit(
            f"--start-row {start_row} exceeds total row count ({len(all_rows)}). Nothing to do."
        )
    if rows_to_skip > 0:
        print(f"Skipping first {rows_to_skip} row(s) (--start-row={start_row}).")
        all_rows = all_rows[rows_to_skip:]

    # ── Output fieldnames ───────────────────────────────────────────────────
    fieldnames = list(fieldnames_in)
    for extra in (
        "AI_grade", "AI_reasoning", "extracted_evidence",
        "a1_prompt_tokens", "a1_completion_tokens",
        "a2_prompt_tokens", "a2_completion_tokens",
    ):
        if extra not in fieldnames:
            fieldnames.append(extra)

    print(f"Pipeline MAS – {len(all_rows)} rows – max_workers=2")
    print("=" * 60)

    # ── Open output file BEFORE pipeline starts ─────────────────────────────
    # Rows are flushed to disk as they complete; a crash won't lose prior work.
    # Append if resuming (--start-row > 1 and file already exists), else overwrite.
    write_mode = "a" if rows_to_skip > 0 and OUTPUT_CSV.exists() else "w"
    out_fh = OUTPUT_CSV.open(write_mode, encoding="utf-8", newline="")
    out_writer = csv.DictWriter(
        out_fh, fieldnames=fieldnames, delimiter=",",
        quoting=csv.QUOTE_MINIMAL, extrasaction="ignore",
    )
    if write_mode == "w":
        out_writer.writeheader()
    out_lock = threading.Lock()

    graded_rows: list[dict] = []
    try:
        graded_rows = run_pipeline(
            all_rows, rubric, endpoint, api_key, deployment, api_version,
            row_offset=rows_to_skip,
            writer=out_writer,
            write_lock=out_lock,
        )
    finally:
        # Always flush whatever was written, even on crash
        out_fh.flush()

    run_end_time = datetime.now()
    run_duration = run_end_time - run_start_time

    # ── Token totals ────────────────────────────────────────────────────────
    total_a1_pt = sum(int(r.get("a1_prompt_tokens", 0) or 0) for r in graded_rows)
    total_a1_ct = sum(int(r.get("a1_completion_tokens", 0) or 0) for r in graded_rows)
    total_a2_pt = sum(int(r.get("a2_prompt_tokens", 0) or 0) for r in graded_rows)
    total_a2_ct = sum(int(r.get("a2_completion_tokens", 0) or 0) for r in graded_rows)

    total_prompt     = total_a1_pt + total_a2_pt
    total_completion = total_a1_ct + total_a2_ct
    total_tokens     = total_prompt + total_completion

    # ── Append summary row then close ───────────────────────────────────────
    summary: dict[str, str] = {f: "" for f in fieldnames}
    summary["assignment"]           = "=== RUN SUMMARY ==="
    summary["AI_reasoning"]         = (
        f"start={run_start_time.strftime('%Y-%m-%d %H:%M:%S')} | "
        f"end={run_end_time.strftime('%Y-%m-%d %H:%M:%S')} | "
        f"duration={str(run_duration).split('.')[0]}"
    )
    summary["a1_prompt_tokens"]     = str(total_a1_pt)
    summary["a1_completion_tokens"] = str(total_a1_ct)
    summary["a2_prompt_tokens"]     = str(total_a2_pt)
    summary["a2_completion_tokens"] = str(total_a2_ct)
    summary["extracted_evidence"]   = (
        f"total_prompt={total_prompt} | "
        f"total_completion={total_completion} | "
        f"total_tokens={total_tokens}"
    )
    out_writer.writerow(summary)
    out_fh.close()

    # ── Console summary ─────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("PIPELINE MAS RUN SUMMARY  (Hypothesis 2a)")
    print("=" * 60)
    print(f"  Start time              : {run_start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  End time                : {run_end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Duration                : {str(run_duration).split('.')[0]}")
    print(f"  Rows processed          : {len(graded_rows)}")
    print(f"  Agent 1 prompt tokens   : {total_a1_pt:,}")
    print(f"  Agent 1 completion tok. : {total_a1_ct:,}")
    print(f"  Agent 2 prompt tokens   : {total_a2_pt:,}")
    print(f"  Agent 2 completion tok. : {total_a2_ct:,}")
    print(f"  ── Total prompt tokens  : {total_prompt:,}")
    print(f"  ── Total compl. tokens  : {total_completion:,}")
    print(f"  ── GRAND TOTAL tokens   : {total_tokens:,}")
    print("=" * 60)
    print(f"Output written to {OUTPUT_CSV}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())