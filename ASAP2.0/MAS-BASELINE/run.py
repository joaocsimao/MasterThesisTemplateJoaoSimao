from __future__ import annotations

import argparse
import csv
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from datetime import datetime


BASE_DIR = Path(__file__).resolve().parent.parent
THIS_DIR = Path(__file__).resolve().parent
INPUT_CSV = BASE_DIR / "asap2_total_master.csv"
RUBRIC_FILE = BASE_DIR / "Criteria.txt"
OUTPUT_CSV = THIS_DIR / "asap2MASgraded.csv"

DEFAULT_API_VERSION = "2024-12-01-preview"
DEFAULT_TEMPERATURE = 0.0
DEFAULT_MAX_TOKENS_EXTRACT = 5000
DEFAULT_MAX_TOKENS_SCORE = 5000


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
        key = key.strip()
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
# Azure OpenAI call (shared)
# ---------------------------------------------------------------------------

def call_azure_openai(
    messages: list[dict[str, str]],
    endpoint: str,
    api_key: str,
    deployment: str,
    api_version: str,
    max_tokens: int,
    max_retries: int = 3,
) -> tuple[str | None, int, int]:
    """
    Returns (content, prompt_tokens, completion_tokens).
    Returns (None, 0, 0) on a content-filter hit.
    Raises RuntimeError immediately on timeout.
    Retries with exponential backoff on 429 / 5xx.
    """
    url = (
        f"{endpoint.rstrip('/')}/openai/deployments/{deployment}"
        f"/chat/completions?api-version={api_version}"
    )
    payload = {
        "messages": messages,
        "temperature": DEFAULT_TEMPERATURE,
        "max_tokens": max_tokens,
        "response_format": {"type": "json_object"},
    }
    req = urllib.request.Request(
        url=url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "api-key": api_key},
        method="POST",
    )

    last_error: Exception | None = None
    for attempt in range(max_retries):
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                body = resp.read().decode("utf-8")
        except TimeoutError as exc:
            raise RuntimeError(
                f"Azure OpenAI request timed out after 180 seconds (attempt {attempt + 1})"
            ) from exc
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            if "content_filter" in error_body:
                print("  Content filter triggered. Skipping this row.")
                return None, 0, 0
            if exc.code == 429 or exc.code >= 500:
                last_error = exc
                wait = 2 ** attempt
                print(f"  [HTTP {exc.code}] attempt {attempt + 1}/{max_retries}, retrying in {wait}s...")
                time.sleep(wait)
                continue
            raise RuntimeError(
                f"Azure OpenAI request failed: {exc.code} {exc.reason}\n{error_body}"
            ) from exc

        response_json = json.loads(body)
        usage = response_json.get("usage", {})
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)

        choices = response_json.get("choices", [])
        if not choices:
            raise RuntimeError(f"Azure OpenAI returned no choices: {body}")

        content = choices[0].get("message", {}).get("content", "")
        if not content:
            raise RuntimeError(f"Azure OpenAI returned empty content: {body}")

        return content, prompt_tokens, completion_tokens

    raise RuntimeError(f"Azure OpenAI request failed after {max_retries} retries: {last_error}")


# ---------------------------------------------------------------------------
# Agent 1 – Scoring Rubric Component Extraction  (fextract)
# ---------------------------------------------------------------------------

FEXTRACT_SYSTEM = "Follow the instructions."

FEXTRACT_OUTPUT_INSTRUCTIONS = (
    "Perform a rule-by-rule check of the student response against every rubric criterion. "
    "Return a single valid JSON object and nothing else. No markdown, no extra text. "
    "For EVERY rubric criterion include a key with: "
    "\"requirement_met\" (boolean), "
    "\"evidence\" (exact text span from the student response, empty string if none), "
    "and \"count\" (integer, only when the rubric requires counting). "
    "Use concise descriptive key names derived from each criterion "
    "(e.g. \"defines_concept\", \"lists_two_advantages\"). "
    "Also include a top-level \"overall_notes\" string for any ambiguities."
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
        {"role": "user", "content": user_content},
    ]


def run_fextract(
    question: str,
    student_answer: str,
    rubric: str,
    endpoint: str,
    api_key: str,
    deployment: str,
    api_version: str,
) -> tuple[dict[str, Any] | None, int, int]:
    """
    Returns (extracted_json_dict, prompt_tokens, completion_tokens).
    Returns (None, ...) on content-filter hit.
    """
    retry_note = ""
    last_error: Exception | None = None
    total_pt, total_ct = 0, 0

    for attempt in range(2):
        messages = build_fextract_messages(question, student_answer, rubric, retry_note)
        raw, pt, ct = call_azure_openai(
            messages, endpoint, api_key, deployment, api_version,
            max_tokens=DEFAULT_MAX_TOKENS_EXTRACT,
        )
        total_pt += pt
        total_ct += ct

        if raw is None:
            return None, total_pt, total_ct

        try:
            parsed = json.loads(raw)
            if not isinstance(parsed, dict):
                raise ValueError("fextract output must be a JSON object")
            return parsed, total_pt, total_ct
        except Exception as exc:
            last_error = exc
            retry_note = (
                "Your previous response was not valid JSON. "
                "Return only a valid JSON object with no markdown or extra text."
            )

    raise RuntimeError(f"fextract failed after retries: {last_error}")


