from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.openapi.utils import get_openapi

app = FastAPI()

# Mount static files first
app.mount("/static", StaticFiles(directory="static"), name="static")


def custom_openapi(app: FastAPI):
    if app.openapi_schema:
        return app.openapi_schema
    
    # Generate base schema
    openapi_schema = get_openapi(
        title="Hotel API",
        version="V1.0",
        description="API for managing hotels and user points.",
        routes=app.routes,  # Access app's routes directly
    )

    # Add logo configuration
    openapi_schema["info"]["x-logo"] = {
        "url": "/static/images/ittapilogo_1.png",
        "altText": "Hotel API Logo",
        "backgroundColor": "#FFFFFF",
        "href": "https://example.com"
    }

    app.openapi_schema = openapi_schema
    return app.openapi_schema

# This is the critical fix ⚠️
app.openapi = custom_openapi 