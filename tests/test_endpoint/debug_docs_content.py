import requests

def debug_docs_content():
    """Debug what's actually being returned by the docs endpoints"""
    
    endpoints = [
        {"url": "http://127.0.0.1:8002/docs", "name": "Swagger UI"},
        {"url": "http://127.0.0.1:8002/redoc", "name": "ReDoc"}
    ]
    
    for endpoint in endpoints:
        print(f"\n=== {endpoint['name']} Content ===")
        try:
            response = requests.get(endpoint['url'])
            print(f"Status: {response.status_code}")
            print(f"Headers: {dict(response.headers)}")
            print(f"Content Length: {len(response.content)}")
            print(f"Content Preview:")
            print("-" * 50)
            print(response.text[:1000])  # First 1000 characters
            print("-" * 50)
            
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    debug_docs_content()