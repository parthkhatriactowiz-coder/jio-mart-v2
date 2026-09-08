from utils import clean_text, clean_delivery_date
import json


def extract_product_data(res, pincode):
    top_attrs = res.get("attributes") or {}

    inner = top_attrs.get("attributes")
    attrs = json.loads(inner) if isinstance(inner, str) else (inner or {})

    variants = attrs.get("variants") or {}
    mfg = attrs.get("manufacturer") or {}
    shelf_life = variants.get("shelf_life") or {}

    item_dims_raw = (variants.get("dimensions") or {}).get("item_dimensions") or {}
    item_dimensions = {
        key: dim.get("value")
        for key, dim in item_dims_raw.items()
        if dim and dim.get("value") is not None
    }

    mfg_addresses = mfg.get("manufacturing_addresses") or []
    manufacturer_address = mfg_addresses[0].get("address") if mfg_addresses else None

    stock_list = variants.get("stock") or []
    sold_by = stock_list[0].get("merchant_info", {}).get("name") if stock_list else None

    item_specifications = {
        sub.get("display_string"): clean_text(sub.get("value"))
        for group in (attrs.get("specifications") or [])
        for sub in (group.get("sub_specs") or [])
    }

    shelf_life_str = None
    if shelf_life.get("window") is not None:
        shelf_life_str = (
            f"{shelf_life.get('window')} {shelf_life.get('window_unit')}".strip()
        )

    key_features = [clean_text(f) for f in (attrs.get("key_features") or [])]

    return {
        "product_name": clean_text(res.get("name")),
        "slug": res.get("slug"),
        "size": top_attrs.get("size"),
        "available": top_attrs.get("is_available"),
        "pincode": pincode,
        "quantity": top_attrs.get("qty"),
        "key_features": key_features or None,
        "brand_name": (attrs.get("brand") or {}).get("name"),
        "sold_by": sold_by,
        "origin_countries": variants.get("origin_countries"),
        "manufacturer_name": mfg.get("name"),
        "manufacturer_address": manufacturer_address,
        "product_code": attrs.get("product_code"),
        "shelf_life": shelf_life_str,
        "item_dimensions": item_dimensions or None,
        "item_specifications": item_specifications or None,
        "product_showcase": clean_text(attrs.get("snippet")),
        "disclaimer": clean_text(attrs.get("disclaimers")),
    }


def extract_variant_sizes(res):
    variant_list = []
    for group in res.get("variants") or []:
        for item in group.get("items") or []:
            variant_list.append(
                {
                    "slug": item.get("slug"),
                    "size": clean_text(item.get("value")),
                }
            )
    return variant_list or None


def extract_price_items(res, pincode=None):
    results = []

    for item in res.get("items") or []:
        price = item.get("price") or {}
        delivery = item.get("delivery_promise") or {}
        item_pincode = pincode or item.get("pincode")

        if item.get("error"):
            results.append(
                {
                    "slug": item.get("slug"),
                    "size": item.get("size"),
                    "in_stock": False,
                    "mrp": None,
                    "selling_price": None,
                    "currency_code": None,
                    "currency_symbol": None,
                    "discount": None,
                    "quantity": None,
                    "pincode": item_pincode,
                    "distance_in_meter": None,
                    "is_serviceable": False,
                    "delivery_min": None,
                    "delivery_max": None,
                    "error": item.get("error"),
                }
            )
            continue

        currency_symbol = clean_text(price.get("currency_symbol"))

        results.append(
            {
                "slug": item.get("slug"),
                "size": item.get("size"),
                "in_stock": True,
                "mrp": price.get("marked"),
                "selling_price": price.get("selling"),
                "currency_code": price.get("currency_code"),
                "currency_symbol": currency_symbol,
                "discount": item.get("discount"),
                "quantity": item.get("quantity"),
                "pincode": item_pincode,
                "distance_in_meter": item.get("distance"),
                "is_serviceable": item.get("is_serviceable"),
                "delivery_min": clean_delivery_date(delivery.get("min")),
                "delivery_max": clean_delivery_date(delivery.get("max")),
            }
        )

    return results or None