# ---------------------------------------------------------------------------
# Agent 2 – Scoring Agent  (fscoring)
# ---------------------------------------------------------------------------

FSCORING_SYSTEM = "Follow the instructions."

FSCORING_OUTPUT_INSTRUCTIONS = (
    "Use the boolean flags, evidence strings, and counts in the Extracted Evidence "
    "to determine the final score. "
    "If the Extracted Evidence contains inconsistencies, use the Student Response for verification. "
    "Resolve all ambiguities strictly in favour of the official rubric definitions. "
    "Return ONLY a valid JSON object with exactly two keys: "
    "\"grade\" (integer 1-6) and \"reasoning\" (one concise sentence). "
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
    question: str,
    student_answer: str,
    rubric: str,
    extracted: dict[str, Any],
    retry_note: str = "",
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
        {"role": "user", "content": user_content},
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
    question: str,
    student_answer: str,
    rubric: str,
    extracted: dict[str, Any],
    endpoint: str,
    api_key: str,
    deployment: str,
    api_version: str,
) -> tuple[dict[str, Any], int, int]:
    """
    Returns (scored_dict, prompt_tokens, completion_tokens).
    """
    retry_note = ""
    last_error: Exception | None = None
    total_pt, total_ct = 0, 0

    for attempt in range(2):
        messages = build_fscoring_messages(
            question, student_answer, rubric, extracted, retry_note
        )
        raw, pt, ct = call_azure_openai(
            messages, endpoint, api_key, deployment, api_version,
            max_tokens=DEFAULT_MAX_TOKENS_SCORE,
        )
        total_pt += pt
        total_ct += ct

        if raw is None:
            return {"grade": -1, "reasoning": "Content filter triggered."}, total_pt, total_ct

        try:
            return parse_fscoring_output(raw), total_pt, total_ct
        except Exception as exc:
            last_error = exc
            retry_note = (
                "Your previous response was invalid. "
                "Return only valid JSON with exactly the keys 'grade' (int 1-6) and 'reasoning' (string)."
            )

    raise RuntimeError(f"fscoring failed after retries: {last_error}")


# ---------------------------------------------------------------------------
# Pipeline: run both agents for one row
# ---------------------------------------------------------------------------

