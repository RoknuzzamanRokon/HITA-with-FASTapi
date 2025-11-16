from database import engine
import os
import models
import logging
from custom_openapi import custom_openapi

# Fastapi Base
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from fastapi.exception_handlers import RequestValidationError

# New imports for caching
from fastapi_cache import FastAPICache
from fastapi_cache.backends.redis import RedisBackend
import redis.asyncio as aioredis

# Import error handlers
from error_handlers import register_error_handlers 

# Include routers
from routes.auth import router as auth_router
from routes.usersIntegrations import router as users_router
from routes.hotelsDemo import router as hotels_demo_router
from routes.hotelIntegration import router as hotels_router
from routes.contents import router as contents_router
from routes.permissions import router as permissions_router
from routes.delete import router as delete_router
from routes.mapping import router as mapping_router
from routes.health import router as health_router
from routes.cache_management import router as cache_router
from routes.cached_user_routes import router as cache_users_router
from routes.audit_dashboard import router as audit_router
from routes.dashboard import router as dashboard_router
from routes.export import router as export_router

from routes.hotelRawData import router as raw_content_data
from routes.hotelFormattingData import router as hotel_formatting_data
from routes.hotelRawDataCollectionFromSupplier import router as hotel_row_data_collection
from routes.locations import router as locations_router
from routes.database_health import router as db_health_router
from routes.analytics import router as analytics_router, dashboard_router as analytics_dashboard_router
from routes.ml_mapping import router as ml_mapping_router

from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from security.middleware import create_security_middleware_stack
from middleware.ip_middleware import IPAddressMiddleware



app = FastAPI()
create_security_middleware_stack(app)

# Add IP address middleware to properly extract client IPs
app.add_middleware(
    IPAddressMiddleware,
    trusted_proxies=['127.0.0.1', '::1', '192.168.0.0/16', '10.0.0.0/8']
)

# Add trusted host middleware to handle proxy headers
app.add_middleware(
    TrustedHostMiddleware, 
    allowed_hosts=["*"]  # Configure this based on your deployment
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "*"  # Allow all origins (remove in production for better security)
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ——————— Initialize Redis cache and Export Worker on startup ———————
@app.on_event("startup")
async def startup():
    # Create Redis connection (adjust URL if needed)
    # Note: decode_responses should be False for fastapi-cache2 to work properly
    redis = aioredis.from_url(
        "redis://localhost", encoding="utf8", decode_responses=False
    )
    # Initialize FastAPI-Cache with a prefix
    FastAPICache.init(RedisBackend(redis), prefix="fastapi-cache")
    
    # Initialize dedicated export worker
    from services.export_worker import get_export_worker
    worker = get_export_worker()
    logger.info("Export worker initialized")

@app.on_event("shutdown")
async def shutdown():
    # Shutdown export worker gracefully
    from services.export_worker import shutdown_export_worker
    shutdown_export_worker()
    logger.info("Export worker shutdown complete")
# ————————————————————————————————————————————————


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logger.info("Starting FastAPI application...")

models.Base.metadata.create_all(bind=engine)

# Register comprehensive error handlers
register_error_handlers(app)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # Check if the error is about password length
    for error in exc.errors():
        if (
            error["loc"][-1] == "password"
            and error["type"] == "string_too_short"
        ):
            return JSONResponse(
                status_code=400,
                content={"error": "Need to input valid password and it must be 8 letter long."}
            )
        
        # Check for email validation error
        if (
            error["loc"][-1] == "email"
            and error["type"] == "value_error"
        ):
            return JSONResponse(
                status_code=400,
                content={"error": "Must need valid email"}
            )
    
    # Convert errors to JSON-serializable format
    serializable_errors = []
    for error in exc.errors():
        error_dict = {
            "loc": error.get("loc", []),
            "msg": str(error.get("msg", "")),
            "type": error.get("type", ""),
        }
        # Add context if available
        if "ctx" in error:
            error_dict["ctx"] = {k: str(v) for k, v in error["ctx"].items()}
        serializable_errors.append(error_dict)
    
    # Default validation error
    return JSONResponse(
        status_code=422,
        content={"detail": serializable_errors}
    )


app.include_router(auth_router)
app.include_router(users_router)
app.include_router(hotels_demo_router)
app.include_router(hotels_router)
app.include_router(contents_router)
app.include_router(permissions_router)
app.include_router(delete_router)
app.include_router(mapping_router)
app.include_router(health_router)
app.include_router(cache_router)
app.include_router(cache_users_router)
app.include_router(audit_router)
app.include_router(dashboard_router)
app.include_router(export_router)


app.include_router(raw_content_data)
app.include_router(hotel_formatting_data)
app.include_router(hotel_row_data_collection)
app.include_router(locations_router)
app.include_router(db_health_router)
app.include_router(analytics_router)
app.include_router(analytics_dashboard_router)
app.include_router(ml_mapping_router)


# Compute absolute path to the directory containing this file
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Mount static files using the absolute path
static_dir = os.path.join(BASE_DIR, "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")
# Override the default docs endpoint to use our custom HTML from custom_openapi
@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    """Custom Swagger UI with enhanced styling and features"""
    from custom_openapi import create_custom_swagger_ui_response
    return create_custom_swagger_ui_response(app)

# Apply the custom OpenAPI schema
app.openapi = lambda: custom_openapi(app)
