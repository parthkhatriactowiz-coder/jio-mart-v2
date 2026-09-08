import pandas as pd
from database import get_db_connection

data = pd.read_excel("jiomart_inputs.xlsx")

conn = get_db_connection()
cursor = conn.cursor()

# Create table - removed UNIQUE constraint on URL to allow duplicates
cursor.execute("""
CREATE TABLE IF NOT EXISTS jiomart_products (
    id INT AUTO_INCREMENT PRIMARY KEY,
    url VARCHAR(500),
    pincode VARCHAR(10),
    status VARCHAR(20) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY unique_url_pincode (url, pincode)
)
""")

# Filter only JioMart URLs
if "URL" in data.columns and "Pincode" in data.columns:
    jiomart_data = data[
        data["URL"].astype(str).str.lower().str.contains("jiomart", na=False)
    ].copy()
    print(f"Found {len(jiomart_data)} JioMart product links")
    print(f"Skipped {len(data) - len(jiomart_data)} non-JioMart URLs")
else:
    jiomart_data = data.copy()
    print("Missing 'URL' or 'Pincode' column")

# Keep ALL rows (including duplicates) since pincodes are different
# Prepare data for bulk insert
product_data = [
    (str(row["URL"]), str(row["Pincode"]), "pending")
    for _, row in jiomart_data.iterrows()
]

# Bulk insert - allows duplicates if url+pincode combination is unique
cursor.executemany(
    "INSERT IGNORE INTO jiomart_products (url, pincode, status) VALUES (%s, %s, %s)",
    product_data,
)

conn.commit()
inserted_count = cursor.rowcount
cursor.close()
conn.close()

print(f"✅ Successfully inserted {inserted_count} JioMart product links with pincodes")
print(f"📊 Total records processed: {len(product_data)}")