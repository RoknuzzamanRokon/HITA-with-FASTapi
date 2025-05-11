from fastapi import FastAPI
from database import engine
import models
import logging
from custom_openapi import custom_openapi
# Include routers
from routes.auth import router as auth_router
from routes.users import router as users_router
from routes.hotelsDemo import router as hotels_demo_router
from routes.hotels import router as hotels_router
from fastapi.staticfiles import StaticFiles
import os



app = FastAPI()



logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logger.info("Starting FastAPI application...")

models.Base.metadata.create_all(bind=engine)

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(hotels_demo_router)
app.include_router(hotels_router)






# Compute absolute path to the directory containing this file
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Mount static files using the absolute path
static_dir = os.path.join(BASE_DIR, "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")
# Apply the custom OpenAPI schema
app.openapi = lambda: custom_openapi(app)


