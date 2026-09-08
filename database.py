import json
import mysql.connector
from mysql.connector import pooling
from logger_config import logger
from utils import serialize_field

DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "actowiz",
    "database": "jio_mart",
}

_db_pool = None


def init_db_pool(pool_size=20):
    global _db_pool
    if _db_pool is None:
        try:
            _db_pool = pooling.MySQLConnectionPool(
                pool_name="jiomart_pool",
                pool_size=pool_size,
                pool_reset_session=True,
                **DB_CONFIG,
            )
            logger.info(f"Initialized MySQL connection pool with size {pool_size}")
        except mysql.connector.Error as e:
            logger.error(f"Error initializing connection pool: {e}")
            raise


def get_db_connection():
    global _db_pool
    if _db_pool is None:
        init_db_pool()
    return _db_pool.get_connection()


def init_db():
    """Create scraped_products table with dedicated columns if it does not exist."""
    create_table_query = """
    CREATE TABLE IF NOT EXISTS scraped_products (
        id INT AUTO_INCREMENT PRIMARY KEY,
        product_id INT,
        url VARCHAR(500) NOT NULL,
        pincode VARCHAR(10) NOT NULL,
        latitude VARCHAR(50),
        longitude VARCHAR(50),
        country VARCHAR(100),
        country_iso_code VARCHAR(10),
        city VARCHAR(100),
        state VARCHAR(100),
        store_ids TEXT,
        polygon_id TEXT,
        product_name VARCHAR(255),
        slug VARCHAR(255) NOT NULL,
        size VARCHAR(50),
        available TINYINT(1),
        quantity VARCHAR(50),
        brand_name VARCHAR(100),
        sold_by VARCHAR(100),
        origin_countries VARCHAR(255),
        manufacturer_name VARCHAR(255),
        manufacturer_address TEXT,
        product_code VARCHAR(100),
        shelf_life VARCHAR(50),
        key_features TEXT,
        item_dimensions TEXT,
        item_specifications TEXT,
        product_showcase TEXT,
        disclaimer TEXT,
        raw_response_hash CHAR(64),
        variants JSON,
        
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        
        UNIQUE KEY unique_product_pincode (url(255), pincode)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(create_table_query)
        conn.commit()
        cursor.close()
        conn.close()
        logger.info("Database table 'scraped_products' checked/created successfully.")
    except mysql.connector.Error as e:
        logger.error(f"Failed to initialize database table: {e}")
        raise


def get_headers(pincode):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT latitude,
                   longitude,
                   country,
                   country_iso_code,
                   city,
                   pincode,
                   state,
                   store_ids,   
                   polygon_id
            FROM location_coordinate
            WHERE pincode = %s
            """,
            (pincode,),
        )
        result = cursor.fetchone()
        cursor.close()
        conn.close()

        if not result:
            logger.warning(f"No location headers found for pincode {pincode}")
            return None

        keys = [
            "latitude",
            "longitude",
            "country",
            "country_iso_code",
            "city",
            "pincode",
            "state",
            "store_ids",
            "polygon_id",
        ]

        return dict(zip(keys, map(str, result)))

    except mysql.connector.Error as e:
        logger.error(f"Database error in get_headers for pincode {pincode}: {e}")
        return None


