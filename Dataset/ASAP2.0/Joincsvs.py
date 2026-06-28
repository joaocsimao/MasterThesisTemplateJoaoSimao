import pandas as pd
import os

def append_grading_csvs(file1_path, file2_path, output_path="asap2_master_dataset.csv"):
    """
    Validates headers and appends two large text-heavy CSVs together safely.
    """
    print("=" * 70)
    print("         ASAP 2.0 DATASET APPEND & HEADER CHECKER")
    print("=" * 70)

    # 1. Check if files exist
    if not os.path.exists(file1_path) or not os.path.exists(file2_path):
        print("[!] Error: One or both input paths do not exist. Check your paths.")
        return

    # 2. Read the CSVs safely using the Python engine (handles paragraph breaks)
    print(f"[*] Loading File 1: {os.path.basename(file1_path)}")
    df1 = pd.read_csv(file1_path, sep=None, engine='python', on_bad_lines='skip')
    
    print(f"[*] Loading File 2: {os.path.basename(file2_path)}")
    df2 = pd.read_csv(file2_path, sep=None, engine='python', on_bad_lines='skip')

    headers1 = list(df1.columns)
    headers2 = list(df2.columns)

    # 3. Header Structural Alignment Validation
    print("\n[*] Validating structural alignment...")
    if headers1 == headers2:
        print("[+] Success: Headers match perfectly!")
    else:
        print("[!] Warning: Columns do not match perfectly.")
        
        # Find exact differences to help you debug if something is wrong
        missing_in_file2 = set(headers1) - set(headers2)
        missing_in_file1 = set(headers2) - set(headers1)
        
        if missing_in_file2:
            print(f"    -> Columns in File 1 missing from File 2: {missing_in_file2}")
        if missing_in_file1:
            print(f"    -> Columns in File 2 missing from File 1: {missing_in_file1}")
        print("[*] Proceeding with structural alignment append (Pandas will fill missing columns with NaN)...")

    # 4. Append/Concatenate DataFrames
    print(f"\n[*] Appending datasets side-by-side...")
    print(f"    -> File 1 Data Rows: {len(df1):,}")
    print(f"    -> File 2 Data Rows: {len(df2):,}")
    
    # ignore_index=True resets the index counter so it goes cleanly from 0 up to the combined total
    combined_df = pd.concat([df1, df2], ignore_index=True)
    
    # 5. Export Master CSV
    print(f"[*] Saving unified master dataset to: {output_path}")
    # index=False ensures we don't write an ugly, unnamed row counter column
    combined_df.to_csv(output_path, index=False)
    
    print("-" * 70)
    print(f"[+] Complete! Total combined master rows: {len(combined_df):,}")
    print("=" * 70)

if __name__ == '__main__':
    # Update these paths to match your folder setup exactly
    FILE_TRAIN = "/home/simao/ThesisTesing/Dataset/ASAP2.0/ASAP_2_Final_github_train.csv"
    FILE_TEST  = "/home/simao/ThesisTesing/Dataset/ASAP2.0/ASAP_2_Final_github_test.csv"
    MASTER_OUT = "/home/simao/ThesisTesing/Dataset/ASAP2.0/asap2_total_master.csv"
    
    append_grading_csvs(FILE_TRAIN, FILE_TEST, MASTER_OUT)