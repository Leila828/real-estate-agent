import io
import math
import requests
from urllib.parse import urlencode
from flask import Flask, request, jsonify, send_file, abort, render_template

import database
import property_finder

import sqlite3
from datetime import datetime, timedelta

# --- Flask App Configuration ---
app = Flask(__name__)
app.config['DATABASE'] = 'bayut_properties.db'
app.config['DEBUG'] = True

database.init_app(app)

# --- Database Initialization (inside app context) ---
with app.app_context():
    database.init_db()


# --- Core Search Logic (Property Finder) ---
def search_properties(filters, page=1, limit=50):
    """
    Fetches property listings using the Property Finder API and caches them.
    """
    print(f"\n{'=' * 80}")
    print(f"[SEARCH] search_properties called with filters: {filters}")
    print(f"{'=' * 80}\n")

    # 1. Prepare filters for the cache key.
    #    Remove empty or invalid filters before creating the cache key string.
    #    BUT KEEP property_type, beds, purpose, and other important filters
    cleaned_filters = {k: v for k, v in filters.items() if v and v != ['']}

    # 2. Add 'page' and 'limit' to the cache key to ensure unique cache entries for different paginations.
    cleaned_filters['page'] = page
    cleaned_filters['limit'] = limit

    # 3. Create a unique query string for caching.
    #    'doseq=True' is crucial for handling lists like beds=['3', '4'].
    sorted_filters = sorted(cleaned_filters.items())
    query_string = urlencode(sorted_filters, doseq=True)

    print(f"[SEARCH] Cache key: {query_string}\n")

    # 4. Check the cache.
    query_id = database.find_cached_query(query_string)

    if query_id:
        print(f"[SEARCH] Cache hit for query: {query_string}")
        # Retrieve paginated properties from the cache
        properties_data = database.get_properties_for_query(query_id)

        # Calculate pagination details
        total_properties = len(properties_data)
        start = (page - 1) * limit
        end = start + limit
        paginated_properties = properties_data[start:end]

        print(f"[SEARCH] Returning {len(paginated_properties)} cached properties (page {page})\n")
        return paginated_properties
    else:
        print(f"[SEARCH] Cache miss for query: {query_string}")
        print(f"[SEARCH] Fetching live from Property Finder...\n")

        # 5. Fetch live data from Property Finder.
        # Wrap filters in the expected structure for property_finder_search
        # Convert 'query' to 'location_query' for Property Finder API
        if 'query' in cleaned_filters:
            cleaned_filters['location_query'] = cleaned_filters.pop('query')

        search_params = {"filters": cleaned_filters}

        print(f"[SEARCH] Calling property_finder.property_finder_search with: {search_params}\n")
        properties = property_finder.property_finder_search(search_params)

        print(f"[SEARCH] Got {len(properties)} properties from API\n")

        if properties:
            # 6. Save the live data to the database.
            print(f"[SEARCH] Saving {len(properties)} properties to cache...\n")
            database.save_query_and_properties(query_string, properties)

        # 7. Apply client-side filtering for price
        min_price = cleaned_filters.get('min_price')
        max_price = cleaned_filters.get('max_price')

        if min_price is not None or max_price is not None:
            print(f"[SEARCH] Applying client-side price filter (min: {min_price}, max: {max_price})...")
            filtered_properties = []
            for prop in properties:
                price = prop.get('price')
                if price is not None:
                    # Check against min_price
                    if min_price is not None and price < min_price:
                        continue
                    # Check against max_price
                    if max_price is not None and price > max_price:
                        continue
                    filtered_properties.append(prop)

            print(f"[SEARCH] Filtered properties count: {len(filtered_properties)}\n")
            properties = filtered_properties

        # 8. Return ALL filtered properties (not paginated here - let the caller handle pagination)
        print(f"[SEARCH] Returning all {len(properties)} properties\n")
        return properties


# --- Flask Routes ---
@app.route("/")
def home():
    return render_template("index.html")


@app.route('/api/search', methods=['GET'])
def api_search():
    """
    API endpoint to search for properties using the Property Finder API.
    This replaces the old Bayut API endpoint.
    """
    try:
        filters = {
            "query": request.args.get('query', 'dubai'),
            "purpose": request.args.get('purpose', 'sale'),
            "property_type": request.args.get('property_type', ''),
            "beds": request.args.getlist('beds'),
            "baths": request.args.getlist('baths'),
            "page": request.args.get('page', 1, type=int),
            "sort": request.args.get('sort', 'mr'),
            "min_price": request.args.get('min_price', type=int),
            "max_price": request.args.get('max_price', type=int),
            "min_area": request.args.get('min_area', type=int),
            "max_area": request.args.get('max_area', type=int),
            "listed_within": request.args.get('listed_within', type=int),
            "amenities": request.args.getlist('amenities'),
            "furnished": request.args.get('furnished', type=str)
        }

        results = search_properties(filters)

        if results:
            return jsonify({
                "success": True,
                "listings": results,
                "count": len(results),
            })
        else:
            return jsonify({
                "success": False,
                "message": "No listings found.",
            }), 404

    except Exception as e:
        print(f"Error in API search: {e}")
        return jsonify({
            "success": False,
            "message": f"An error occurred: {str(e)}",
        }), 500


@app.route('/get_image')
def get_image():
    image_url = request.args.get('url')
    allowed_image_prefixes = ['https://www.propertyfinder.ae/property/']
    is_valid_prefix = any(image_url and image_url.startswith(prefix) for prefix in allowed_image_prefixes)
    if not is_valid_prefix:
        return "Invalid image URL", 400
    try:
        response = requests.get(image_url, headers={'Referer': 'https://www.propertyfinder.ae/'}, timeout=10)
        response.raise_for_status()
        content_type = response.headers.get('Content-Type', 'application/octet-stream')
        return send_file(io.BytesIO(response.content), mimetype=content_type)
    except requests.exceptions.Timeout:
        return "Image fetch timed out", 408
    except requests.exceptions.RequestException as e:
        return f"Image not found or forbidden: {e}", 404
    except Exception as e:
        return f"Internal server error: {e}", 500


@app.route('/property/<int:property_id>')
def property_detail(property_id):
    abort(501, description="This function has not been updated for Property Finder properties.")


@app.route('/api/properties/<int:property_id>')
def api_property_detail(property_id):
    """
    Returns a single property's details as a JSON object,
    retrieved from the cache (now populated with PF data).
    """
    db = database.get_db()
    cursor = db.cursor()

    cursor.execute("SELECT * FROM cached_properties WHERE id = ?", (str(property_id),))
    property_row = cursor.fetchone()

    if property_row is None:
        abort(404, description="Property not found in cache.")

    property_dict = dict(property_row)
    if property_dict.get('all_image_urls'):
        property_dict['all_image_urls'] = property_dict['all_image_urls'].split(',')
    else:
        property_dict['all_image_urls'] = []

    return jsonify(property_dict)


@app.route("/map_view")
def map_view():
    lat = request.args.get('lat', type=float)
    lng = request.args.get('lng', type=float)

    if lat is None or lng is None:
        abort(400, "Missing latitude or longitude in the URL.")

    return render_template("map_page.html", lat=lat, lng=lng)


if __name__ == '__main__':
    app.run(debug=True)