from __future__ import annotations

import csv
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from datetime import datetime
import argparse

BASE_DIR = Path(__file__).resolve().parent.parent
THIS_DIR = Path(__file__).resolve().parent
INPUT_CSV = BASE_DIR / "asap2_total_master.csv"
RUBRIC_FILE = BASE_DIR / "Criteria.txt"
OUTPUT_CSV = THIS_DIR / "asap2_total_master_graded.csv"

DEFAULT_API_VERSION = "2024-12-01-preview"
DEFAULT_TEMPERATURE = 0.0
DEFAULT_MAX_TOKENS = 1000


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


def build_prompt(question: str, student_answer: str, rubric: str, retry_note: str = "") -> list[dict[str, str]]:
    output_instructions = (
        "assign exactly one integer grade from 1 to 6 and provide concise reasoning. "
        "Return JSON only, with exactly these keys: grade, reasoning. "
        "The grade must be an integer in  [1, 2, 3, 4, 5, 6]."
    )

    user_content = (
        f"Question: {question}\n"
        f"Student Answer: {student_answer}\n"
        f"Rubric: {rubric}\n"
        f"Output Instructions: {output_instructions}\n"
    )

    if retry_note:
        user_content += f"\n{retry_note}\n"

    return [
        {
            "role": "system",
            "content": (
                "Follow the instructions."
            ),
        },
        {
            "role": "user",
            "content": user_content,
        },
    ]


def call_azure_openai(
    messages: list[dict[str, str]],
    endpoint: str,
    api_key: str,
    deployment: str,
    api_version: str,
    max_retries: int = 3,
) -> tuple[str | None, int, int]:
    """Returns (content, prompt_tokens, completion_tokens)."""
    url = f"{endpoint.rstrip('/')}/openai/deployments/{deployment}/chat/completions?api-version={api_version}"
    payload = {
        "messages": messages,
        "temperature": DEFAULT_TEMPERATURE,
        "max_tokens": DEFAULT_MAX_TOKENS,
        "response_format": {"type": "json_object"},
    }
    request = urllib.request.Request(
        url=url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "api-key": api_key,
        },
        method="POST",
    )

    last_error: Exception | None = None
    for attempt in range(max_retries):
        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                response_body = response.read().decode("utf-8")

        except TimeoutError as exc:
            last_error = exc
            wait = 2 ** attempt
            print(f"  [Timeout] attempt {attempt + 1}/{max_retries}, retrying in {wait}s...")
            time.sleep(wait)
            continue

        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            if "content_filter" in error_body:
                print("Content filter triggered. Skipping this row.")
                return None, 0, 0
            if exc.code == 429 or exc.code >= 500:
                last_error = exc
                wait = 2 ** attempt
                print(f"  [HTTP {exc.code}] attempt {attempt + 1}/{max_retries}, retrying in {wait}s...")
                time.sleep(wait)
                continue
            raise RuntimeError(f"Azure OpenAI request failed: {exc.code} {exc.reason}\n{error_body}") from exc

        response_json = json.loads(response_body)
        usage = response_json.get("usage", {})
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)

        choices = response_json.get("choices", [])
        if not choices:
            raise RuntimeError(f"Azure OpenAI returned no choices: {response_body}")

        message = choices[0].get("message", {})
        content = message.get("content", "")
        if not content:
            raise RuntimeError(f"Azure OpenAI returned empty content: {response_body}")

        return content, prompt_tokens, completion_tokens

    raise RuntimeError(f"Azure OpenAI request failed after {max_retries} retries: {last_error}")


def parse_model_json(raw_text: str) -> dict[str, Any]:
    parsed = json.loads(raw_text)
    if not isinstance(parsed, dict):
        raise ValueError("Model output is not a JSON object")

    if "grade" not in parsed or "reasoning" not in parsed:
        raise ValueError("Model output must include grade and reasoning")

    grade_value = parsed["grade"]
    if not isinstance(grade_value, int):
        raise ValueError("Grade must be an integer")

    if grade_value < 1 or grade_value > 6:
        raise ValueError("Grade must be between 1 and 6")

    reasoning_value = parsed["reasoning"]
    if not isinstance(reasoning_value, str) or not reasoning_value.strip():
        raise ValueError("Reasoning must be a non-empty string")

    return {
        "grade": grade_value,
        "reasoning": reasoning_value.strip(),
    }


def grade_row(
    question: str,
    answer: str,
    rubric: str,
    endpoint: str,
    api_key: str,
    deployment: str,
    api_version: str,
) -> tuple[dict[str, Any], int, int]:
    """Returns (graded_result, prompt_tokens, completion_tokens)."""
    retry_note = ""
    last_error: Exception | None = None
    total_prompt_tokens = 0
    total_completion_tokens = 0

    for attempt in range(2):
        try:
            messages = build_prompt(question, answer, rubric, retry_note=retry_note)
            raw_content, prompt_tokens, completion_tokens = call_azure_openai(
                messages, endpoint, api_key, deployment, api_version
            )
            total_prompt_tokens += prompt_tokens
            total_completion_tokens += completion_tokens

            if raw_content is None:
                return {"grade": -1, "reasoning": "Content filter triggered."}, total_prompt_tokens, total_completion_tokens

            try:
                return parse_model_json(raw_content), total_prompt_tokens, total_completion_tokens
            except Exception as exc:
                last_error = exc
                retry_note = (
                    "Your previous response was invalid. Return only valid JSON with exactly the keys "
                    "grade and reasoning. The grade must be a single integer from 1 to 6."
                )

        except Exception as exc:
            last_error = exc
            print(f"  [Error] {exc}")

    print(f"  Giving up on this row, recording grade=-1. Last error: {last_error}")
    return {"grade": -1, "reasoning": f"Error: {last_error}"}, total_prompt_tokens, total_completion_tokens