def grade_row(
    question: str,
    answer: str,
    rubric: str,
    endpoint: str,
    api_key: str,
    deployment: str,
    api_version: str,
) -> tuple[dict[str, Any], int, int, int, int]:
    """
    Returns (result_dict, a1_prompt_tokens, a1_completion_tokens,
                          a2_prompt_tokens, a2_completion_tokens).
    result_dict keys: grade, reasoning, extracted_evidence
    """
    # --- Agent 1 ---
    extracted, a1_pt, a1_ct = run_fextract(
        question, answer, rubric, endpoint, api_key, deployment, api_version
    )
    if extracted is None:
        return (
            {"grade": -1, "reasoning": "Content filter triggered (extraction).", "extracted_evidence": "{}"},
            a1_pt, a1_ct, 0, 0,
        )

    # --- Agent 2 ---
    scored, a2_pt, a2_ct = run_fscoring(
        question, answer, rubric, extracted,
        endpoint, api_key, deployment, api_version,
    )

    result = {
        "grade": scored["grade"],
        "reasoning": scored["reasoning"],
        "extracted_evidence": json.dumps(extracted, ensure_ascii=False),
    }
    return result, a1_pt, a1_ct, a2_pt, a2_ct


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    # --- argument parsing ---
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-row", type=int, default=1,
                        help="1-based row index to start from (skip earlier rows)")
    parser.add_argument("--resume-from", type=Path, default=None,
                        help="Path to a partial output CSV; counts its data rows and resumes grading from there")
    args = parser.parse_args()
    start_row = args.start_row
    resume_from: Path | None = args.resume_from

    load_env_file(BASE_DIR / ".env")

    if not INPUT_CSV.exists():
        raise SystemExit(f"Input CSV not found: {INPUT_CSV}")
    if not RUBRIC_FILE.exists():
        raise SystemExit(f"Rubric file not found: {RUBRIC_FILE}")
    if resume_from is not None and not resume_from.exists():
        raise SystemExit(f"Resume-from CSV not found: {resume_from}")

    endpoint = get_env("AZURE_OPENAI_ENDPOINT")
    api_key = get_env("AZURE_OPENAI_API_KEY")
    deployment = get_env("AZURE_OPENAI_DEPLOYMENT")
    api_version = get_env("AZURE_OPENAI_API_VERSION", DEFAULT_API_VERSION).strip()

    rubric = load_text(RUBRIC_FILE)

    run_start_time = datetime.now()
    start_log = OUTPUT_CSV.with_suffix(".starttime")
    start_log.write_text(run_start_time.strftime('%Y-%m-%d %H:%M:%S'), encoding="utf-8")

    # Accumulators
    total_a1_pt = total_a1_ct = 0
    total_a2_pt = total_a2_ct = 0

    # --- count already-graded rows from partial output CSV ---
    rows_to_skip = start_row - 1
    if resume_from is not None:
        with resume_from.open("r", encoding="utf-8-sig", newline="") as resumefile:
            resume_reader = csv.DictReader(resumefile, delimiter=",")
            rows_to_skip = sum(
                1 for row in resume_reader
                if (row.get("assignment") or "").strip() != "=== RUN SUMMARY ==="
            )
        print(f"Resuming: skipping first {rows_to_skip} row(s) already present in {resume_from}.")

    with (
        INPUT_CSV.open("r", encoding="utf-8-sig", newline="") as infile,
        OUTPUT_CSV.open("w", encoding="utf-8", newline="") as outfile,
    ):
        reader = csv.DictReader(infile, delimiter=",")
        fieldnames = list(reader.fieldnames or [])
        for extra in (
            "AI_grade", "AI_reasoning", "extracted_evidence",
            "a1_prompt_tokens", "a1_completion_tokens",
            "a2_prompt_tokens", "a2_completion_tokens",
        ):
            if extra not in fieldnames:
                fieldnames.append(extra)

        writer = csv.DictWriter(
            outfile, fieldnames=fieldnames, delimiter=",", quoting=csv.QUOTE_MINIMAL
        )
        writer.writeheader()

        # Advance the input reader past already-graded rows
        for _ in range(rows_to_skip):
            try:
                next(reader)
            except StopIteration:
                break

        for row_index, row in enumerate(reader, start=rows_to_skip + 1):
            question = (row.get("assignment") or "").strip()
            student_answer = (row.get("full_text") or "").strip()

            if not question:
                print(f"  Row {row_index}: missing assignment, skipping.")
                continue
            if not student_answer:
                print(f"  Row {row_index}: missing full_text, skipping.")
                continue

            print(f"Row {row_index} – running fextract ...", end=" ", flush=True)
            try:
                result, a1_pt, a1_ct, a2_pt, a2_ct = grade_row(
                    question, student_answer, rubric,
                    endpoint, api_key, deployment, api_version,
                )
            except Exception as exc:
                print(f"\n  Row {row_index}: error during grading, skipping. Reason: {exc}")
                row["AI_grade"] = "-1"
                row["AI_reasoning"] = f"Error: {exc}"
                row["extracted_evidence"] = "{}"
                row["a1_prompt_tokens"] = "0"
                row["a1_completion_tokens"] = "0"
                row["a2_prompt_tokens"] = "0"
                row["a2_completion_tokens"] = "0"
                writer.writerow(row)
                continue

            total_a1_pt += a1_pt
            total_a1_ct += a1_ct
            total_a2_pt += a2_pt
            total_a2_ct += a2_ct

            row["AI_grade"] = str(result["grade"])
            row["AI_reasoning"] = result["reasoning"]
            row["extracted_evidence"] = result["extracted_evidence"]
            row["a1_prompt_tokens"] = str(a1_pt)
            row["a1_completion_tokens"] = str(a1_ct)
            row["a2_prompt_tokens"] = str(a2_pt)
            row["a2_completion_tokens"] = str(a2_ct)
            writer.writerow(row)

            status = "SKIPPED (content filter)" if result["grade"] == -1 else f"grade={result['grade']}"
            print(
                f"fscoring done | {status} | "
                f"tokens A1 in={a1_pt} out={a1_ct}  A2 in={a2_pt} out={a2_ct}"
            )

    run_end_time = datetime.now()
    run_duration = run_end_time - run_start_time

    total_prompt = total_a1_pt + total_a2_pt
    total_completion = total_a1_ct + total_a2_ct
    total_tokens = total_prompt + total_completion

    # Append summary row
    with OUTPUT_CSV.open("a", encoding="utf-8", newline="") as outfile:
        writer = csv.DictWriter(
            outfile, fieldnames=fieldnames, delimiter=",", quoting=csv.QUOTE_MINIMAL
        )
        summary: dict[str, str] = {f: "" for f in fieldnames}
        summary["assignment"] = "=== RUN SUMMARY ==="
        summary["AI_reasoning"] = (
            f"start={run_start_time.strftime('%Y-%m-%d %H:%M:%S')} | "
            f"end={run_end_time.strftime('%Y-%m-%d %H:%M:%S')} | "
            f"duration={str(run_duration).split('.')[0]}"
        )
        summary["a1_prompt_tokens"] = str(total_a1_pt)
        summary["a1_completion_tokens"] = str(total_a1_ct)
        summary["a2_prompt_tokens"] = str(total_a2_pt)
        summary["a2_completion_tokens"] = str(total_a2_ct)
        summary["extracted_evidence"] = (
            f"total_prompt={total_prompt} | "
            f"total_completion={total_completion} | "
            f"total_tokens={total_tokens}"
        )
        writer.writerow(summary)

    # Console summary
    print("\n" + "=" * 60)
    print("AUTOSCORE RUN SUMMARY")
    print("=" * 60)
    print(f"  Start time              : {run_start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  End time                : {run_end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Duration                : {str(run_duration).split('.')[0]}")
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