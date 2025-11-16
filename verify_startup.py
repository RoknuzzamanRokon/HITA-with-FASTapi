"""
Verify Application Startup

This script checks if the application can start without errors.
"""

import sys

print("Verifying application can start...")
print("="*60)

try:
    # Try to import main module
    print("\n1. Importing main module...")
    import main
    print("   ✅ Main module imported successfully")
    
    # Check if export worker is available
    print("\n2. Checking export worker...")
    from services.export_worker import get_export_worker
    print("   ✅ Export worker module available")
    
    # Check if export routes are available
    print("\n3. Checking export routes...")
    from routes.export import router
    print("   ✅ Export routes available")
    
    # Check if app is created
    print("\n4. Checking FastAPI app...")
    app = main.app
    print(f"   ✅ FastAPI app created: {app.title if hasattr(app, 'title') else 'Unnamed'}")
    
    # List all routes
    print("\n5. Checking export endpoints...")
    export_routes = [route for route in app.routes if '/export' in str(route.path)]
    for route in export_routes:
        print(f"   • {route.methods} {route.path}")
    
    print("\n" + "="*60)
    print("✅ ✅ ✅ ALL CHECKS PASSED ✅ ✅ ✅")
    print("="*60)
    print("\nThe application should start successfully.")
    print("\nTo start the server, run:")
    print("  uvicorn main:app --host 0.0.0.0 --port 8001 --reload")
    
except ImportError as e:
    print(f"\n❌ Import Error: {str(e)}")
    print("\nMissing dependency or syntax error in code.")
    sys.exit(1)
    
except Exception as e:
    print(f"\n❌ Error: {str(e)}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
