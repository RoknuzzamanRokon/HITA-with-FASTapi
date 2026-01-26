import typesense

client = typesense.Client(
    {
        "nodes": [{"host": "localhost", "port": "8108", "protocol": "http"}],
        "api_key": "xyz123",
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
