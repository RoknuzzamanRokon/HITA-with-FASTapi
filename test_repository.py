#!/usr/bin/env python3
"""
Test script for the enhanced user repository
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import get_db
from repositories.user_repository import UserRepository, UserFilters, SortConfig
from models import UserRole
from datetime import datetime, timedelta

def test_repository():
    """Test the repository functionality"""
    print("Testing Enhanced User Repository...")
    
    # Get database session
    db = next(get_db())
    
    try:
        # Initialize repository
        repo = UserRepository(db)
        print("✓ Repository initialized successfully")
        
        # Test 1: Get user statistics
        print("\n1. Testing user statistics...")
        stats = repo.get_user_statistics()
        print(f"   Total users: {stats['total_users']}")
        print(f"   Super users: {stats['super_users']}")
        print(f"   Admin users: {stats['admin_users']}")
        print(f"   General users: {stats['general_users']}")
        print(f"   Active users: {stats['active_users']}")
        print("   ✓ Statistics retrieved successfully")
        
        # Test 2: Basic pagination
        print("\n2. Testing basic pagination...")
        filters = UserFilters()
        sort_config = SortConfig(sort_by="created_at", sort_order="desc")
        
        users, total = repo.get_users_with_pagination(
            page=1, 
            limit=5, 
            filters=filters, 
            sort_config=sort_config
        )
        print(f"   Retrieved {len(users)} users out of {total} total")
        if users:
            print(f"   First user: {users[0].username} ({users[0].email})")
        print("   ✓ Pagination working")
        
        # Test 3: Search functionality
        print("\n3. Testing search functionality...")
        if users:
            # Search for the first user's username
            search_term = users[0].username[:3]  # First 3 characters
            search_results = repo.search_users(search_term, limit=10)
            print(f"   Search for '{search_term}' returned {len(search_results)} results")
            print("   ✓ Search working")
        
        # Test 4: Filtering by role
        print("\n4. Testing role filtering...")
        role_filters = UserFilters(role=UserRole.GENERAL_USER)
        general_users, general_total = repo.get_users_with_pagination(
            page=1, 
            limit=5, 
            filters=role_filters, 
            sort_config=sort_config
        )
        print(f"   Found {general_total} general users")
        print("   ✓ Role filtering working")
        
        # Test 5: Advanced filtering
        print("\n5. Testing advanced filtering...")
        advanced_users, advanced_total, metadata = repo.get_users_with_advanced_filters(
            page=1,
            limit=3,
            is_active=True,
            sort_by="username",
            sort_order="asc"
        )
        print(f"   Advanced filter returned {len(advanced_users)} users")
        print(f"   Metadata: {metadata['pagination']}")
        print("   ✓ Advanced filtering working")
        
        # Test 6: Get user with details
        print("\n6. Testing detailed user retrieval...")
        if users:
            detailed_user = repo.get_user_with_details(users[0].id)
            if detailed_user:
                print(f"   Retrieved detailed info for: {detailed_user.username}")
                print(f"   Point balance: {detailed_user.current_point_balance}")
                print(f"   Active suppliers: {len(detailed_user.active_supplier_list)}")
                print("   ✓ Detailed user retrieval working")
        
        print("\n🎉 All repository tests passed successfully!")
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        db.close()
    
    return True

if __name__ == "__main__":
    success = test_repository()
    sys.exit(0 if success else 1)