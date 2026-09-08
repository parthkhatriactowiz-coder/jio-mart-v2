from database import get_db_connection


def create_location_table():
    connection = get_db_connection()
    cursor = connection.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS location_coordinate (
            id INT AUTO_INCREMENT PRIMARY KEY,
            latitude VARCHAR(50),
            longitude VARCHAR(50),
            country VARCHAR(100),
            country_iso_code VARCHAR(10),
            city VARCHAR(100),
            pincode VARCHAR(10),
            state VARCHAR(100),
            store_ids TEXT,
            polygon_id TEXT
        )
    """)

    connection.commit()

    cursor.close()
    connection.close()


def get_pending_pincodes():
    connection = get_db_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT pincode
        FROM pincodes
        WHERE status = 'pending'
    """)

    pincodes = [row[0] for row in cursor.fetchall()]

    cursor.close()
    connection.close()

    return pincodes


def save_location(location):
    connection = get_db_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO location_coordinate (
            latitude,
            longitude,
            country,
            country_iso_code,
            city,
            pincode,
            state,
            store_ids,
            polygon_id
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """,
        (
            location["latitude"],
            location["longitude"],
            location["country"],
            location["country_iso_code"],
            location["city"],
            location["pincode"],
            location["state"],
            location["store_ids"],
            location["polygon_id"],
        ),
    )

    connection.commit()

    cursor.close()
    connection.close()


def update_pincode_status(pincode, status):
    connection = get_db_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        UPDATE pincodes
        SET status = %s
        WHERE pincode = %s
    """,
        (status, pincode),
    )

    connection.commit()

    cursor.close()
    connection.close()
