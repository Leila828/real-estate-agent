"""
FIXED Property Finder API with CORRECT filter handling.

Key fix: PropertyFinder uses bdr[] for bedrooms, not bf/bt
"""
import requests
import re
import json
from urllib.parse import urlencode, quote

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def search_location(query: str):
    """Search for location ID using PropertyFinder location API"""
    url = "https://www.propertyfinder.ae/api/pwa/locations"
    params = {"locale": "en", "filters.name": query, "pagination.limit": 20}

    try:
        res = requests.get(url, params=params, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        res.raise_for_status()
        data = res.json()

        # Extract location ID from response
        if isinstance(data, dict):
            data_obj = data.get("data", {})
            if isinstance(data_obj, dict):
                attrs = data_obj.get("attributes", [])
                if isinstance(attrs, list) and attrs:
                    return attrs[0].get("id"), attrs[0].get("name")
    except Exception as e:
        print(f"⚠️ Error searching location: {e}")

    return None, None


def build_search_url(filters: dict):
    """
    Build the CORRECT PropertyFinder search URL with proper parameter formatting.

    CRITICAL: PropertyFinder uses these EXACT parameters:
    - c: category (1=buy, 2=rent)
    - t: property type ID
    - l: location ID
    - bdr[]: bedroom array (MUST be array format, e.g., bdr[]=5)
    - pt: price to (max price)
    - pf: price from (min price)
    - fu: furnished (0=any, 1=furnished, 2=unfurnished)
    - ob: order by (mr=most recent, pa=price asc, pd=price desc)
    """

    base_url = "https://www.propertyfinder.ae/en/search"

    # Build parameters manually to control exact format
    params = []

    # Category (buy/rent)
    purpose = filters.get("purpose", "sale")
    params.append(f"c={'1' if purpose == 'sale' else '2'}")

    # Property type mapping
    property_type_map = {
        "villa": "35",
        "apartment": "1",
        "townhouse": "22",
        "penthouse": "20",
        "compound": "17",
        "duplex": "18",
        "full floor": "23",
        "half floor": "24",
        "whole building": "31"
    }

    if "property_type" in filters and filters["property_type"]:
        pt = str(filters["property_type"]).lower().strip()
        if pt in property_type_map:
            params.append(f"t={property_type_map[pt]}")

    # Location
    if "location_id" in filters and filters["location_id"]:
        params.append(f"l={filters['location_id']}")

    # CRITICAL FIX: Bedrooms as ARRAY parameter
    # PropertyFinder expects: bdr[]=5 NOT bf=5&bt=5
    if "beds" in filters and filters["beds"]:
        beds_value = filters["beds"]
        # Handle if it's a list or single value
        if isinstance(beds_value, list):
            for bed in beds_value:
                if bed:
                    params.append(f"bdr[]={bed}")
        else:
            # Single value - still use array format
            params.append(f"bdr[]={beds_value}")

    # Price range
    if "min_price" in filters and filters["min_price"]:
        params.append(f"pf={filters['min_price']}")

    if "max_price" in filters and filters["max_price"]:
        # Ensure it's formatted as integer (no .0)
        max_price = filters['max_price']
        if isinstance(max_price, float):
            max_price = int(max_price)
        params.append(f"pt={max_price}")

    # Bathrooms (if needed)
    if "baths" in filters and filters["baths"]:
        baths_value = filters["baths"]
        if isinstance(baths_value, list):
            for bath in baths_value:
                if bath:
                    params.append(f"bath[]={bath}")
        else:
            params.append(f"bath[]={baths_value}")

    # Furnished
    if "furnished" in filters:
        fu_map = {"any": "0", "furnished": "1", "unfurnished": "2"}
        fu_val = str(filters["furnished"]).lower()
        params.append(f"fu={fu_map.get(fu_val, '0')}")
    else:
        params.append("fu=0")  # Default to any

    # Sort order
    sort = filters.get("sort", "mr")
    params.append(f"ob={sort}")

    # Build final URL
    url = f"{base_url}?{'&'.join(params)}"
    return url


def fetch_listings_from_search_page(url: str):
    """
    Fetch listings by scraping the search page HTML and extracting
    the __NEXT_DATA__ JSON which contains all property data.
    """
    print(f"🔗 Fetching: {url}")

    try:
        res = requests.get(url, headers=HEADERS, timeout=15)
        res.raise_for_status()
        html = res.text
    except Exception as e:
        print(f"❌ Failed to fetch page: {e}")
        return []

    # Extract the JSON data from __NEXT_DATA__ script tag
    match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html, re.S)
    if not match:
        print("❌ Could not find __NEXT_DATA__ in HTML")
        return []

    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError as e:
        print(f"❌ Failed to parse JSON: {e}")
        return []

    # Navigate to listings
    page_props = data.get("props", {}).get("pageProps", {})
    search_result = page_props.get("searchResult", {})
    listings = search_result.get("listings", [])

    print(f"✅ Found {len(listings)} listings in HTML")

    # Map to our schema
    mapped_results = []
    for listing in listings:
        if listing.get("listing_type") == "property":
            prop = listing.get("property", {})
            if not prop:
                continue

            # Extract images
            images = [img.get("medium") for img in prop.get("images", []) if img.get("medium")]

            # Extract contact info
            mobile = None
            whatsapp = None
            for contact in prop.get("contact_options", []):
                if contact.get("type") == "phone":
                    mobile = contact.get("value")
                elif contact.get("type") == "whatsapp":
                    whatsapp = contact.get("value")

            mapped_results.append({
                "id": prop.get("id"),
                "title": prop.get("title"),
                "price": prop.get("price", {}).get("value"),
                "area": prop.get("size", {}).get("value"),
                "rooms": prop.get("bedrooms_value"),
                "baths": prop.get("bathrooms_value"),
                "purpose": prop.get("offering_type"),
                "completion_status": prop.get("completion_status"),
                "latitude": prop.get("location", {}).get("coordinates", {}).get("lat"),
                "longitude": prop.get("location", {}).get("coordinates", {}).get("lon"),
                "location_name": prop.get("location", {}).get("full_name"),
                "cover_photo_url": images[0] if images else None,
                "all_image_urls": images,
                "agency_name": prop.get("broker", {}).get("name"),
                "contact_name": prop.get("agent", {}).get("name"),
                "mobile_number": mobile,
                "whatsapp_number": whatsapp,
            })

    return mapped_results


