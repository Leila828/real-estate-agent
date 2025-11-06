"""
SIMPLE DEBUG - Find where property_type is lost
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import test_prop as tp

print("\n" + "="*80)
print("TEST 1: Search WITHOUT property_type")
print("="*80)

filters_no_type = {
    'query': 'Victory Heights',
    'purpose': 'sale',
    'beds': '5',
    'max_price': 10000000
}

print(f"\nInput filters: {filters_no_type}")

with tp.app.app_context():
    results_no_type = tp.search_properties(filters_no_type)

print(f"\nResults: {len(results_no_type)} properties")
print("\nFirst 5:")
for p in results_no_type[:5]:
    print(f"  - {p.get('rooms')} bed - AED {p.get('price'):,} - {p.get('title')[:50]}")

print("\n" + "="*80)
print("TEST 2: Search WITH property_type='villa'")
print("="*80)

filters_with_type = {
    'query': 'Victory Heights',
    'purpose': 'sale',
    'property_type': 'villa',
    'beds': '5',
    'max_price': 10000000
}

print(f"\nInput filters: {filters_with_type}")

# Clear cache first
import database
with tp.app.app_context():
    db = database.get_db()
    cursor = db.cursor()
    cursor.execute("DELETE FROM cached_queries")
    cursor.execute("DELETE FROM cached_properties")
    db.commit()
    print("\n[CLEARED CACHE]\n")
    
    results_with_type = tp.search_properties(filters_with_type)

print(f"\nResults: {len(results_with_type)} properties")
print("\nFirst 5:")
for p in results_with_type[:5]:
    print(f"  - {p.get('rooms')} bed - AED {p.get('price'):,} - {p.get('title')[:50]}")

print("\n" + "="*80)
print("ANALYSIS")
print("="*80)

if len(results_with_type) == len(results_no_type):
    print("\n🔴 BUG CONFIRMED: property_type is NOT working!")
    print(f"   Same results: {len(results_no_type)} (without type) vs {len(results_with_type)} (with type)")
    print("\n   This means property_type is being IGNORED or REMOVED somewhere")
    
    print("\n   THE BUG IS IN ONE OF THESE PLACES:")
    print("   1. test_prop.py - cleaned_filters is removing property_type")
    print("   2. property_finder.py - property_type is not being used")
    print("   3. pf_debug_api.py - property_type is being popped")
else:
    print(f"\n✅ GOOD: property_type IS working!")
    print(f"   Without: {len(results_no_type)} results")
    print(f"   With villa: {len(results_with_type)} results")

print("\n" + "="*80)
print("CHECKING THE CODE PATH")
print("="*80)

print("\n1. In test_prop.py search_properties():")
print("   Line: cleaned_filters = {k: v for k, v in filters.items() if v and v != ['']}")
print("   This removes 'property_type' if it's missing/None")
print("\n   Line: if 'query' in cleaned_filters:")
print("        cleaned_filters['location_query'] = cleaned_filters.pop('query')")
print("   This converts 'query' → 'location_query'")
print("\n   ⚠️  Does it pass property_type to property_finder.property_finder_search()?")
print("   CHECK: search_params = {'filters': cleaned_filters}")
print("        properties = property_finder.property_finder_search(search_params)")

print("\n2. In property_finder.py property_finder_search():")
print("   Line: inner_filters = search_filters.get('filters', {})")
print("   ⚠️  Is property_type in inner_filters?")

print("\n3. In property_finder.py fetch_propertyfinder_listings():")
print("   Line: if key == 'property_type':")
print("         pt_id = PROPERTY_TYPE_MAP.get(value.lower())")
print("         if pt_id:")
print("             api_params['t'] = pt_id")
print("   ⚠️  This should convert property_type → API parameter 't'")

print("\n4. Check FILTERS_MAP in property_finder.py:")
print("   Does it have 'property_type' in FILTERS_MAP?")
print("   If yes, it might be double-processed\n")