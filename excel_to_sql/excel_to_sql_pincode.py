import pandas as pd
from database import get_db_connection

data = pd.read_excel("jiomart_inputs.xlsx")

conn = get_db_connection()
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS pincodes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    pincode VARCHAR(10) UNIQUE,
    status VARCHAR(20) DEFAULT 'pending'
)
""")

# Filter out Dmart URLs
if 'URL' in data.columns:
    # Convert to string and check if URL contains 'dmart' (case-insensitive)
    data['is_dmart'] = data['URL'].astype(str).str.lower().str.contains('dmart', na=False)
    
    # Count skipped rows
    skipped_count = data['is_dmart'].sum()
    filtered_data = data[~data['is_dmart']]
    
    print(f"Skipped {skipped_count} rows with Dmart URLs")
    print(f"Processing {len(filtered_data)} rows")
else:
    filtered_data = data
    print("No 'URL' column found, processing all rows")

# Get unique pincodes from filtered data
unique_pincodes = filtered_data["Pincode"].unique()

for pincode in unique_pincodes:
    pincode = str(pincode)

    cursor.execute(
        "INSERT IGNORE INTO pincodes (pincode, status) VALUES (%s, 'pending')",
        (pincode,),
    )

conn.commit()
cursor.close()
conn.close()

print(f"Data inserted successfully! Inserted {len(unique_pincodes)} unique pincodes.")