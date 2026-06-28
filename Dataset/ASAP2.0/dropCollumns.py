import pandas as pd
import os

def clean_grading_csv(file_path, output_path="cleaned_asap2_dataset.csv"):
    """
    Loads the dataset and drops the specified demographic/metadata columns.
    """
    if not os.path.exists(file_path):
        print(f"[!] Error: File not found at '{file_path}'")
        return

    print(f"[*] Loading dataset: {os.path.basename(file_path)}...")
    
    # Using the robust python engine to ensure student essay paragraph breaks don't crash it
    df = pd.read_csv(file_path, sep=None, engine='python', on_bad_lines='skip')
    
    # The exact list of columns you want to remove (matching your spelling/headers)
    columns_to_drop = [
        'set', 
        'pubpriv', 
        'economically_disadvantaged', 
        'student_disability_status', 
        'ell_status', 
        'race_ethnicity', 
        'gender',
        'task'
    ]
    
    # Filter the drop list to only include columns that actually exist in the file
    existing_drops = [col for col in columns_to_drop if col in df.columns]
    
    print(f"[*] Dropping columns: {existing_drops}")
    df_cleaned = df.drop(columns=existing_drops)
    
    # Save the polished dataframe
    print(f"[*] Saving cleaned file to: {output_path}")
    df_cleaned.to_csv(output_path, index=False)
    
    print("-" * 60)
    print(f"[+] Success! Remaining columns: {list(df_cleaned.columns)}")
    print(f"[+] Total rows preserved: {len(df_cleaned):,}")

if __name__ == '__main__':
    # Update this path to match your target file
    INPUT_FILE = "/home/simao/ThesisTesing/Dataset/ASAP2.0/asap2_total_master.csv"
    OUTPUT_FILE = "/home/simao/ThesisTesing/Dataset/ASAP2.0/cleaned_asap2_dataset.csv"
    
    clean_grading_csv(INPUT_FILE, OUTPUT_FILE)