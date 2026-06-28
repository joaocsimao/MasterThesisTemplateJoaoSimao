import pandas as pd

# 1. Manually list your 3 specific file paths here
file_paths = [
    "/home/simao/ThesisTesing/ASAP2.0/MAS-H2/MAS-H2a/asap2MASgradeduntil9515.csv",
    "/home/simao/ThesisTesing/ASAP2.0/MAS-H2/MAS-H2a/MASGradedfrom9515.csv"
]

print("Starting to merge the following files:")
for path in file_paths:
    print(f" -> Reading: {path}")

# 2. Read the specific files into DataFrames
df_list = [pd.read_csv(file) for file in file_paths]

# 3. Combine them into one
combined_df = pd.concat(df_list, ignore_index=True)

# 4. Save the final result
combined_df.to_csv("MASgraded.csv", index=False)

print("\nSuccess! Your 3 files have been merged into 'combined_output.csv'.")