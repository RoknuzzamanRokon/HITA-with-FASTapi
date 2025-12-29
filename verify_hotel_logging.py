
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
                
                print("\nRecent hotel activities:")
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
