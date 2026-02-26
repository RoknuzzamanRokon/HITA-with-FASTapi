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

print(f"🔧 Connecting to Typesense:")
print(f"   Host: {TYPESENSE_HOST}")
print(f"   Port: {TYPESENSE_PORT}")
print(f"   Protocol: {TYPESENSE_PROTOCOL}")
print()

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
        "connection_timeout_seconds": 10,
    }
)

schema = {
    "name": "hotels",
    "fields": [
        {"name": "id", "type": "string"},
        {"name": "ittid", "type": "string", "optional": True},
        {"name": "name", "type": "string"},
        {"name": "address1", "type": "string", "optional": True},
        {"name": "address2", "type": "string", "optional": True},
        {"name": "city", "type": "string", "optional": True},
        {"name": "country", "type": "string", "optional": True},
        {"name": "country_code", "type": "string", "optional": True},
        {"name": "postal_code", "type": "string", "optional": True},
        {"name": "chain", "type": "string", "optional": True},
        {"name": "property_type", "type": "string", "optional": True},
        {"name": "lat", "type": "float", "optional": True},
        {"name": "lon", "type": "float", "optional": True},
        # optional: helps filtering/ranking later
        {"name": "popularity", "type": "int32", "optional": True},
    ],
}

# recreate if exists (optional)
try:
    client.collections["hotels"].delete()
except Exception:
    pass

print(client.collections.create(schema))
print("✅ hotels collection created")
