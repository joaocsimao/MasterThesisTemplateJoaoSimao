import pandas as pd
import os

def count_true_essays(file_path):
    if not os.path.exists(file_path):
        print(f"[!] File not found: {file_path}")
        return
        
    print(f"[*] Processing {os.path.basename(file_path)}...")
    
    # We use sep=None and engine='python' to auto-detect whether it uses commas or semicolons
    # This prevents paragraph breaks from being counted as rows
    try:
        df = pd.read_csv(file_path, sep=None, engine='python', on_bad_lines='skip')
        print(f"    -> Real Essay Count (Rows): {len(df):,}")
        print(f"    -> Detected Columns: {list(df.columns[:4])} ...") # Show first few columns
        return len(df)
    except Exception as e:
        print(f"[!] Error parsing file: {e}")

if __name__ == '__main__':
    # Update these to your exact paths
    FILE1 = "/home/simao/ThesisTesing/Dataset/ASAP2.0/ASAP_2_Final_github_test.csv"
    FILE2 = "/home/simao/ThesisTesing/Dataset/ASAP2.0/ASAP_2_Final_github_train.csv"
    
    total = 0
    for f in [FILE1, FILE2]:
        count = count_true_essays(f)
        if count:
            total += count
            
    print(f"\n[+] Total actual essays across processed files: {total:,}")