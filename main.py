from concurrent.futures import ThreadPoolExecutor, as_completed

from database import (
    get_headers,
    get_pending_pincodes_batch,
    init_db,
    init_db_pool,
    save_scraped_product,
    update_product_status,
)
from jiomart_client import JioMartAccessDenied, JioMartClient
from logger_config import logger
from utils import save_raw_response_gzip

MAX_WORKERS = 2
BATCH_SIZE = 100


def process_product_item(client, item):
    product_id, url, pincode = item
    logger.info(f"Processing product_id={product_id}, pincode={pincode}")

    location = get_headers(pincode)
    if not location:
        logger.warning(
            f"No location headers for product_id={product_id}, pincode={pincode}"
        )
        update_product_status(product_id, "no_location")
        return False

    product_path = url.split("/product/")[-1]

    if client.access_denied.is_set():
        return False

    try:
        product_result = client.get_product_info(product_path, location)
    except JioMartAccessDenied:
        logger.error(
            f"JioMart access denied for product_id={product_id}; leaving item pending"
        )
        return False
    if product_result is None:
        logger.warning(
            f"Product info returned None for product_id={product_id}, pincode={pincode}"
        )
        update_product_status(product_id, "failed")
        return False
    product_data, product_raw = product_result

    try:
        price_result = client.get_product_prices(
            product_path, location, size=product_data.get("size")
        )
    except JioMartAccessDenied:
        logger.error(
            f"JioMart access denied while fetching prices for product_id={product_id}; leaving item pending"
        )
        return False
    variants, price_raw = price_result or (None, None)
    product_data["variants"] = variants

    raw_response_hash = save_raw_response_gzip(
        url,
        pincode,
        {"product": product_raw, "prices": price_raw},
    )
    saved = save_scraped_product(
        product_id,
        url,
        pincode,
        location,
        product_data,
        raw_response_hash,
    )
    return saved


def main():
    logger.info("Starting JioMart Scraper...")

    init_db_pool(pool_size=MAX_WORKERS + 5)
    init_db()

    client = JioMartClient()
    total_processed = 0

    while True:
        batch = get_pending_pincodes_batch(batch_size=BATCH_SIZE)
        if not batch:
            logger.info("No more pending products found. Scraping complete.")
            break

        logger.info(
            f"Fetched batch of {len(batch)} pending products. Processing with {MAX_WORKERS} workers..."
        )

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {
                executor.submit(process_product_item, client, item): item
                for item in batch
            }

            for future in as_completed(futures):
                item = futures[future]
                try:
                    success = future.result()
                    if success:
                        total_processed += 1
                except Exception as e:
                    logger.error(
                        f"Unhandled exception processing item {item}: {e}"
                    )

        if client.access_denied.is_set():
            logger.error(
                "Stopping scraper because JioMart access was denied. Pending products were not marked as failed."
            )
            break

        logger.info(
            f"Batch completed. Total processed so far: {total_processed}"
        )

    logger.info(
        f"Scraper finished. Total products processed: {total_processed}"
    )


if __name__ == "__main__":
    main()