def main() -> int:
    # --- argument parsing ---
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-row", type=int, default=1,
                        help="1-based row index to start from (skip earlier rows)")
    parser.add_argument("--resume-from", type=Path, default=None,
                        help="Path to a partial output CSV to resume from; already-graded rows are "
                             "copied through and new grading continues after them")
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
    total_prompt_tokens = 0
    total_completion_tokens = 0

    with INPUT_CSV.open("r", encoding="utf-8-sig", newline="") as infile, OUTPUT_CSV.open(
        "w", encoding="utf-8", newline=""
    ) as outfile:
        reader = csv.DictReader(infile, delimiter=",")
        fieldnames = list(reader.fieldnames or [])
        for extra_field in ("AI_grade", "AI_reasoning", "prompt_tokens", "completion_tokens"):
            if extra_field not in fieldnames:
                fieldnames.append(extra_field)

        writer = csv.DictWriter(outfile, fieldnames=fieldnames, delimiter=",", quoting=csv.QUOTE_MINIMAL)
        writer.writeheader()

        # --- resume logic: copy already-graded rows from partial output CSV ---
        rows_copied = 0
        if resume_from is not None:
            with resume_from.open("r", encoding="utf-8-sig", newline="") as resumefile:
                resume_reader = csv.DictReader(resumefile, delimiter=",")
                for resume_row in resume_reader:
                    # Skip summary rows
                    if (resume_row.get("assignment") or "").strip() == "=== RUN SUMMARY ===":
                        continue
                    # Ensure the row has all expected fieldnames (fill missing with empty string)
                    out_row = {field: resume_row.get(field, "") for field in fieldnames}
                    writer.writerow(out_row)
                    rows_copied += 1

            print(f"Resumed {rows_copied} already-graded row(s) from {resume_from}.")

        # Advance the input reader past the already-copied rows
        rows_to_skip = rows_copied if resume_from is not None else (start_row - 1)
        for _ in range(rows_to_skip):
            try:
                next(reader)
            except StopIteration:
                break

        # --- main grading loop ---
        for row_index, row in enumerate(reader, start=rows_to_skip + 1):
            question = (row.get("assignment") or "").strip()
            student_answer = (row.get("full_text") or "").strip()

            if not question:
                raise SystemExit(f"Missing question_text in row {row_index}")
            if not student_answer:
                raise SystemExit(f"Missing student_answer in row {row_index}")

            graded, row_prompt_tokens, row_completion_tokens = grade_row(
                question, student_answer, rubric, endpoint, api_key, deployment, api_version
            )

            total_prompt_tokens += row_prompt_tokens
            total_completion_tokens += row_completion_tokens

            row["AI_grade"] = str(graded["grade"])
            row["AI_reasoning"] = graded["reasoning"]
            row["prompt_tokens"] = str(row_prompt_tokens)
            row["completion_tokens"] = str(row_completion_tokens)
            writer.writerow(row)

            if graded["grade"] == -1:
                print(f"Skipped row {row_index} (grade=-1): {graded['reasoning']}")
            else:
                print(
                    f"Graded row {row_index}: grade={graded['grade']} "
                    f"| tokens in={row_prompt_tokens} out={row_completion_tokens}"
                )

    run_end_time = datetime.now()
    run_duration = run_end_time - run_start_time
    total_tokens = total_prompt_tokens + total_completion_tokens

    # Append a summary row at the bottom of the CSV
    with OUTPUT_CSV.open("a", encoding="utf-8", newline="") as outfile:
        writer = csv.DictWriter(outfile, fieldnames=fieldnames, delimiter=";", quoting=csv.QUOTE_MINIMAL)
        summary_row: dict[str, str] = {field: "" for field in fieldnames}
        summary_row["assignment"] = "=== RUN SUMMARY ==="
        summary_row["AI_reasoning"] = (
            f"start={run_start_time.strftime('%Y-%m-%d %H:%M:%S')} | "
            f"end={run_end_time.strftime('%Y-%m-%d %H:%M:%S')} | "
            f"duration={str(run_duration).split('.')[0]} | "
            f"total_prompt_tokens={total_prompt_tokens} | "
            f"total_completion_tokens={total_completion_tokens} | "
            f"total_tokens={total_tokens}"
        )
        summary_row["prompt_tokens"] = str(total_prompt_tokens)
        summary_row["completion_tokens"] = str(total_completion_tokens)
        writer.writerow(summary_row)

    # Print summary to console
    print("\n" + "=" * 55)
    print("RUN SUMMARY")
    print("=" * 55)
    print(f"  Start time   : {run_start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  End time     : {run_end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Duration     : {str(run_duration).split('.')[0]}")
    print(f"  Prompt tokens: {total_prompt_tokens:,}")
    print(f"  Compl. tokens: {total_completion_tokens:,}")
    print(f"  Total tokens : {total_tokens:,}")
    print("=" * 55)
    print(f"Wrote graded output to {OUTPUT_CSV}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())