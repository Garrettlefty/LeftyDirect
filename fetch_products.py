#!/usr/bin/env python3
"""
LeftyDirect catalog builder.

Pulls left-handed golf club listings from affiliate sources, keeps only
items that explicitly confirm left-hand dexterity, normalizes them into
the schema index.html expects, and writes products.json.

This is a working TEMPLATE, not a finished production script. Two things
you must do before it will pull real data:

  1. Get approved for the affiliate program(s) you want to use, and get
     API credentials from each one. LeftyDirect (or any AI assistant)
     cannot create these accounts for you — see README.md.
  2. Check each API's current docs before relying on this. Field names,
     auth flows, and category/aspect IDs change over time, and this file
     was written from general knowledge of how these APIs work rather
     than a live, verified call against them.

Run locally with:
    pip install -r requirements.txt
    export EBAY_OAUTH_TOKEN=...
    export AMAZON_ACCESS_KEY=... AMAZON_SECRET_KEY=... AMAZON_PARTNER_TAG=...
    python scripts/fetch_products.py

In production this is meant to run on a schedule via
.github/workflows/update-products.yml, with the same variables stored as
GitHub Actions secrets.
"""

import json
import os
import sys
import time
import datetime
import argparse
import requests

OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "..", "products.json")

# Search terms we sweep across every source. Keeping "left" / "lh" in the
# query is not enough on its own -- we still verify dexterity per-item
# below before anything is allowed into the catalog.
SEARCH_TERMS = [
    "left handed golf driver",
    "left handed golf irons",
    "left handed golf hybrid",
    "left handed golf wedge",
    "left handed golf putter",
    "left handed complete golf set",
]

CATEGORY_KEYWORDS = {
    "driver": ["driver"],
    "iron": ["iron", "irons"],
    "hybrid": ["hybrid", "rescue"],
    "wedge": ["wedge"],
    "putter": ["putter"],
    "set": ["complete set", "package set", "box set"],
}


def guess_category(title: str) -> str:
    t = title.lower()
    for cat, keywords in CATEGORY_KEYWORDS.items():
        if any(k in t for k in keywords):
            return cat
    return "iron"  # safe default; review uncategorized items manually


def is_confirmed_left_handed(title: str, item_specifics: dict) -> bool:
    """
    The single most important filter on this whole site: never show a
    club we can't affirmatively confirm is left-handed. Prefer a
    structured field (e.g. eBay's "Dexterity" item specific) over just
    matching the word "left" in a title, since titles can say things like
    "fits right OR left" or "left over stock" (unrelated to handedness).
    """
    dexterity = (item_specifics or {}).get("Dexterity", "").lower()
    if "left" in dexterity:
        return True
    t = title.lower()
    if "right handed" in t or "right-handed" in t or "rh " in t:
        return False
    return "left handed" in t or "left-handed" in t or " lh " in t


# ---------------------------------------------------------------------
# eBay Partner Network (Browse API)
# Docs: https://developer.ebay.com/api-docs/buy/browse/overview.html
# You'll need an OAuth application token and an EPN campaign ID.
# ---------------------------------------------------------------------
def fetch_ebay_listings(oauth_token: str, campaign_id: str) -> list:
    if not oauth_token:
        print("  [ebay] skipped — EBAY_OAUTH_TOKEN not set")
        return []

    results = []
    headers = {
        "Authorization": f"Bearer {oauth_token}",
        "X-EBAY-C-MARKETPLACE-ID": "EBAY_US",
    }
    for term in SEARCH_TERMS:
        try:
            resp = requests.get(
                "https://api.ebay.com/buy/browse/v1/item_summary/search",
                headers=headers,
                params={"q": term, "category_ids": "115280", "limit": 20},
                timeout=15,
            )
            resp.raise_for_status()
            for item in resp.json().get("itemSummaries", []):
                specifics = {
                    a["name"]: a["value"]
                    for a in item.get("additionalProductIdentities", [])
                } if item.get("additionalProductIdentities") else {}
                title = item.get("title", "")
                if not is_confirmed_left_handed(title, specifics):
                    continue
                price = item.get("price", {})
                results.append({
                    "source_id": item.get("itemId"),
                    "title": title,
                    "category": guess_category(title),
                    "price": float(price.get("value", 0)),
                    "currency": price.get("currency", "USD"),
                    "retailer": item.get("seller", {}).get("username", "eBay seller"),
                    # EPN affiliate links are normally built with the Affiliate
                    # API / campaign ID rather than the raw itemWebUrl —
                    # swap this for a real generated tracking link.
                    "affiliate_url": item.get("itemWebUrl", "#"),
                    "image_url": (item.get("image") or {}).get("imageUrl"),
                })
            time.sleep(0.3)  # be polite to the API
        except requests.RequestException as e:
            print(f"  [ebay] request failed for '{term}': {e}")
    return results