def property_finder_search(search_filters: dict):
    """
    Main search function with improved error handling and filtering.
    """
    filters = search_filters.get('filters', {})
    query = filters.get("location_query", filters.get("query", "dubai"))

    # Get location ID
    print(f"\n🔍 Searching for location: '{query}'")
    location_id, location_name = search_location(query)

    if location_id:
        print(f"✅ Found: {location_name} (ID: {location_id})")
        filters["location_id"] = location_id
    else:
        print(f"⚠️ Could not find location '{query}', searching without location filter")

    # Build search URL with correct parameters
    search_url = build_search_url(filters)
    print(f"\n🔍 Search URL: {search_url}\n")

    # Fetch listings from HTML
    results = fetch_listings_from_search_page(search_url)

    print(f"\n🎯 Total results from API: {len(results)}")

    # Apply client-side filters for safety (belt and suspenders approach)
    original_count = len(results)

    # Price filtering
    if "min_price" in filters and filters["min_price"]:
        min_price = int(filters["min_price"])
        before = len(results)
        results = [r for r in results if r.get("price") and r["price"] >= min_price]
        if before != len(results):
            print(f"💰 Min price filter ({min_price:,} AED): {before} → {len(results)}")

    if "max_price" in filters and filters["max_price"]:
        max_price = int(filters["max_price"])
        before = len(results)
        results = [r for r in results if r.get("price") and r["price"] <= max_price]
        if before != len(results):
            print(f"💰 Max price filter ({max_price:,} AED): {before} → {len(results)}")

    # CRITICAL: Exact bedroom match (client-side verification)
    if "beds" in filters and filters["beds"]:
        target_beds = filters["beds"]
        # Handle if it's a list (take first value) or single value
        if isinstance(target_beds, list):
            target_beds = target_beds[0] if target_beds else None

        if target_beds:
            target_beds = int(target_beds)
            before = len(results)
            results = [r for r in results if r.get("rooms") == target_beds]
            if before != len(results):
                print(f"🛏️ Bedroom filter (exactly {target_beds}): {before} → {len(results)}")

    # Bathroom filtering
    if "baths" in filters and filters["baths"]:
        target_baths = filters["baths"]
        if isinstance(target_baths, list):
            target_baths = target_baths[0] if target_baths else None

        if target_baths:
            target_baths = int(target_baths)
            before = len(results)
            results = [r for r in results if r.get("baths") and r["baths"] >= target_baths]
            if before != len(results):
                print(f"🚿 Bathroom filter (min {target_baths}): {before} → {len(results)}")

    if len(results) != original_count:
        print(f"\n📊 Final results after all filters: {len(results)}")

    return results