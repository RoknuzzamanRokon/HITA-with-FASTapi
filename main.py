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

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ——————— Initialize Redis cache on startup ———————
@app.on_event("startup")
async def startup():
    # Create Redis connection (adjust URL if needed)
    redis = aioredis.from_url(
        "redis://localhost", encoding="utf8", decode_responses=True
    )
    # Initialize FastAPI-Cache with a  prefix
    FastAPICache.init(RedisBackend(redis), prefix="fastapi-cache")
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
        
    # Default validation error
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors()}
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


# Compute absolute path to the directory containing this file
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Mount static files using the absolute path
static_dir = os.path.join(BASE_DIR, "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")
# Apply the custom OpenAPI schema
app.openapi = lambda: custom_openapi(app)