# ---------------------------------------------------------------------
# Amazon Product Advertising API 5.0 (SearchItems)
# Docs: https://webservices.amazon.com/paapi5/documentation/
# Requires an approved Amazon Associates account with recent qualifying
# sales, plus access + secret keys and a partner tag.
# Using the official `amazon-paapi` (or `python-amazon-paapi`) package is
# recommended over hand-rolling the AWS4 signing shown here.
# ---------------------------------------------------------------------
def fetch_amazon_listings(access_key: str, secret_key: str, partner_tag: str) -> list:
    if not all([access_key, secret_key, partner_tag]):
        print("  [amazon] skipped — AMAZON_ACCESS_KEY/SECRET_KEY/PARTNER_TAG not set")
        return []

    try:
        from amazon_paapi import AmazonApi
    except ImportError:
        print("  [amazon] skipped — run: pip install python-amazon-paapi")
        return []

    amazon = AmazonApi(access_key, secret_key, partner_tag, "US")
    results = []
    for term in SEARCH_TERMS:
        try:
            search_result = amazon.search_items(keywords=term, search_index="SportingGoods", item_count=10)
            for item in getattr(search_result, "items", []):
                title = item.item_info.title.display_value if item.item_info and item.item_info.title else ""
                features = " ".join(item.item_info.features.display_values) if (
                    item.item_info and item.item_info.features
                ) else ""
                if not is_confirmed_left_handed(title + " " + features, {}):
                    continue
                price = None
                if item.offers and item.offers.listings:
                    price = item.offers.listings[0].price.amount
                results.append({
                    "source_id": item.asin,
                    "title": title,
                    "category": guess_category(title),
                    "price": price or 0,
                    "currency": "USD",
                    "retailer": "Amazon",
                    "affiliate_url": item.detail_page_url,  # already tagged with your partner_tag
                    "image_url": item.images.primary.large.url if item.images and item.images.primary else None,
                })
            time.sleep(1)  # PA-API rate limits are strict, especially for new accounts
        except Exception as e:
            print(f"  [amazon] request failed for '{term}': {e}")
    return results


# ---------------------------------------------------------------------
# Placeholders for the golf-specific retail networks worth adding next.
# Most golf-specific retailers (Golf Galaxy / Dick's, PGA Tour Superstore,
# Worldwide Golf Shops, Rock Bottom Golf, 2nd Swing Golf) run their
# affiliate programs through a network like Impact, Rakuten Advertising,
# CJ Affiliate, ShareASale, or AWIN rather than hosting their own API.
# Once you're approved on a network, that network gives you a product
# feed (usually a CSV/XML file, sometimes an API) you can parse the same
# way as the functions above: normalize -> filter for confirmed
# left-hand dexterity -> append to `results`.
# ---------------------------------------------------------------------
def fetch_network_feed_placeholder(network_name: str) -> list:
    print(f"  [{network_name}] not yet implemented — see comment above this function")
    return []


def normalize(raw_items: list, brand_hint=None) -> list:
    normalized = []
    for item in raw_items:
        brand = brand_hint
        if not brand:
            brand = item["title"].split(" ")[0]
        normalized.append({
            "id": item.get("source_id") or f"gen-{abs(hash(item['title']))}",
            "brand": brand,
            "name": item["title"],
            "category": item["category"],
            "hand": "left",
            "price": round(float(item.get("price") or 0), 2),
            "currency": item.get("currency", "USD"),
            "retailer": item.get("retailer", "Unknown retailer"),
            "affiliate_url": item.get("affiliate_url", "#"),
            "image_url": item.get("image_url"),
            "specs": {},
            "dexterity_verified": True,
            "added_at": datetime.date.today().isoformat(),
        })
    return normalized


def main():
    parser = argparse.ArgumentParser(description="Rebuild LeftyDirect's product feed.")
    parser.add_argument("--out", default=OUTPUT_PATH, help="Where to write products.json")
    parser.add_argument("--dry-run", action="store_true", help="Print results instead of writing the file")
    args = parser.parse_args()

    print("Fetching left-handed listings…")
    raw = []
    raw += fetch_ebay_listings(
        oauth_token=os.environ.get("EBAY_OAUTH_TOKEN"),
        campaign_id=os.environ.get("EBAY_CAMPAIGN_ID"),
    )
    raw += fetch_amazon_listings(
        access_key=os.environ.get("AMAZON_ACCESS_KEY"),
        secret_key=os.environ.get("AMAZON_SECRET_KEY"),
        partner_tag=os.environ.get("AMAZON_PARTNER_TAG"),
    )
    # Add more sources here as you get approved for them:
    # raw += fetch_network_feed_placeholder("Impact")
    # raw += fetch_network_feed_placeholder("Rakuten Advertising")

    if not raw:
        print("No live sources configured — nothing to update. "
              "See README.md to connect your first affiliate program.")
        sys.exit(0)

    products = normalize(raw)

    # De-duplicate by (brand, name, retailer) so the same club from the
    # same retailer doesn't show up twice across search terms.
    seen = set()
    deduped = []
    for p in products:
        key = (p["brand"], p["name"], p["retailer"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(p)

    payload = {
        "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
        "source": "automated",
        "products": deduped,
    }

    if args.dry_run:
        print(json.dumps(payload, indent=2)[:2000], "...")
        print(f"\n{len(deduped)} left-handed products found (dry run, file not written).")
        return

    with open(args.out, "w") as f:
        json.dump(payload, f, indent=2)
    print(f"Wrote {len(deduped)} verified left-handed products to {args.out}")


if __name__ == "__main__":
    main()
