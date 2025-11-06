import sqlite3
from flask import g

DATABASE = 'bayut_properties.db'


def get_db():
    """Get database connection"""
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db


def init_app(app):
    """Initialize the app with database"""
    app.teardown_appcontext(close_connection)


def close_connection(exception):
    """Close database connection"""
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()


def init_db():
    """Initialize database tables"""
    db = get_db()
    cursor = db.cursor()

    # Create cached_queries table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS cached_queries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        query_string TEXT UNIQUE NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # Create cached_properties table (REMOVED query_id - we'll use junction table)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS cached_properties (
        id TEXT PRIMARY KEY,
        title TEXT,
        price INTEGER,
        area INTEGER,
        rooms INTEGER,
        baths INTEGER,
        purpose TEXT,
        completion_status TEXT,
        latitude REAL,
        longitude REAL,
        location_name TEXT,
        cover_photo_url TEXT,
        all_image_urls TEXT,
        agency_name TEXT,
        contact_name TEXT,
        mobile_number TEXT,
        whatsapp_number TEXT,
        down_payment_percentage REAL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # Create query_property_map table (junction table)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS query_property_map (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        query_id INTEGER NOT NULL,
        property_id TEXT NOT NULL,
        FOREIGN KEY (query_id) REFERENCES cached_queries(id),
        FOREIGN KEY (property_id) REFERENCES cached_properties(id),
        UNIQUE(query_id, property_id)
    )
    ''')

    db.commit()
    print("Database initialized for search caching.")


def find_cached_query(query_string):
    """Find a cached query by query string"""
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT id FROM cached_queries WHERE query_string = ?", (query_string,))
    result = cursor.fetchone()
    return result[0] if result else None


def save_query_and_properties(query_string, properties):
    """Save a query and its associated properties"""
    db = get_db()
    cursor = db.cursor()

    try:
        # Insert the query
        cursor.execute(
            "INSERT OR IGNORE INTO cached_queries (query_string) VALUES (?)",
            (query_string,)
        )
        db.commit()

        # Get the query ID
        cursor.execute("SELECT id FROM cached_queries WHERE query_string = ?", (query_string,))
        query_id = cursor.fetchone()[0]

        # Insert properties (WITHOUT query_id in the properties table)
        for prop in properties:
            # Convert all_image_urls to comma-separated string if it's a list
            all_image_urls = prop.get('all_image_urls', [])
            if isinstance(all_image_urls, list):
                all_image_urls_str = ','.join(all_image_urls) if all_image_urls else ''
            else:
                all_image_urls_str = all_image_urls

            # Insert/update property (no query_id here)
            cursor.execute('''
            INSERT OR REPLACE INTO cached_properties (
                id, title, price, area, rooms, baths, purpose,
                completion_status, latitude, longitude, location_name,
                cover_photo_url, all_image_urls, agency_name, contact_name,
                mobile_number, whatsapp_number, down_payment_percentage
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                str(prop.get('id')),
                prop.get('title'),
                prop.get('price'),
                prop.get('area'),
                prop.get('rooms'),
                prop.get('baths'),
                prop.get('purpose'),
                prop.get('completion_status'),
                prop.get('latitude'),
                prop.get('longitude'),
                prop.get('location_name'),
                prop.get('cover_photo_url'),
                all_image_urls_str,
                prop.get('agency_name'),
                prop.get('contact_name'),
                prop.get('mobile_number'),
                prop.get('whatsapp_number'),
                prop.get('down_payment_percentage')
            ))

            # Insert the mapping in the junction table
            cursor.execute('''
            INSERT OR IGNORE INTO query_property_map (query_id, property_id)
            VALUES (?, ?)
            ''', (query_id, str(prop.get('id'))))

        db.commit()
        print(f"Saved {len(properties)} properties for query ID {query_id}.")

    except Exception as e:
        db.rollback()
        print(f"Error saving query and properties: {e}")
        raise


def get_properties_for_query(query_id):
    """Get all properties for a cached query"""
    db = get_db()
    cursor = db.cursor()

    cursor.execute('''
    SELECT cp.* FROM cached_properties cp
    JOIN query_property_map qpm ON cp.id = qpm.property_id
    WHERE qpm.query_id = ?
    ''', (query_id,))

    rows = cursor.fetchall()
    properties = []

    for row in rows:
        prop = dict(row)
        # Convert all_image_urls back to list
        if prop.get('all_image_urls'):
            prop['all_image_urls'] = prop['all_image_urls'].split(',')
        else:
            prop['all_image_urls'] = []
        properties.append(prop)

    return properties