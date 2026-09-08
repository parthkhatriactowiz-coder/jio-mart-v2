import json
import threading
import time
from curl_cffi import requests

from config import BASE_URL, JIOMART_TOKEN, PRICE_URL
from extractors import (
    extract_price_items,
    extract_product_data,
    extract_variant_sizes,
)
from logger_config import logger
from utils import extract_variant_size_pairs


class JioMartAccessDenied(Exception):
    """Raised when JioMart or its CDN blocks an API request."""


class JioMartClient:
    def __init__(self):
        self._thread_state = threading.local()
        self.access_denied = threading.Event()

    def _get_session(self):
        session = getattr(self._thread_state, "session", None)
        if session is None:
            session = requests.Session(impersonate="chrome")
            self._thread_state.session = session
        return session

    def _build_headers(self, location, content_type=False):
        headers = {
            "accept": "application/json, text/plain, */*",
            "authorization": JIOMART_TOKEN,
            "user-agent": "Mozilla/5.0",
            "accept-language": "en-US,en;q=0.9",
            "referer": "https://www.jiomart.com/",
            "origin": "https://www.jiomart.com",
            "x-currency-code": "INR",
            "x-fp-sdk-version": "1.10.3-70",
            "x-geolocation": json.dumps(
                {
                    "latitude": location.get("latitude", ""),
                    "longitude": location.get("longitude", ""),
                    "polygon_ids": location.get("polygon_ids", []),
                }
            ),
            "x-location-detail": json.dumps(
                {
                    "country": location.get("country", ""),
                    "country_iso_code": location.get("country_iso_code", ""),
                    "city": location.get("city", ""),
                    "pincode": location.get("pincode", ""),
                    "state": location.get("state", ""),
                }
            ),
        }
        if content_type:
            headers["content-type"] = "application/json"
        return headers

    def _request(self, method, url, **kwargs):
        for attempt in range(3):
            response = self._get_session().request(method, url, **kwargs)
            if response.status_code == 403:
                self.access_denied.set()
                logger.error(
                    "JioMart denied access (403) for %s. Check the token or network access."
                    % url
                )
                raise JioMartAccessDenied()
            if response.status_code not in (429, 500, 502, 503, 504):
                return response
            if attempt < 2:
                time.sleep(2**attempt)
        return response

    def get_product_info(self, product_path, location):
        url = f"{BASE_URL}/{product_path}"
        try:
            response = self._request(
                "GET",
                url,
                headers=self._build_headers(location),
                params={"store_ids": location.get("store_ids", [])},
                timeout=30,
            )
            if response.status_code != 200:
                logger.warning(
                    f"Failed product info fetch for {product_path} (Status {response.status_code})"
                )
                return None
            raw_data = response.json()
            return (
                extract_product_data(raw_data, pincode=location.get("pincode")),
                raw_data,
            )
        except JioMartAccessDenied:
            raise
        except Exception as e:
            logger.error(f"Error fetching product info for {product_path}: {e}")
            return None

    def _fetch_variants_raw(self, product_path, location):
        url = f"{BASE_URL}/{product_path}/variants"
        try:
            response = self._request(
                "GET",
                url,
                headers=self._build_headers(location),
                params={"store_ids": location.get("store_ids", [])},
                timeout=30,
            )
            if response.status_code != 200:
                logger.debug(
                    f"Variants fetch status {response.status_code} for {product_path}"
                )
                return None
            return response.json()
        except JioMartAccessDenied:
            raise
        except Exception as e:
            logger.error(f"Error fetching variants for {product_path}: {e}")
            return None

    def get_product_variants(self, product_path, location):
        res = self._fetch_variants_raw(product_path, location)
        if res is None:
            return None
        return extract_variant_sizes(res)

    def get_product_prices(self, product_path, location, size=None):
        variants_res = self._fetch_variants_raw(product_path, location)
        variant_pairs = (
            extract_variant_size_pairs(variants_res) if variants_res else None
        )
        if not variant_pairs:
            variant_pairs = [{"slug": product_path, "size": size}]

        logger.debug(
            f"Fetching prices for {len(variant_pairs)} variant(s) of {product_path}"
        )
        try:
            response = self._request(
                "POST",
                PRICE_URL,
                headers=self._build_headers(location, content_type=True),
                json={"items": variant_pairs},
                timeout=30,
            )
            if response.status_code != 200:
                logger.warning(
                    f"Failed price fetch for {product_path} (Status {response.status_code})"
                )
                return None
            raw_data = response.json()
            return (
                extract_price_items(raw_data, pincode=location.get("pincode")),
                {"variants": variants_res, "prices": raw_data},
            )
        except JioMartAccessDenied:
            raise
        except Exception as e:
            logger.error(f"Error fetching prices for {product_path}: {e}")
            return None
