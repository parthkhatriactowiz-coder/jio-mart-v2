import json

import requests
from datetime import datetime, timezone

from excel_to_sql.location_databse import (
    create_location_table,
    get_pending_pincodes,
    save_location,
    update_pincode_status,
)
from config import GOOGLE_API_KEY, JIOMART_TOKEN


def get_jiomart_headers(data):
    fp_date = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    headers = {
        "accept": "application/json, text/plain, */*",
        "authorization": JIOMART_TOKEN,
        "cache-control": "no-cache",
        "pragma": "no-cache",
        "user-agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/152.0.0.0 Safari/537.36"
        ),
        "x-currency-code": "INR",
        "x-fp-date": fp_date,
        "x-fp-sdk-version": "1.10.3-70",
        "x-fp-signature": (
            "v1.1:46b60c1b8ae4e1f26410cdef12c9cc16b78ac3e2aa53ebcf8c0edcaca22097e1"
        ),
        "x-geolocation": (
            f'{{"latitude":"{data["latitude"]}",' f'"longitude":"{data["longitude"]}"}}'
        ),
        "x-location-detail": (
            f'{{"country":"{data["country"]}",'
            f'"country_iso_code":"{data["country_iso_code"]}",'
            f'"city":"{data["city"]}",'
            f'"pincode":"{data["pincode"]}",'
            f'"state":"{data["state"]}"}}'
        ),
    }

    return headers


def get_location_details(pincode):
    url = "https://maps.googleapis.com/maps/api/geocode/json"

    params = {
        "address": f"{pincode}, India",
        "key": GOOGLE_API_KEY,
    }

    response = requests.get(
        url,
        params=params,
        timeout=30,
    )

    data = response.json()

    if data["status"] != "OK" or not data["results"]:
        return None
    result = data["results"][0]
    loc = result["geometry"]["location"]

    detail = {
        "country": "INDIA",
        "country_iso_code": "IN",
        "city": "",
        "pincode": pincode,
        "state": "",
    }

    for comp in result.get("address_components", []):
        types = comp.get("types", [])

        if "locality" in types or "sublocality" in types:
            detail["city"] = comp["long_name"]

        elif "administrative_area_level_1" in types:
            detail["state"] = comp["long_name"]

        elif "country" in types:
            detail["country"] = comp["long_name"]
            detail["country_iso_code"] = comp["short_name"]

        elif "postal_code" in types:
            detail["pincode"] = comp["long_name"]

    return {
        "latitude": str(loc["lat"]),
        "longitude": str(loc["lng"]),
        **detail,
    }


def get_pincode_serviceability(location):
    url = (
        "https://www.jiomart.com/api/service/application/logistics/v1.0/pincode/"
        + location["pincode"]
    )

    headers = get_jiomart_headers(location)

    res = requests.get(
        url,
        headers=headers,
        timeout=30,
    )

    response = res.json()

    data = response.get("data")[0]

    parents = data.get("parents")

    cords = []

    for cord in parents:
        name = cord.get("name")
        sub_type = cord.get("sub_type")

        cords.append({sub_type: name})

    country_code = data.get("meta_code", {}).get(
        "country_code",
        "",
    )

    return cords, country_code


def get_pincode_delivery_promise(data, location):
    url = (
        "https://www.jiomart.com/api/service/application/logistics/v1.0/"
        "delivery-promise"
    )

    headers = get_jiomart_headers(data)

    res = requests.get(
        url,
        headers=headers,
        timeout=30,
    )

    response = res.json()

    store_ids = response.get("query_params", {}).get("store_ids", [])

    polygon_ids = []

    for item in response.get("items", []):
        for journey in item.get("journey_wise_promise", []):
            polygon_id = journey.get("meta", {}).get("polygon_id")

            if polygon_id:
                polygon_ids.append(polygon_id)

    if not response.get("items"):
        data["country"] = location["country"]
        data["state"] = location["state"]
        data["city"] = location["city"]

    return store_ids, polygon_ids


if __name__ == "__main__":
    create_location_table()
    pincodes = get_pending_pincodes()

    for pincode in pincodes:

        try:
            location = get_location_details(pincode)

            if not location:
                print(f"Google location failed: {pincode}")
                continue

            jiomart_data, country_code = get_pincode_serviceability(location)

            if not jiomart_data:
                print(f"Serviceability lookup failed: {pincode}")
                continue

            jiomart_data = {
                key: value for item in jiomart_data for key, value in item.items()
            }

            data = {
                "pincode": pincode,
                **jiomart_data,
                "country_iso_code": country_code,
                "latitude": location["latitude"],
                "longitude": location["longitude"],
            }

            store_ids, polygon_ids = get_pincode_delivery_promise(
                data,
                location,
            )

            save_location(
                {
                    "latitude": location.get("latitude", ""),
                    "longitude": location.get("longitude", ""),
                    "country": location.get("country", ""),
                    "country_iso_code": location.get("country_iso_code", ""),
                    "city": location.get("city", ""),
                    "pincode": pincode,
                    "state": location.get("state", ""),
                    "store_ids": json.dumps(store_ids),
                    "polygon_id": json.dumps(polygon_ids),
                }
            )
            update_pincode_status(pincode, "completed")

            print(f"Saved: {pincode}")

        except Exception as e:
            update_pincode_status(pincode, "failed")
            print(f"Error for {pincode}: {e}")
