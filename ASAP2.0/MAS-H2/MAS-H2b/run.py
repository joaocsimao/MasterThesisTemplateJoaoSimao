"""
Hypothesis 2b – Adaptive Parallel Multi-Agent Grader
=====================================================
Identical fextract → fscoring pipeline as the sequential baseline,
but rows are processed concurrently via ThreadPoolExecutor with an
adaptive controller that steps concurrency down on Azure errors and
carefully increases it again after clean runs.

Worker count is resolved at runtime (highest to lowest priority):
  1. MAX_WORKERS environment variable (explicit integer)


Output row order mirrors input order because the scheduler keeps a
stable result slot for each input row.

Extra output columns vs baseline
---------------------------------
  wall_seconds   – elapsed wall-clock time for this row (float, seconds)
  worker_id      – which ThreadPoolExecutor worker handled the row

Summary row additionally records:
  total_wall_seconds – end-to-end wall time of the whole run
  speedup_factor     – sequential_sum_wall / total_wall_seconds  (ideal = n_workers)

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
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
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
ADAPTIVE_GROWTH_STREAK     = 4
BASE_RETRY_DELAY_SECONDS   = 1.5
MAX_RETRY_DELAY_SECONDS    = 8.0


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
# Resolve worker count
# ---------------------------------------------------------------------------

def resolve_worker_count() -> int:
    """
    Returns the number of parallel workers to use.

    This grader is I/O-bound on Azure OpenAI API calls, not CPU-bound.
    Too many parallel workers will trigger Azure 429 throttle errors.

    Resolution order (first wins):
      1. MAX_WORKERS env var   – explicit user override
      2. 4                     – conservative default safe for most Azure deployments
    """
    raw = os.getenv("MAX_WORKERS", "").strip()
    if raw.isdigit() and int(raw) > 0:
        return int(raw)
    return 4


def resolve_growth_threshold() -> int:
    raw = os.getenv("ADAPTIVE_GROWTH_STREAK", "").strip()
    if raw.isdigit() and int(raw) > 0:
        return int(raw)
    return ADAPTIVE_GROWTH_STREAK


def retry_delay_seconds(attempt: int, retry_after: float | None = None) -> float:
    if retry_after is not None and retry_after > 0:
        return min(retry_after, MAX_RETRY_DELAY_SECONDS)
    delay = BASE_RETRY_DELAY_SECONDS * (2 ** attempt)
    return min(delay, MAX_RETRY_DELAY_SECONDS)


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
            f"Azure OpenAI request timed out after 180 seconds: {exc}"
        ) from exc
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        if "content_filter" in error_body:
            print("  Content filter triggered. Skipping this row.")
            return None, 0, 0
        if exc.code == 429:
            raise AzureThrottleError(
                f"Azure OpenAI request throttled: {exc.code} {exc.reason}\n{error_body}",
                retry_after=parse_retry_after(exc.headers.get("Retry-After")),
            ) from exc
        if exc.code in {408, 500, 502, 503, 504}:
            raise AzureTransientError(
                f"Azure OpenAI request failed transiently: {exc.code} {exc.reason}\n{error_body}"
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
) -> tuple[dict[str, Any] | None, int, int, int, str | None]:
    """
    Returns (extracted_dict, prompt_tokens, completion_tokens, retryable_events, error_msg).
    extracted_dict is None on content-filter hit or unrecoverable failure.
    error_msg is set only on failure (None on success or content-filter skip).
    Never raises.
    """
    retry_note: str              = ""
    last_error: Exception | None = None
    total_pt = total_ct = 0
    retryable_events = 0

    for attempt in range(MAX_ROW_RETRIES):
        messages = build_fextract_messages(question, student_answer, rubric, retry_note)
        try:
            raw, pt, ct = call_azure_openai(
                messages, endpoint, api_key, deployment, api_version,
                max_tokens=DEFAULT_MAX_TOKENS_EXTRACT,
            )
        except AzureRetryableError as exc:
            retryable_events += 1
            last_error = exc
            if attempt >= MAX_ROW_RETRIES - 1:
                break
            wait = retry_delay_seconds(attempt, exc.retry_after)
            print(f"  [fextract {exc.kind}] attempt {attempt + 1}/{MAX_ROW_RETRIES}, retrying in {wait:.1f}s...")
            time.sleep(wait)
            retry_note = (
                f"The previous attempt failed with a transient Azure {exc.kind} error. "
                "Return only a valid JSON object with no markdown or extra text."
            )
            continue

        total_pt += pt
        total_ct += ct

        if raw is None:                          # content filter
            return None, total_pt, total_ct, retryable_events, None

        try:
            parsed = json.loads(raw)
            if not isinstance(parsed, dict):
                raise ValueError("fextract output must be a JSON object")
            return parsed, total_pt, total_ct, retryable_events, None
        except Exception as exc:
            last_error = exc
            retry_note = (
                "Your previous response was not valid JSON. "
                "Return only a valid JSON object with no markdown or extra text."
            )

    msg = f"fextract failed after {MAX_ROW_RETRIES} attempts: {last_error}"
    return None, total_pt, total_ct, retryable_events, msg


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
) -> tuple[dict[str, Any], int, int, int, str | None]:
    """
    Returns (scored_dict, prompt_tokens, completion_tokens, retryable_events, error_msg).
    scored_dict always has 'grade' and 'reasoning'; grade == -1 signals failure.
    Never raises — errors are captured into the returned dict.
    """
    retry_note: str              = ""
    last_error: Exception | None = None
    total_pt = total_ct = 0
    retryable_events = 0

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
            retryable_events += 1
            last_error = exc
            if attempt >= MAX_ROW_RETRIES - 1:
                break
            wait = retry_delay_seconds(attempt, exc.retry_after)
            print(f"  [fscoring {exc.kind}] attempt {attempt + 1}/{MAX_ROW_RETRIES}, retrying in {wait:.1f}s...")
            time.sleep(wait)
            retry_note = (
                f"The previous attempt failed with a transient Azure {exc.kind} error. "
                "Return only valid JSON with exactly the keys 'grade' and 'reasoning'."
            )
            continue

        total_pt += pt
        total_ct += ct

        if raw is None:                          # content filter
            return {"grade": -1, "reasoning": "Content filter triggered."}, total_pt, total_ct, retryable_events, None

        try:
            return parse_fscoring_output(raw), total_pt, total_ct, retryable_events, None
        except Exception as exc:
            last_error = exc
            retry_note = (
                "Your previous response was invalid. "
                "Return only valid JSON with exactly the keys 'grade' (int 1-6) "
                "and 'reasoning' (string)."
            )

    msg = f"fscoring failed after {MAX_ROW_RETRIES} attempts: {last_error}"
    return {"grade": -1, "reasoning": msg}, total_pt, total_ct, retryable_events, msg


# ---------------------------------------------------------------------------
# Pipeline: one row  (+ timing + worker_id)
# ---------------------------------------------------------------------------

def grade_row(
    row_index:   int,
    question:    str,
    answer:      str,
    rubric:      str,
    endpoint:    str,
    api_key:     str,
    deployment:  str,
    api_version: str,
    worker_id:   int,
) -> dict[str, Any]:
    """
    Runs fextract → fscoring for a single row.
    Returns a flat result dict ready to merge into the CSV row.
    Never raises.
    """
    t0 = time.perf_counter()

    # --- Agent 1: fextract ---
    extracted, a1_pt, a1_ct, a1_retryable, a1_error = run_fextract(
        question, answer, rubric, endpoint, api_key, deployment, api_version
    )
    if extracted is None:
        wall   = time.perf_counter() - t0
        status = "error" if a1_error else "skip"
        return {
            "grade":                -1,
            "reasoning":            a1_error or "Content filter triggered (extraction).",
            "extracted_evidence":   "{}",
            "a1_prompt_tokens":     a1_pt,
            "a1_completion_tokens": a1_ct,
            "a2_prompt_tokens":     0,
            "a2_completion_tokens": 0,
            "wall_seconds":         round(wall, 3),
            "worker_id":            worker_id,
            "retryable_events":     a1_retryable,
            "status":               status,
        }

    # --- Agent 2: fscoring ---
    scored, a2_pt, a2_ct, a2_retryable, a2_error = run_fscoring(
        question, answer, rubric, extracted,
        endpoint, api_key, deployment, api_version,
    )

    wall = time.perf_counter() - t0
    if a2_error:
        status = "error"
    elif scored["grade"] == -1 and scored["reasoning"] == "Content filter triggered.":
        status = "skip"
    elif scored["grade"] >= 0:
        status = "ok"
    else:
        status = "error"

    return {
        "grade":                scored["grade"],
        "reasoning":            scored["reasoning"],
        "extracted_evidence":   json.dumps(extracted, ensure_ascii=False),
        "a1_prompt_tokens":     a1_pt,
        "a1_completion_tokens": a1_ct,
        "a2_prompt_tokens":     a2_pt,
        "a2_completion_tokens": a2_ct,
        "wall_seconds":         round(wall, 3),
        "worker_id":            worker_id,
        "retryable_events":     a1_retryable + a2_retryable,
        "status":               status,
    }


# ---------------------------------------------------------------------------
# Thread wrapper – captures worker identity
# ---------------------------------------------------------------------------

_worker_local        = threading.local()
_worker_counter      = 0
_worker_counter_lock = threading.Lock()


def _assign_worker_id() -> int:
    """Returns a stable integer ID for the current thread."""
    if not hasattr(_worker_local, "id"):
        global _worker_counter
        with _worker_counter_lock:
            _worker_counter += 1
            _worker_local.id = _worker_counter
    return _worker_local.id


def _grade_row_wrapper(
    row_index:   int,
    row:         dict[str, str],
    rubric:      str,
    endpoint:    str,
    api_key:     str,
    deployment:  str,
    api_version: str,
) -> tuple[int, dict[str, str], dict[str, Any]]:
    """
    Thin wrapper executed inside the thread pool.
    Returns (row_index, original_row, result_dict).
    Never raises — grade_row captures all errors internally.
    """
    worker_id = _assign_worker_id()
    question  = (row.get("assignment") or "").strip()
    answer    = (row.get("full_text")  or "").strip()
    result    = grade_row(
        row_index, question, answer, rubric,
        endpoint, api_key, deployment, api_version,
        worker_id,
    )
    return row_index, row, result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--start-row", type=int, default=1,
        help="1-based row number in the input CSV to start from (rows before this are skipped).",
    )
    args      = parser.parse_args()
    start_row = max(1, args.start_row)

    load_env_file(BASE_DIR / ".env")

    if not INPUT_CSV.exists():
        raise SystemExit(f"Input CSV not found: {INPUT_CSV}")
    if not RUBRIC_FILE.exists():
        raise SystemExit(f"Rubric file not found: {RUBRIC_FILE}")

    endpoint    = get_env("AZURE_OPENAI_ENDPOINT")
    api_key     = get_env("AZURE_OPENAI_API_KEY")
    deployment  = get_env("AZURE_OPENAI_DEPLOYMENT")
    api_version = get_env("AZURE_OPENAI_API_VERSION", DEFAULT_API_VERSION).strip()

    rubric    = load_text(RUBRIC_FILE)
    n_workers = resolve_worker_count()

    run_start_time = datetime.now()
    start_log = OUTPUT_CSV.with_suffix(".starttime")
    start_log.write_text(run_start_time.strftime('%Y-%m-%d %H:%M:%S'), encoding="utf-8")

    print(f"Parallel MAS grader | workers = {n_workers}")
    print(f"Input  : {INPUT_CSV}")
    print(f"Output : {OUTPUT_CSV}")
    print("-" * 60)

    # ── Read all rows up front ──────────────────────────────────────────────
    with INPUT_CSV.open("r", encoding="utf-8-sig", newline="") as infile:
        reader        = csv.DictReader(infile, delimiter=",")
        fieldnames_in = list(reader.fieldnames or [])
        all_rows: list[dict[str, str]] = list(reader)

    if not all_rows:
        raise SystemExit("Input CSV is empty.")

    # Validate mandatory columns
    for i, row in enumerate(all_rows, start=1):
        if not (row.get("assignment") or "").strip():
            raise SystemExit(f"Missing assignment in row {i}")
        if not (row.get("full_text") or "").strip():
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

    n_rows = len(all_rows)

    # ── Build output fieldnames ─────────────────────────────────────────────
    extra_cols = [
        "AI_grade", "AI_reasoning", "extracted_evidence",
        "a1_prompt_tokens", "a1_completion_tokens",
        "a2_prompt_tokens", "a2_completion_tokens",
        "wall_seconds", "worker_id",
        "total_wall_seconds", "speedup_factor",
        "adaptive_start_workers", "adaptive_peak_workers",
        "adaptive_min_workers", "adaptive_retryable_events",
        "adaptive_error_rows",
    ]
    fieldnames_out = list(fieldnames_in)
    for col in extra_cols:
        if col not in fieldnames_out:
            fieldnames_out.append(col)

    # ── Open output file BEFORE execution starts ────────────────────────────
    # Rows are flushed to disk as they complete; a crash won't lose prior work.
    # Append if resuming (--start-row > 1 and file already exists), else overwrite.
    write_mode = "a" if rows_to_skip > 0 and OUTPUT_CSV.exists() else "w"
    out_fh = OUTPUT_CSV.open(write_mode, encoding="utf-8", newline="")
    out_writer = csv.DictWriter(
        out_fh, fieldnames=fieldnames_out, delimiter=",",
        quoting=csv.QUOTE_MINIMAL, extrasaction="ignore",
    )
    if write_mode == "w":
        out_writer.writeheader()
    out_lock = threading.Lock()

    # Accumulators
    total_a1_pt = total_a1_ct = 0
    total_a2_pt = total_a2_ct = 0
    total_wall               = 0.0
    completed                = 0
    adaptive_retryable_events = 0
    adaptive_error_rows       = 0

    wall_start           = time.perf_counter()
    target_workers       = n_workers
    peak_target_workers  = target_workers
    min_target_workers   = target_workers
    growth_threshold     = resolve_growth_threshold()
    clean_success_streak = 0

    pending_rows:   deque[tuple[int, dict[str, str]]] = deque(enumerate(all_rows))
    active_futures: dict[Any, tuple[int, dict[str, str]]] = {}

    try:
        # ── Parallel execution ──────────────────────────────────────────────
        with ThreadPoolExecutor(max_workers=500) as executor:
            while pending_rows or active_futures:
                while pending_rows and len(active_futures) < target_workers:
                    idx, row = pending_rows.popleft()
                    future = executor.submit(
                        _grade_row_wrapper,
                        rows_to_skip + idx + 1,   # 1-based original CSV row number
                        row,
                        rubric,
                        endpoint, api_key, deployment, api_version,
                    )
                    active_futures[future] = (idx, row)

                if not active_futures:
                    break

                done_futures, _ = wait(set(active_futures.keys()), return_when=FIRST_COMPLETED)

                for future in done_futures:
                    idx, orig_row = active_futures.pop(future)
                    row_index, _, result = future.result()   # never raises (grade_row is safe)
                    array_idx = idx                          # 0-based index into all_rows slice

                    out_row = dict(orig_row)
                    out_row["AI_grade"]             = str(result["grade"])
                    out_row["AI_reasoning"]         = result["reasoning"]
                    out_row["extracted_evidence"]   = result["extracted_evidence"]
                    out_row["a1_prompt_tokens"]     = str(result["a1_prompt_tokens"])
                    out_row["a1_completion_tokens"] = str(result["a1_completion_tokens"])
                    out_row["a2_prompt_tokens"]     = str(result["a2_prompt_tokens"])
                    out_row["a2_completion_tokens"] = str(result["a2_completion_tokens"])
                    out_row["wall_seconds"]         = str(result["wall_seconds"])
                    out_row["worker_id"]            = str(result["worker_id"])

                    # Write to disk immediately
                    with out_lock:
                        out_writer.writerow(out_row)
                        out_fh.flush()

                    total_a1_pt += result["a1_prompt_tokens"]
                    total_a1_ct += result["a1_completion_tokens"]
                    total_a2_pt += result["a2_prompt_tokens"]
                    total_a2_ct += result["a2_completion_tokens"]
                    total_wall  += result["wall_seconds"]
                    completed   += 1

                    row_retryable_events = int(result.get("retryable_events", 0))
                    adaptive_retryable_events += row_retryable_events
                    if result.get("status") == "error":
                        adaptive_error_rows += 1

                    # Adaptive concurrency controller
                    if row_retryable_events > 0:
                        clean_success_streak = 0
                        target_workers = max(150, target_workers - 1)
                    else:
                        clean_success_streak += 1
                        if clean_success_streak >= growth_threshold and target_workers < n_workers:
                            target_workers += 20
                            clean_success_streak = 0

                    peak_target_workers = max(peak_target_workers, target_workers)
                    min_target_workers  = min(min_target_workers,  target_workers)

                    if result.get("status") == "error":
                        status_str = "ERROR (retryable failure)"
                    elif result["grade"] == -1 and "Content filter" in result["reasoning"]:
                        status_str = "SKIPPED (content filter)"
                    else:
                        status_str = f"grade={result['grade']}"

                    print(
                        f"[{completed:>4}/{n_rows}] row={row_index:>4} "
                        f"worker={result['worker_id']} | {status_str} | "
                        f"target={target_workers} | wall={result['wall_seconds']:.1f}s | "
                        f"tokens A1 in={result['a1_prompt_tokens']} out={result['a1_completion_tokens']}  "
                        f"A2 in={result['a2_prompt_tokens']} out={result['a2_completion_tokens']}"
                    )

    finally:
        out_fh.flush()

    total_wall_clock = time.perf_counter() - wall_start
    run_end_time     = datetime.now()
    run_duration     = run_end_time - run_start_time
    speedup          = (total_wall / total_wall_clock) if total_wall_clock > 0 else 0.0

    # ── Append summary row then close ───────────────────────────────────────
    total_prompt     = total_a1_pt + total_a2_pt
    total_completion = total_a1_ct + total_a2_ct
    total_tokens     = total_prompt + total_completion

    summary: dict[str, str] = {f: "" for f in fieldnames_out}
    summary["assignment"]           = "=== RUN SUMMARY ==="
    summary["AI_reasoning"]         = (
        f"start={run_start_time.strftime('%Y-%m-%d %H:%M:%S')} | "
        f"end={run_end_time.strftime('%Y-%m-%d %H:%M:%S')} | "
        f"duration={str(run_duration).split('.')[0]} | "
        f"workers={n_workers}"
    )
    summary["a1_prompt_tokens"]          = str(total_a1_pt)
    summary["a1_completion_tokens"]      = str(total_a1_ct)
    summary["a2_prompt_tokens"]          = str(total_a2_pt)
    summary["a2_completion_tokens"]      = str(total_a2_ct)
    summary["extracted_evidence"]        = (
        f"total_prompt={total_prompt} | "
        f"total_completion={total_completion} | "
        f"total_tokens={total_tokens}"
    )
    summary["wall_seconds"]              = f"{total_wall_clock:.3f}"
    summary["total_wall_seconds"]        = f"{total_wall_clock:.3f}"
    summary["speedup_factor"]            = f"{speedup:.2f}"
    summary["adaptive_start_workers"]    = str(n_workers)
    summary["adaptive_peak_workers"]     = str(peak_target_workers)
    summary["adaptive_min_workers"]      = str(min_target_workers)
    summary["adaptive_retryable_events"] = str(adaptive_retryable_events)
    summary["adaptive_error_rows"]       = str(adaptive_error_rows)
    out_writer.writerow(summary)
    out_fh.close()

    # ── Console summary ─────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("PARALLEL AUTOSCORE RUN SUMMARY")
    print("=" * 60)
    print(f"  Workers used            : {n_workers}")
    print(f"  Adaptive peak workers   : {peak_target_workers}")
    print(f"  Adaptive min workers    : {min_target_workers}")
    print(f"  Start time              : {run_start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  End time                : {run_end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Wall-clock duration     : {total_wall_clock:.1f}s")
    print(f"  Sum of per-row walls    : {total_wall:.1f}s  (≈ sequential time)")
    print(f"  Speedup factor          : {speedup:.2f}x")
    print(f"  Retryable Azure events  : {adaptive_retryable_events}")
    print(f"  Error rows              : {adaptive_error_rows}")
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