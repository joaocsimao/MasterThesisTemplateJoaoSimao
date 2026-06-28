"""
clean_csv_column.py

Checks a specific column in a CSV for empty or NaN values and removes those rows.

Usage:
    python clean_csv_column.py <file.csv> <column_name> [dry-run]

Examples:
    python clean_csv_column.py data.csv email            # deletes rows and saves
    python clean_csv_column.py data.csv email dry-run    # only reports, no changes
"""

import sys
import pandas as pd


def check_and_clean(filepath: str, column: str, dry_run: bool) -> None:
    # Load CSV
    try:
        df = pd.read_csv(filepath)
    except FileNotFoundError:
        print(f"Error: File '{filepath}' not found.")
        sys.exit(1)
    except Exception as e:
        print(f"Error reading CSV: {e}")
        sys.exit(1)

    # Validate column exists
    if column not in df.columns:
        print(f"Error: Column '{column}' not found in CSV.")
        print(f"Available columns: {', '.join(df.columns)}")
        sys.exit(1)

    total_rows = len(df)

    # Identify empty/NaN rows: covers None, NaN, and whitespace-only strings
    empty_mask = df[column].isna() | df[column].astype(str).str.strip().eq("")
    empty_rows = df[empty_mask]
    empty_count = len(empty_rows)

    print(f"\nFile       : {filepath}")
    print(f"Column     : {column}")
    print(f"Total rows : {total_rows}")
    print(f"Empty/NaN  : {empty_count}")

    if empty_count == 0:
        print("\nNo empty or NaN values found. Nothing to do.")
        return

    # Show which rows are affected (row index + preview)
    print(f"\nAffected rows (first 10 shown):")
    print("-" * 50)
    preview = empty_rows.head(10)
    for idx, row in preview.iterrows():
        print(f"  Row {idx:>5}: ")
    if empty_count > 10:
        print(f"  ... and {empty_count - 10} more.")
    print("-" * 50)

    if dry_run:
        print(f"\n[DRY-RUN] No changes made. Would have deleted {empty_count} row(s).")
        print(f"[DRY-RUN] Rows remaining after clean: {total_rows - empty_count}")
    else:
        cleaned_df = df[~empty_mask]
        cleaned_df.to_csv(filepath, index=False)
        print(f"\nDeleted {empty_count} row(s). File saved: {filepath}")
        print(f"Rows remaining: {len(cleaned_df)}")


def main():
    if len(sys.argv) < 3:
        print("Usage: python clean_csv_column.py <file.csv> <column_name> [dry-run]")
        sys.exit(1)

    filepath = sys.argv[1]
    column   = sys.argv[2]
    dry_run  = len(sys.argv) >= 4 and sys.argv[3].lower() == "dry-run"

    if dry_run:
        print("Mode: DRY-RUN (no changes will be written)")
    else:
        print("Mode: LIVE (rows will be deleted and file overwritten)")

    check_and_clean(filepath, column, dry_run)


if __name__ == "__main__":
    main()