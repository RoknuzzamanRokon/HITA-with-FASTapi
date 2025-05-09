from fastapi.openapi.utils import get_openapi
from fastapi import FastAPI

def custom_openapi(app: FastAPI):
    """Customize the OpenAPI schema with a logo."""
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title="Hotel API",
        version="1.0.0",
        description="API for managing hotels and user points.",
        routes=app.routes,
    )
    # Add the x-logo extension to the OpenAPI schema
    openapi_schema["info"]["x-logo"] = {
        "url": "https://example.com/logo.png",  # Replace with your logo URL
        "altText": "Hotel API Logo",  # Optional: Alternative text for the logo
        "backgroundColor": "#FFFFFF",  # Optional: Background color for the logo
        "href": "https://example.com"  # Optional: Link when clicking the logo
    }
    app.openapi_schema = openapi_schema
    return app.openapi_schema