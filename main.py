from fastapi import FastAPI, Request
from database import engine
import models
import logging
from custom_openapi import custom_openapi
# Include routers
from routes.auth import router as auth_router
from routes.users import router as users_router
from routes.hotelsDemo import router as hotels_demo_router
from routes.hotels import router as hotels_router
from routes.contents import router as contents_router
from fastapi.staticfiles import StaticFiles
import os
from fastapi.responses import JSONResponse
from fastapi.exception_handlers import RequestValidationError
from fastapi.exceptions import RequestValidationError



app = FastAPI()



logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logger.info("Starting FastAPI application...")

models.Base.metadata.create_all(bind=engine)



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





# Compute absolute path to the directory containing this file
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Mount static files using the absolute path
static_dir = os.path.join(BASE_DIR, "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")
# Apply the custom OpenAPI schema
app.openapi = lambda: custom_openapi(app)


