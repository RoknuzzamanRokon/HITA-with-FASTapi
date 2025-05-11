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



app = FastAPI()



logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logger.info("Starting FastAPI application...")

models.Base.metadata.create_all(bind=engine)


# Apply the custom OpenAPI schema
app.openapi = lambda: custom_openapi(app)



app.include_router(auth_router)
app.include_router(users_router)
app.include_router(hotels_demo_router)
app.include_router(hotels_router)

