#!/usr/bin/env python3
"""
Simple syntax checker for dashboard.py
"""

import ast
import sys

def check_syntax(filename):
    """Check if a Python file has valid syntax"""
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            source = f.read()
        
        # Parse the AST to check syntax
        ast.parse(source)
        print(f"✅ {filename} has valid syntax")
        return True
    except SyntaxError as e:
        print(f"❌ Syntax error in {filename}:")
        print(f"   Line {e.lineno}: {e.text}")
        print(f"   Error: {e.msg}")
        return False
    except Exception as e:
        print(f"❌ Error checking {filename}: {e}")
        return False

if __name__ == "__main__":
    files_to_check = [
        "routes/dashboard.py",
        "main.py"
    ]
    
    all_good = True
    for file in files_to_check:
        if not check_syntax(file):
            all_good = False
    
    if all_good:
        print("\n🎉 All files have valid syntax!")
        print("✅ Dashboard implementation is ready")
        print("🚀 You can now start your FastAPI server")
    else:
        print("\n🔧 Please fix the syntax errors above")
        sys.exit(1)