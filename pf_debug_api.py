from flask import Flask, request, jsonify, send_from_directory
import os
from dotenv import load_dotenv

#import property_finder as pf
import property_finder_v2 as pf
import test_prop as tp
import google.generativeai as genai
from googleapiclient.discovery import build
from google.generativeai import protos  # Import protos for clean use below
import traceback  # Ensure traceback is imported for error logging

# --- CRITICAL CONFIGURATION START ---
# 1. Load environment variables from .env file immediately
load_dotenv()

# 2. Check for and configure the Gemini API key immediately
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
if not GEMINI_API_KEY:
    # Print an error and exit if the key is missing before the app starts
    raise EnvironmentError("GEMINI_API_KEY not set. Check your .env file or environment variables.")
else:
    # Configure the client once at the start
    genai.configure(api_key=GEMINI_API_KEY)
    print("Gemini API configured successfully.")

# 3. Check for Google Search Keys
GOOGLE_SEARCH_API_KEY = os.environ.get("GOOGLE_SEARCH_API_KEY")
GOOGLE_CSE_ID = os.environ.get("GOOGLE_CSE_ID")
# --- CRITICAL CONFIGURATION END ---


app = Flask(__name__)


@app.after_request
def after_request(response):
    """Add CORS headers to all responses"""
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response


@app.route("/")
def index():
    """Serve the HTML test interface"""
    return send_from_directory(os.path.dirname(os.path.abspath(__file__)), 'pf_web_test.html')


@app.get('/favicon.ico')
def favicon():
    return ('', 204)


@app.get('/.well-known/appspecific/com.chrome.devtools.json')
def chrome_devtools_probe():
    return ('', 204)


