"""
Direct test script to debug Victory Heights 5-bedroom villa search
Run this to see exactly what the API returns
"""
import property_finder as pf

print("=" * 80)
print("🔍 TESTING: Victory Heights 5-Bedroom Villas under 10M AED")
print("=" * 80)

# Step 1: Search for location
print("\n📍 Step 1: Finding location ID for 'Victory Heights'...")
locations = pf.search_location("Victory Heights")
print(f"Raw location API response structure: {type(locations)}")
print(f"Location API response keys: {locations.keys() if isinstance(locations, dict) else 'Not a dict'}\n")

location_id = None
location_name = None

if isinstance(locations, dict):
    data_obj = locations.get("data")
    print(f"Data object type: {type(data_obj)}")

    if isinstance(data_obj, dict):
        print(f"Data is a dict: {data_obj.keys()}")
        attrs = data_obj.get("attributes", [])
        if attrs and isinstance(attrs, list):
            print(f"Attributes is a list with {len(attrs)} items")
            first_attr = attrs[0]
            location_id = first_attr.get("id")
            location_name = first_attr.get("name")
            print(f"✅ Found location_id: {location_id} ({location_name})\n")
    elif isinstance(data_obj, list) and data_obj:
        print(f"Data is a list with {len(data_obj)} items")
        first_item = data_obj[0]
        location_id = first_item.get("id")
        location_name = first_item.get("name")
        print(f"✅ Found location_id: {location_id} ({location_name})\n")

if not location_id:
    print("❌ ERROR: Could not find location_id!")
    print("Full response:", locations)
    exit(1)

# Step 2: Get build ID
print("📦 Step 2: Getting build_id...")
filters = {
    "purpose": "sale",
    "property_type": "villa",
    "location_id": location_id,
    "beds": "5",  # 5 bedrooms
}
build_id = pf.initialise(filters)
print(f"✅ Got build_id: {build_id}\n")

# Step 3: Fetch listings with manual pagination
print("=" * 80)
print("📄 Step 3: Fetching listings page by page...")
print("=" * 80)

all_results = []

for page in range(1, 6):  # Test first 5 pages
    print(f"\n{'─' * 60}")
    print(f"📄 PAGE {page}")
    print(f"{'─' * 60}")

    page_filters = filters.copy()
    page_filters["page"] = page

    results = pf.fetch_propertyfinder_listings(page_filters, build_id)

    if not results:
        print(f"❌ Page {page} returned 0 results")
        break

    print(f"✅ Page {page} returned {len(results)} results:")
    for i, prop in enumerate(results, 1):
        print(f"  {i}. {prop['title'][:60]}... | AED {prop['price']:,} | {prop['rooms']}BR")

    all_results.extend(results)

# Apply price filter manually
print("\n" + "=" * 80)
print("💰 Step 4: Applying price filter (under 10M AED)")
print("=" * 80)

max_price = 10_000_000
filtered_results = [p for p in all_results if p['price'] and p['price'] <= max_price]

print(f"\n🎯 FINAL RESULTS: {len(filtered_results)} properties found\n")

for i, prop in enumerate(filtered_results, 1):
    print(f"{i}. {prop['title']}")
    print(f"   💰 AED {prop['price']:,}")
    print(f"   📍 {prop['location_name']}")
    print(f"   🛏️  {prop['rooms']} BR • {prop['baths']} BA • {prop['area']} sqft")
    print()

# Show what was filtered out
filtered_out = [p for p in all_results if not (p['price'] and p['price'] <= max_price)]
if filtered_out:
    print(f"\n❌ {len(filtered_out)} properties filtered out (over 10M):")
    for prop in filtered_out:
        print(f"   - {prop['title'][:50]}... | AED {prop['price']:,}")