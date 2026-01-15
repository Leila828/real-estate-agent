"""
Test the location lookup API to understand its response structure
"""
import property_finder as pf
import json

test_queries = ["Victory Heights", "Dubai Marina", "Palm Jumeirah", "JBR"]

for query in test_queries:
    print(f"\n{'=' * 80}")
    print(f"🔍 Testing location lookup: '{query}'")
    print(f"{'=' * 80}")

    result = pf.search_location(query)

    print(f"\nResponse type: {type(result)}")

    if isinstance(result, dict):
        print(f"Keys: {list(result.keys())}")

        # Pretty print the response
        print(f"\nFull response:")
        print(json.dumps(result, indent=2, default=str)[:1000])  # First 1000 chars

        # Try to extract location_id
        data = result.get("data")
        if isinstance(data, list) and data:
            print(f"\n✅ Found {len(data)} locations:")
            for i, item in enumerate(data[:3], 1):  # Show first 3
                loc_id = item.get("id")
                loc_name = item.get("name")
                loc_type = item.get("type")
                print(f"  {i}. ID: {loc_id} | Name: {loc_name} | Type: {loc_type}")
        elif isinstance(data, dict):
            print(f"\nData is dict with keys: {data.keys()}")
            attrs = data.get("attributes")
            if attrs:
                print(f"Attributes: {attrs[:500]}")
        else:
            print(f"\n❌ Unexpected data structure: {type(data)}")
    else:
        print(f"❌ Response is not a dict: {result}")

print(f"\n{'=' * 80}")
print("Testing complete!")
print(f"{'=' * 80}")