@app.get("/pf/locations")
def pf_locations():
    """Lookup PF location suggestions for a free-text query."""
    query = request.args.get("query", "").strip()
    if not query:
        return jsonify({"error": "query is required"}), 400
    try:
        data = pf.search_location(query)
        return jsonify({
            "input": {"query": query},
            "raw": data,
            "attributes": data.get("data", {}).get("attributes", [])
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.post("/pf/build-id")
def pf_build_id():
    """Resolve PF buildId for a minimal set of filters."""
    body = request.get_json(silent=True) or {}
    filters = body.get("filters", {})
    try:
        build_id = pf.initialise(filters)
        return jsonify({
            "input": {"filters": filters},
            "build_id": build_id
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.post("/pf/listings")
def pf_listings():
    """Fetch PF listings directly using filters and an optional build_id."""
    body = request.get_json(silent=True) or {}
    filters = body.get("filters", {})
    build_id = body.get("build_id")
    try:
        if not build_id:
            build_id = pf.initialise(filters)
        listings = pf.fetch_propertyfinder_listings(filters, build_id)
        return jsonify({
            "input": {"filters": filters, "build_id": build_id},
            "count": len(listings),
            "listings": listings
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.post("/pf/search")
def pf_search():
    """Run the full PF search pipeline (with caching)."""
    body = request.get_json(silent=True) or {}
    filters = body.get("filters", {})
    try:
        with tp.app.app_context():
            results = tp.search_properties(filters)
        results = _filter_listings_by_constraints(results, filters)
        return jsonify({
            "input": body,
            "count": len(results),
            "listings": results
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def google_search_tool(query: str):
    """Searches Google for reviews or information about a location."""
    print(f"Tool: google_search_tool, Query: {query}")
    try:
        if not GOOGLE_SEARCH_API_KEY or not GOOGLE_CSE_ID:
            return {"status": "error", "message": "GOOGLE_SEARCH_API_KEY or GOOGLE_CSE_ID not set"}

        # Use the globally configured keys
        service = build("customsearch", "v1", developerKey=GOOGLE_SEARCH_API_KEY)
        res = service.cse().list(q=query, cx=GOOGLE_CSE_ID, num=3).execute()

        snippets = [
            {"snippet": item["snippet"], "source": item["link"]}
            for item in res.get("items", [])
        ]

        if not snippets:
            return {"status": "error", "message": "No Google search results found."}

        return {"status": "success", "results": snippets}

    except Exception as e:
        print(f"Error in google_search_tool: {e}")
        return {"status": "error", "message": str(e)}


def property_search_tool(filters: dict):
    """Searches Property Finder for listings using the database cache."""
    print(f"\n{'=' * 80}")
    print(f"[PROPERTY_SEARCH_TOOL] Called with filters: {filters}")
    print(f"{'=' * 80}\n")

    normalized_filters = filters.copy()

    # Gemini sends "location" but tp.search_properties expects "query"
    if 'location' in normalized_filters:
        normalized_filters['query'] = normalized_filters.pop('location')
    if 'location_query' in normalized_filters:
        normalized_filters['query'] = normalized_filters.pop('location_query')

    # Gemini sends "beds" - convert to string
    if 'beds' in normalized_filters and normalized_filters['beds'] is not None:
        val = normalized_filters['beds']
        normalized_filters['beds'] = str(int(val))

    print(f"[PROPERTY_SEARCH_TOOL] Normalized filters: {normalized_filters}\n")

    try:
        with tp.app.app_context():
            print(f"[PROPERTY_SEARCH_TOOL] Calling tp.search_properties()...\n")
            results = tp.search_properties(normalized_filters)

        print(f"[PROPERTY_SEARCH_TOOL] Got {len(results)} results from tp.search_properties()\n")

        # Apply client-side filtering
        print(f"[PROPERTY_SEARCH_TOOL] Applying client-side filtering...\n")
        filtered_results = _filter_listings_by_constraints(results, normalized_filters)

        print(f"[PROPERTY_SEARCH_TOOL] After filtering: {len(filtered_results)} results\n")

        return {
            "status": "success",
            "count": len(filtered_results),
            "listings": filtered_results
        }
    except Exception as e:
        print(f"[PROPERTY_SEARCH_TOOL] Error: {e}")
        traceback.print_exc()
        return {"status": "error", "message": str(e)}


def _filter_listings_by_constraints(listings, constraints):
    """Apply client-side filtering to enforce min/max price and exact bedroom match."""
    if not isinstance(listings, list):
        print("[FILTER] Input is not a list, returning empty")
        return []

    min_price = constraints.get("min_price")
    max_price = constraints.get("max_price")
    beds = constraints.get("beds")
    purpose = (constraints.get("purpose") or '').strip().lower()

    print(f"\n{'=' * 80}")
    print(f"[FILTER] Starting with {len(listings)} listings")
    print(f"[FILTER] Constraints applied:")
    print(f"  - min_price: {min_price}")
    print(f"  - max_price: {max_price}")
    print(f"  - beds: {beds}")
    print(f"  - purpose: {purpose}")
    print(f"{'=' * 80}\n")

    filtered = []
    skipped = {
        "price_too_low": [],
        "price_too_high": [],
        "beds_mismatch": [],
        "purpose_mismatch": [],
        "passed": []
    }

    for idx, p in enumerate(listings):
        price = p.get("price")
        rooms = p.get("rooms")
        p_purpose = (p.get("purpose") or '').strip().lower()
        property_id = p.get("id", "unknown")

        # Price filtering - min
        if min_price is not None and price is not None:
            try:
                if price < int(min_price):
                    skipped["price_too_low"].append(property_id)
                    continue
            except (ValueError, TypeError):
                pass

        # Price filtering - max
        if max_price is not None and price is not None:
            try:
                if price > int(max_price):
                    skipped["price_too_high"].append(property_id)
                    continue
            except (ValueError, TypeError):
                pass

        # CRITICAL FIX: Exact bedroom match (not minimum, EXACT)
        if beds is not None and rooms is not None:
            try:
                beds_int = int(beds)
                rooms_int = int(rooms)
                if rooms_int != beds_int:
                    skipped["beds_mismatch"].append(f"{property_id}({rooms_int}bed)")
                    continue
            except (ValueError, TypeError):
                pass

        # Purpose filtering
        if purpose and p_purpose:
            if purpose == 'sale' and 'sale' not in p_purpose:
                skipped["purpose_mismatch"].append(property_id)
                continue
            if purpose == 'rent' and 'rent' not in p_purpose:
                skipped["purpose_mismatch"].append(property_id)
                continue

        filtered.append(p)
        skipped["passed"].append(property_id)

    print(f"[FILTER] BREAKDOWN:")
    print(f"  ✅ PASSED filter: {len(skipped['passed'])} properties")
    if skipped['price_too_low']:
        print(f"  ❌ Price too low: {len(skipped['price_too_low'])} - {skipped['price_too_low'][:3]}")
    if skipped['price_too_high']:
        print(f"  ❌ Price too high: {len(skipped['price_too_high'])} - {skipped['price_too_high'][:3]}")
    if skipped['beds_mismatch']:
        print(f"  ❌ Bedroom mismatch: {len(skipped['beds_mismatch'])} - {skipped['beds_mismatch'][:3]}")
    if skipped['purpose_mismatch']:
        print(f"  ❌ Purpose mismatch: {len(skipped['purpose_mismatch'])} - {skipped['purpose_mismatch'][:3]}")

    print(f"\n[FILTER] FINAL RESULT: {len(filtered)} properties passed all filters\n")
    print(f"{'=' * 80}\n")

    return filtered


@app.post("/api/gemini_search")
def gemini_search():
    """AI-powered search using Gemini with MANUAL Tool Calling."""
    try:
        # genai is configured globally, no need to check or configure here again.
        if genai is None:
            return jsonify({"error": "Gemini SDK not installed"}), 500

        data = request.get_json(silent=True) or {}
        query = (data.get('query') or '').strip()
        if not query:
            return jsonify({"error": "Query is required"}), 400

        # Define tools using protos
        tools = [
            protos.Tool(
                function_declarations=[
                    protos.FunctionDeclaration(
                        name="property_search_tool",
                        description="Search for properties on Property Finder. Use this when user wants to find villas, apartments, or other properties.",
                        parameters=protos.Schema(
                            type_=protos.Type.OBJECT,
                            properties={
                                "location": protos.Schema(type_=protos.Type.STRING,
                                                          description="Location/area to search"),
                                "max_price": protos.Schema(type_=protos.Type.INTEGER,
                                                           description="Maximum price in AED"),
                                "min_price": protos.Schema(type_=protos.Type.INTEGER,
                                                           description="Minimum price in AED"),
                                "beds": protos.Schema(type_=protos.Type.INTEGER,
                                                      description="Minimum number of bedrooms"),
                                "property_type": protos.Schema(type_=protos.Type.STRING,
                                                               description="Property type: villa, apartment, townhouse, penthouse, etc"),
                                "purpose": protos.Schema(type_=protos.Type.STRING,
                                                         description="Property listing type: 'sale' or 'rent'")
                            },
                            required=["location"]
                        )
                    )
                ]
            ),
            protos.Tool(
                function_declarations=[
                    protos.FunctionDeclaration(
                        name="google_search_tool",
                        description="Search Google for information, reviews, or general knowledge about locations.",
                        parameters=protos.Schema(
                            type_=protos.Type.OBJECT,
                            properties={
                                "query": protos.Schema(type_=protos.Type.STRING, description="Search query")
                            },
                            required=["query"]
                        )
                    )
                ]
            )
        ]

        model = genai.GenerativeModel(
            model_name="models/gemini-2.5-pro",
            system_instruction=(
                "You are an expert UAE real estate agent AI assistant. "
                "CRITICAL INSTRUCTIONS:\n"
                "1. ALWAYS parse location names FIRST and EXACTLY from user query:\n"
                "   - 'Victory Heights' → use as location\n"
                "   - 'JBR' → use as location\n"
                "   - 'Palm Jumeirah' → use as location\n"
                "   - 'Arabian Ranches' → use as location\n"
                "2. Extract price constraints:\n"
                "   - 'under 5M' → max_price: 5000000\n"
                "   - 'above 2M' → min_price: 2000000\n"
                "   - '2M to 4M' → min_price: 2000000, max_price: 4000000\n"
                "3. Extract property type:\n"
                "   - 'villa' → property_type: 'villa'\n"
                "   - 'apartment' → property_type: 'apartment'\n"
                "4. When users search for properties, ALWAYS use 'property_search_tool' with:\n"
                "   - location: the exact location name from query\n"
                "   - max_price/min_price: from price constraints\n"
                "   - beds: number of bedrooms (if specified)\n"
                "   - property_type: type of property (if mentioned)\n"
                "   - purpose: 'sale' or 'rent' (default to 'sale')\n"
                "5. For location info/reviews, use 'google_search_tool'\n"
                "6. After tool results, provide a natural, helpful response with property details."
            ),
            tools=tools
        )

        chat = model.start_chat(enable_automatic_function_calling=False)

        print(f"Sending query to Gemini: {query}")
        response = chat.send_message(query)
        print(f"Initial response received")

        tool_calls_made = []
        final_response = ""
        max_iterations = 5
        iteration = 0

        # MANUAL tool calling loop
        while iteration < max_iterations:
            iteration += 1
            print(f"Iteration {iteration}: Checking for function calls")

            if not response.candidates or not response.candidates[0].content.parts:
                print("No candidates or parts found, breaking loop")
                break

            last_part = response.candidates[0].content.parts[-1]
            print(f"Last part type: {type(last_part)}")

            # Check if there's a function call
            if hasattr(last_part, 'function_call') and last_part.function_call:
                fn_call = last_part.function_call
                fn_name = fn_call.name
                fn_args = dict(fn_call.args)

                print(f"Gemini called: {fn_name} with args: {fn_args}")

                # Execute the appropriate tool
                if fn_name == "property_search_tool":
                    fn_result = property_search_tool(fn_args)
                elif fn_name == "google_search_tool":
                    fn_result = google_search_tool(fn_args.get("query", ""))
                else:
                    fn_result = {"error": f"Unknown tool: {fn_name}"}

                print(f"Tool result: {fn_result}")

                tool_calls_made.append({
                    "tool_name": fn_name,
                    "args": fn_args,
                    "result": fn_result
                })

                # Send tool result back to Gemini
                try:
                    response = chat.send_message(
                        genai.protos.Content(
                            parts=[
                                genai.protos.Part(
                                    function_response=genai.protos.FunctionResponse(
                                        name=fn_name,
                                        response=fn_result
                                    )
                                )
                            ]
                        )
                    )
                    print(f"Tool response sent")
                except Exception as tool_err:
                    print(f"Error sending tool response: {tool_err}")
                    traceback.print_exc()
                    raise
            else:
                # No function call, extract text
                print("No function call found, extracting final response")
                try:
                    final_response = response.text
                except:
                    final_response = ""
                    for part in response.candidates[0].content.parts:
                        if hasattr(part, 'text') and part.text:
                            final_response += part.text
                break

        # Extract listings from tool results
        listings = []
        for tool_call in tool_calls_made:
            if tool_call["tool_name"] == "property_search_tool":
                tool_result = tool_call.get("result", {})
                if tool_result.get("status") == "success":
                    listings.extend(tool_result.get("listings", []))

        return jsonify({
            "success": True,
            "engine": "gemini_agent",
            "query": query,
            "ai_response": final_response,
            "tool_calls_made": tool_calls_made,
            "listings": listings,
            "result": {
                "listings": listings
            }
        })

    except Exception as e:
        print(f"Error in Gemini agent: {e}")
        tb = traceback.format_exc()
        print(tb)
        return jsonify({
            "error": "Gemini agent search failed",
            "details": str(e),
            "traceback": tb
        }), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5055, debug=True)