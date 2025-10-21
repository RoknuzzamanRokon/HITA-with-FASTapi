#!/usr/bin/env python3
"""
Wrapper script to run the mapping data insertion with proper environment
"""

import subprocess
import sys
import os

def main():
    print("🚀 Starting Hotel Mapping Data Insertion")
    print("=" * 50)
    
    # Change to backend directory
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(backend_dir)
    
    try:
        # Run with pipenv
        result = subprocess.run([
            "pipenv", "run", "python", "utils/insert_mapping_data.py"
        ], check=False)
        
        if result.returncode == 0:
            print("\n✅ Process completed successfully!")
        else:
            print(f"\n⚠️ Process exited with code {result.returncode}")
            
    except KeyboardInterrupt:
        print("\n⚠️ Process interrupted by user")
    except FileNotFoundError:
        print("❌ Error: pipenv not found. Please install pipenv or run directly:")
        print("   cd backend && python utils/insert_mapping_data.py")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()