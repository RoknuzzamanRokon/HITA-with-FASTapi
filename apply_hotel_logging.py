"""
Apply user activity logging to hotelIntegration.py automatically

This script will modify the existing hotelIntegration.py file to add
comprehensive user activity logging.
"""

import sys

sys.path.append(".")


def apply_logging_to_hotel_integration():
    """Apply activity logging to the existing hotelIntegration.py file"""

    try:
        # Read the current file
        with open("routes/hotelIntegration.py", "r", encoding="utf-8") as f:
            content = f.read()

        print("✓ Read existing hotelIntegration.py file")

        # Check if audit logging is already imported
        if "from security.audit_logging import" in content:
            print("✓ Audit logging already imported")
        else:
            # Add the import after the existing imports
            import_line = "from security.audit_logging import AuditLogger, ActivityType, SecurityLevel"

            # Find the last import line
            lines = content.split("\n")
            last_import_index = -1

            for i, line in enumerate(lines):
                if line.strip().startswith("from ") or line.strip().startswith(
                    "import "
                ):
                    last_import_index = i

            if last_import_index != -1:
                lines.insert(last_import_index + 1, "")
                lines.insert(
                    last_import_index + 2,
                    "# Import audit logging for user activity tracking",
                )
                lines.insert(last_import_index + 3, import_line)
                content = "\n".join(lines)
                print("✓ Added audit logging import")

        # Check if Request is imported
        if (
            "Request" not in content
            or "from fastapi import" not in content
            or "Request" not in content.split("from fastapi import")[1].split("\n")[0]
        ):
            # Add Request to FastAPI import
            content = content.replace(
                "from fastapi import APIRouter, Depends, HTTPException, status",
                "from fastapi import APIRouter, Depends, HTTPException, status, Request",
            )
            print("✓ Added Request import")

        # Add helper function if not exists
        helper_function = '''
def log_hotel_activity(
    db: Session,
    user: User,
    request: Request,
    activity_type: str,
    details: Dict[str, Any],
    security_level: SecurityLevel = SecurityLevel.LOW
):
    """Helper function to log hotel-related activities"""
    try:
        audit_logger = AuditLogger(db)
        audit_logger.log_activity(
            activity_type=ActivityType.API_ACCESS,
            user_id=user.id,
            details={
                **details,
                "module": "hotel_integration",
                "user_role": user.role.value,
                "user_email": user.email,
                "activity_category": activity_type
            },
            request=request,
            security_level=security_level,
            success=True
        )
    except Exception as e:
        logger.error(f"Failed to log hotel activity: {e}")

'''

        if "def log_hotel_activity(" not in content:
            # Find where to insert the helper function (after router definition)
            router_index = content.find("router = APIRouter(")
            if router_index != -1:
                # Find the end of the router definition
                end_index = content.find(")", router_index)
                end_index = content.find("\n", end_index) + 1

                content = content[:end_index] + helper_function + content[end_index:]
                print("✓ Added log_hotel_activity helper function")

        # Write the modified content back
        with open("routes/hotelIntegration.py", "w", encoding="utf-8") as f:
            f.write(content)

        print("✓ Successfully updated hotelIntegration.py")
        print()

        print("NEXT STEPS:")
        print("1. Add 'request: Request' parameter to each endpoint function")
        print("2. Add logging calls in each endpoint using log_hotel_activity()")
        print("3. Test the endpoints to ensure they work correctly")
        print()

        print("EXAMPLE USAGE IN ENDPOINT:")
        print(
            """
# Add this at the beginning of each endpoint function:
log_hotel_activity(
    db=db,
    user=current_user,
    request=request,
    activity_type="hotel_operation",
    details={
        "action": "specific_action_name",
        "endpoint": request.url.path,
        "method": request.method
    }
)
"""
        )

        return True

    except Exception as e:
        print(f"✗ Error updating hotelIntegration.py: {e}")
        return False


def create_verification_script():
    """Create a script to verify the logging is working"""

    verification_code = '''
"""
Verify hotel integration activity logging is working
"""

import sys
sys.path.append('.')

def verify_hotel_logging():
    try:
        from database import engine
        from sqlalchemy import text
        
        with engine.connect() as connection:
            # Check for hotel integration activities
            result = connection.execute(text("""
                SELECT COUNT(*) FROM user_activity_logs 
                WHERE JSON_EXTRACT(details, '$.module') = 'hotel_integration'
            """))
            
            hotel_activities = result.fetchone()[0]
            print(f"Hotel integration activities logged: {hotel_activities}")
            
            if hotel_activities > 0:
                # Show recent hotel activities
                result = connection.execute(text("""
                    SELECT user_id, 
                           JSON_EXTRACT(details, '$.activity_category') as category,
                           JSON_EXTRACT(details, '$.action') as action,
                           JSON_EXTRACT(details, '$.endpoint') as endpoint,
                           created_at
                    FROM user_activity_logs 
                    WHERE JSON_EXTRACT(details, '$.module') = 'hotel_integration'
                    ORDER BY created_at DESC 
                    LIMIT 10
                """))
                
                print("\\nRecent hotel activities:")
                for row in result:
                    print(f"  User: {row[0]}, Category: {row[1]}, Action: {row[2]}")
                    print(f"    Endpoint: {row[3]}, Time: {row[4]}")
                
            else:
                print("No hotel integration activities found yet.")
                print("Make some API calls to hotel endpoints to test logging.")
                
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    verify_hotel_logging()
'''

    with open("verify_hotel_logging.py", "w", encoding="utf-8") as f:
        f.write(verification_code)

    print("✓ Created verify_hotel_logging.py script")


def main():
    print("=== Applying Hotel Integration Activity Logging ===")
    print()

    # Apply the logging modifications
    if apply_logging_to_hotel_integration():
        print("SUCCESS: Hotel integration activity logging has been set up!")

        # Create verification script
        create_verification_script()

        print()
        print("WHAT WAS ADDED:")
        print("✓ Audit logging imports")
        print("✓ Request import for FastAPI")
        print("✓ log_hotel_activity() helper function")
        print()

        print("MANUAL STEPS NEEDED:")
        print("1. Add 'request: Request' parameter to each endpoint")
        print("2. Add logging calls using log_hotel_activity() in each function")
        print("3. Test endpoints after modifications")
        print()

        print("VERIFICATION:")
        print("After making API calls, run: python verify_hotel_logging.py")

    else:
        print("FAILED: Could not apply logging modifications")


if __name__ == "__main__":
    main()
