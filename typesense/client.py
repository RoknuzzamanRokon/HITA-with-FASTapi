import typesense
import os

# Typesense configuration
TYPESENSE_CONFIG = {
    "nodes": [
        {
            "host": os.getenv("TYPESENSE_HOST", "localhost"),
            "port": os.getenv("TYPESENSE_PORT", "8108"),
            "protocol": os.getenv("TYPESENSE_PROTOCOL", "http"),
        }
    ],
    "api_key": os.getenv("TYPESENSE_API_KEY", "xyz123"),
    "connection_timeout_seconds": 30,
}


def get_typesense_client():
    """Get configured Typesense client instance"""
    return typesense.Client(TYPESENSE_CONFIG)
