import pandas as pd
import argparse

def main():
    parser = argparse.ArgumentParser(description="Analyze essay word count statistics.")
    parser.add_argument("csv_path", help="Path to the CSV file")

    args = parser.parse_args()

    df = pd.read_csv(args.csv_path, sep=None, engine="python")
    print(df["essay_word_count"].describe())

if __name__ == "__main__":
    main()