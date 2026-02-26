import csv
import typesense
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get configuration from environment variables
TYPESENSE_HOST = os.getenv("TYPESENSE_HOST", "localhost")
TYPESENSE_PORT = os.getenv("TYPESENSE_PORT", "8108")
TYPESENSE_PROTOCOL = os.getenv("TYPESENSE_PROTOCOL", "http")
TYPESENSE_API_KEY = os.getenv("TYPESENSE_API_KEY", "xyz123")

# CSV path - use relative path that works on both Windows and Linux
CSV_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "static",
    "hotelcontent",
    "itt_hotel_basic_info.csv",
)

BATCH_SIZE = 5000

print(f"🔧 Configuration:")
print(f"   Host: {TYPESENSE_HOST}")
print(f"   Port: {TYPESENSE_PORT}")
print(f"   Protocol: {TYPESENSE_PROTOCOL}")
print(f"   CSV Path: {CSV_PATH}")
print()

# Check if CSV file exists
if not os.path.exists(CSV_PATH):
    print(f"❌ Error: CSV file not found at {CSV_PATH}")
    print(f"Please ensure the file exists at this location.")
    exit(1)

client = typesense.Client(
    {
        "nodes": [
            {
                "host": TYPESENSE_HOST,
                "port": TYPESENSE_PORT,
                "protocol": TYPESENSE_PROTOCOL,
            }
        ],
        "api_key": TYPESENSE_API_KEY,
        "connection_timeout_seconds": 30,
    }
)


def to_float(v):
    try:
        if v is None:
            return None
        v = str(v).strip()
        if v == "" or v.lower() == "null":
            return None
        return float(v)
    except Exception:
        return None


def to_str(v):
    if v is None:
        return None
    v = str(v).strip()
    return v if v != "" else None


def flush(batch):
    if not batch:
        return
    # action="upsert" lets you rerun safely
    res = client.collections["hotels"].documents.import_(batch, {"action": "upsert"})
    # res is a list of dictionaries in newer versions of typesense
    # quick error check:
    if isinstance(res, list):
        errors = [
            item
            for item in res
            if isinstance(item, dict) and item.get("success") == False
        ]
    else:
        # fallback for older versions that return string
        errors = [line for line in res.splitlines() if '"success":false' in line]

    if errors:
        print("⚠️ import errors:", errors[:3], f"(showing 3 of {len(errors)})")


batch = []
count = 0

with open(CSV_PATH, newline="", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        doc = {
            "id": to_str(row.get("Id")) or "",
            "ittid": to_str(row.get("ittid")),
            "name": to_str(row.get("Name")) or "",
            "address1": to_str(row.get("AddressLine1")),
            "address2": to_str(row.get("AddressLine2")),
            "city": to_str(row.get("CityName")),
            "country": to_str(row.get("CountryName")),
            "country_code": to_str(row.get("CountryCode")),
            "postal_code": to_str(row.get("PostalCode")),
            "chain": to_str(row.get("ChainName")),
            "property_type": to_str(row.get("PropertyType")),
            "lat": to_float(row.get("Latitude")),
            "lon": to_float(row.get("Longitude")),
            "popularity": 1,  # Default popularity score
        }

        batch.append(doc)
        count += 1

        if len(batch) >= BATCH_SIZE:
            flush(batch)
            batch = []
            if count % (BATCH_SIZE * 10) == 0:
                print(f"✅ Imported {count:,} docs...")

flush(batch)
print(f"🎉 Done. Total imported: {count:,}")
