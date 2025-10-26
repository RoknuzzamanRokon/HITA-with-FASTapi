from fastapi import FastAPI

# Create a minimal FastAPI app to test docs
app = FastAPI(title="Test API", version="1.0.0")

@app.get("/")
def read_root():
    return {"message": "Hello World"}

@app.get("/test")
def test_endpoint():
    return {"test": "This is a test endpoint"}

if __name__ == "__main__":
    import uvicorn
    print("Starting minimal FastAPI app...")
    print("Docs available at: http://127.0.0.1:8003/docs")
    print("ReDoc available at: http://127.0.0.1:8003/redoc")
    uvicorn.run(app, host="127.0.0.1", port=8003)