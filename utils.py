from datetime import datetime
import gzip
import hashlib
import json
import os
import unicodedata


def clean_text(text):
    if not text:
        return text
    replacements = {
        "\u2013": "-",
        "\u2014": "-",
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2026": "...",
    }
    for bad, good in replacements.items():
        text = text.replace(bad, good)
    return unicodedata.normalize("NFKC", text)


def extract_variant_size_pairs(res):
    pairs = []
    for group in res.get("variants") or []:
        for item in group.get("items") or []:
            sizes_with_id = item.get("sizes_with_identifer") or []
            size = sizes_with_id[0].get("size") if sizes_with_id else item.get("value")
            pairs.append(
                {
                    "slug": item.get("slug"),
                    "size": size,
                }
            )
    return pairs or None


def clean_delivery_date(date_str):
    if not date_str:
        return None
    try:
        dt = datetime.fromisoformat(str(date_str).replace("Z", "+00:00"))
        if dt.tzinfo is not None:
            dt = dt.astimezone()
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(date_str).replace("T", " ").rstrip("Z")


def serialize_field(val):
    if val is None:
        return None
    if isinstance(val, (dict, list)):
        return json.dumps(val, ensure_ascii=False)
    return str(val)


def save_raw_response_gzip(url, pincode, raw_data, folder="raw_responses_v2"):
    """
    Compresses raw API response payload using gzip and saves to folder.
    Returns SHA256 hash string for database tracking.
    """
    if not raw_data:
        return None
    try:
        os.makedirs(folder, exist_ok=True)
        unique_key = f"{url}|{pincode}"
        file_hash = hashlib.sha256(unique_key.encode("utf-8")).hexdigest()
        filepath = os.path.join(folder, f"{file_hash}.json.gz")
        json_bytes = json.dumps(raw_data, ensure_ascii=False).encode("utf-8")
        with gzip.open(filepath, "wb") as f:
            f.write(json_bytes)
        return file_hash
    except Exception:
        return None
