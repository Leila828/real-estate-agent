# AI-Powered Property Finder Search Engine

This project implements a sophisticated property search engine that leverages an AI agent (Gemini) to interpret natural language queries and a custom web scraper (`property_finder.py`) to fetch and cache real-time property listings from Property Finder.

## 1. System Requirements

The project is built using Python and requires the following:

*   **Python:** Version 3.8+
*   **Database:** SQLite (used for caching, no external setup required)

## 2. Setup and Installation

Follow these steps to set up the project environment.

### 2.1. Clone the Repository

Assuming you have all the project files in a single directory:

```bash
# Ensure all files are in the current directory:
# comprehensive_debug.py, test_prop.py, pf_debug_api.py, property_finder.py, pf_web_test.html, database.py (assumed)
ls
```

### 2.2. Install Dependencies

The project relies on several Python packages, including `Flask`, `requests`, and the Google Gemini SDK.

```bash
pip install Flask requests google-genai
```

*(Note: The `database.py` file is assumed to exist and contain the necessary SQLite functions for caching, as referenced in `test_prop.py` and `comprehensive_debug.py`.)*

## 3. API Key Configuration

The AI agent functionality requires a Google Gemini API key.

### 3.1. Obtain API Key

1.  Go to the Google AI Studio or the Google Cloud Console to generate a **Gemini API Key**.
2.  The key should be set as an environment variable named `GEMINI_API_KEY`.

### 3.2. Set Environment Variable

Set the key in your terminal session. This must be done **before** running the application.

```bash
export GEMINI_API_KEY="YOUR_GEMINI_API_KEY_HERE"
```

*(Optional: If you are using the `google_search_tool` in `pf_debug_api.py`, you will also need to set `GOOGLE_SEARCH_API_KEY` and `GOOGLE_CSE_ID`.)*

#### 1.Where to get these keys:

1.  GEMINI_API_KEY: Get from https://ai.google.dev/

2.  GOOGLE_SEARCH_API_KEY: Get from https://console.cloud.google.com/

3.  GOOGLE_CSE_ID: Get from https://programmablesearchengine.google.com/

## 4. Execution

There are two primary ways to run the project: the web application (for the full AI experience) and the command-line debug script.

### 4.1. Running the Web Application (Full AI Agent)

The `pf_debug_api.py` file runs the Flask application, which serves the web interface and the AI-powered search API.

```bash
python pf_debug_api.py
```

*   The application will start on `http://127.0.0.1:5055` (or similar).
*   Open your browser to this address to access the `pf_web_test.html` interface and interact with the AI agent using natural language prompts.

### 4.2. Running the Comprehensive Debug Script

The `comprehensive_debug.py` script is used to test the core search and filtering logic.

```bash
python comprehensive_debug.py
```

*   **Purpose:** This script tests the search function with and without the `property_type` filter and is useful for verifying that the data fetching and caching layers are working correctly.
*   **Note on the Bug:** As previously analyzed, this script needs the client-side filtering logic to be applied to its results to match the website's output.

## 5. Project Structure Overview

| File | Role | Key Functionality |
| :--- | :--- | :--- |
| `property_finder.py` | **Data Scraper** | Fetches raw data from Property Finder API, handles location ID lookup, and extracts the dynamic `buildId`. |
| `test_prop.py` | **Core Search/Caching** | Implements the `search_properties` function, which manages cache key generation, SQLite caching, and calls the data scraper. |
| `pf_debug_api.py` | **AI Agent / API Server** | Hosts the Flask application, defines the `gemini_search` endpoint, sets up the Gemini AI model with tools, and applies the crucial client-side filtering (`_filter_listings_by_constraints`). |
| `comprehensive_debug.py` | **Testing Script** | Command-line utility to test the `search_properties` function flow. |
| `pf_web_test.html` | **Frontend** | The simple HTML interface for interacting with the `pf_debug_api.py` server. |
| `database.py` | **Database Layer** | *(Assumed)* Contains functions like `init_db`, `find_cached_query`, and `save_query_and_properties` for SQLite interaction. |