def get_pending_pincodes_batch(batch_size=100):
    """
    Fetch pending JioMart products in batches.
    Returns list of records: (id, url, pincode)
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        query = """
            SELECT id, url, pincode
            FROM jiomart_products
            WHERE status = 'pending'
            ORDER BY id
            LIMIT %s
        """
        cursor.execute(query, (batch_size,))
        batch = cursor.fetchall()
        cursor.close()
        conn.close()
        return batch
    except mysql.connector.Error as e:
        logger.error(f"Database error fetching pending batch: {e}")
        return []


def save_scraped_product(
    product_id, url, pincode, location, product_data, raw_response_hash=None
):

    loc = location or {}

    latitude = loc.get("latitude")
    longitude = loc.get("longitude")
    country = loc.get("country")
    country_iso_code = loc.get("country_iso_code")
    city = loc.get("city")
    state = loc.get("state")
    store_ids = loc.get("store_ids")
    polygon_id = loc.get("polygon_id")

    product_name = product_data.get("product_name")
    slug = product_data.get("slug") or url.split("/product/")[-1]
    size = product_data.get("size")
    available = 1 if product_data.get("available") else 0
    quantity = product_data.get("quantity")
    brand_name = product_data.get("brand_name")
    sold_by = product_data.get("sold_by")
    origin_countries = serialize_field(product_data.get("origin_countries"))
    manufacturer_name = product_data.get("manufacturer_name")
    manufacturer_address = product_data.get("manufacturer_address")
    product_code = product_data.get("product_code")
    shelf_life = product_data.get("shelf_life")
    key_features = serialize_field(product_data.get("key_features"))
    item_dimensions = serialize_field(product_data.get("item_dimensions"))
    item_specifications = serialize_field(product_data.get("item_specifications"))
    product_showcase = product_data.get("product_showcase")
    disclaimer = product_data.get("disclaimer")

    variants = product_data.get("variants") or []
    if not variants:
        variants = [
            {
                "slug": slug,
                "size": size,
                "in_stock": available,
                "error": "No price variants found",
            }
        ]

    variants_json = json.dumps(variants, ensure_ascii=False)

    insert_query = """
        INSERT INTO scraped_products (
            product_id, url, pincode,
            latitude, longitude, country, country_iso_code, city, state, store_ids, polygon_id,
            product_name, slug, size, available, quantity, brand_name, sold_by, origin_countries,
            manufacturer_name, manufacturer_address, product_code, shelf_life, key_features,
            item_dimensions, item_specifications, product_showcase, disclaimer,
            raw_response_hash, variants
        ) VALUES (
            %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s
        ) ON DUPLICATE KEY UPDATE
            product_id = VALUES(product_id),
            latitude = VALUES(latitude),
            longitude = VALUES(longitude),
            country = VALUES(country),
            country_iso_code = VALUES(country_iso_code),
            city = VALUES(city),
            state = VALUES(state),
            store_ids = VALUES(store_ids),
            polygon_id = VALUES(polygon_id),
            product_name = VALUES(product_name),
            size = VALUES(size),
            available = VALUES(available),
            quantity = VALUES(quantity),
            brand_name = VALUES(brand_name),
            sold_by = VALUES(sold_by),
            origin_countries = VALUES(origin_countries),
            manufacturer_name = VALUES(manufacturer_name),
            manufacturer_address = VALUES(manufacturer_address),
            product_code = VALUES(product_code),
            shelf_life = VALUES(shelf_life),
            key_features = VALUES(key_features),
            item_dimensions = VALUES(item_dimensions),
            item_specifications = VALUES(item_specifications),
            product_showcase = VALUES(product_showcase),
            disclaimer = VALUES(disclaimer),
            raw_response_hash = VALUES(raw_response_hash),
            variants = VALUES(variants),
            updated_at = CURRENT_TIMESTAMP;
    """

    row = (
        product_id,
        url,
        pincode,
        latitude,
        longitude,
        country,
        country_iso_code,
        city,
        state,
        store_ids,
        polygon_id,
        product_name,
        slug,
        size,
        available,
        quantity,
        brand_name,
        sold_by,
        origin_countries,
        manufacturer_name,
        manufacturer_address,
        product_code,
        shelf_life,
        key_features,
        item_dimensions,
        item_specifications,
        product_showcase,
        disclaimer,
        raw_response_hash,
        variants_json,
    )

    update_status_query = """
        UPDATE jiomart_products
        SET status = 'completed'
        WHERE id = %s;
    """

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(insert_query, row)
        cursor.execute(update_status_query, (product_id,))

        conn.commit()
        cursor.close()
        logger.info(
            f"Successfully saved product with {len(variants)} variant(s) for product_id={product_id}, pincode={pincode}"
        )
        return True
    except mysql.connector.Error as e:
        logger.error(f"Error saving product_id={product_id}: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn and conn.is_connected():
            conn.close()


def update_product_status(product_id, status):
    """Update status of product in jiomart_products table."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE jiomart_products SET status = %s WHERE id = %s",
            (status, product_id),
        )
        conn.commit()
        cursor.close()
        logger.info(f"Updated product_id={product_id} status to '{status}'")
    except mysql.connector.Error as e:
        logger.error(f"Failed to update status for product_id={product_id}: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn and conn.is_connected():
            conn.close()
