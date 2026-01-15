"""
Test the new hybrid approach that uses HTML scraping
"""
import property_finder_v2 as pf

print("="*80)
print("🔍 TESTING: Victory Heights 5-Bedroom Villas under 10M AED (V2)")
print("="*80)

filters = {
    "filters": {
        "location_query": "Victory Heights",
        "purpose": "sale",
        "property_type": "villa",
        "beds": "5",
        "max_price": 10000000
    }
}

results = pf.property_finder_search(filters)

print(f"\n{'='*80}")
print(f"🎯 FINAL RESULTS: {len(results)} properties")
print(f"{'='*80}\n")

for i, prop in enumerate(results, 1):
    print(f"{i}. {prop['title']}")
    print(f"   💰 AED {prop['price']:,}")
    print(f"   📍 {prop['location_name']}")
    print(f"   🛏️  {prop['rooms']} BR • {prop['baths']} BA • {prop['area']} sqft")
    print()