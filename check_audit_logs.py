"""
Check what's actually in the audit logs database
"""

from database import SessionLocal
import models
from sqlalchemy import func

def check_audit_logs():
    """Check what audit logs exist in database"""
    
    db = SessionLocal()
    
    try:
        print("🔍 Checking Audit Logs Database")
        print("=" * 50)
        
        # Total logs in database
        total_logs = db.query(models.UserActivityLog).count()
        print(f"Total audit logs in database: {total_logs}")
        
        # Logs with user_id (authenticated)
        user_logs = db.query(models.UserActivityLog).filter(models.UserActivityLog.user_id.isnot(None)).count()
        print(f"Logs with user_id: {user_logs}")
        
        # Logs without user_id (unauthenticated)
        anon_logs = db.query(models.UserActivityLog).filter(models.UserActivityLog.user_id.is_(None)).count()
        print(f"Logs without user_id: {anon_logs}")
        
        # Recent logs (last 10)
        recent_logs = db.query(models.UserActivityLog).order_by(models.UserActivityLog.created_at.desc()).limit(10).all()
        
        print(f"\n📋 Recent Audit Logs:")
        for log in recent_logs:
            user_info = f"User: {log.user_id}" if log.user_id else "User: Anonymous"
            print(f"   - {log.action} | {user_info} | IP: {log.ip_address} | {log.created_at}")
        
        # Activity by type
        activity_counts = db.query(
            models.UserActivityLog.action,
            func.count(models.UserActivityLog.id).label('count')
        ).group_by(models.UserActivityLog.action).all()
        
        print(f"\n📊 Activity Counts by Type:")
        for action, count in activity_counts:
            print(f"   - {action}: {count}")
        
        # Check specific user (roman)
        roman_user = db.query(models.User).filter(models.User.username == 'roman').first()
        if roman_user:
            roman_logs = db.query(models.UserActivityLog).filter(models.UserActivityLog.user_id == roman_user.id).count()
            print(f"\n👤 Roman's audit logs: {roman_logs}")
        else:
            print(f"\n👤 User 'roman' not found in database")
        
    finally:
        db.close()

if __name__ == "__main__":
    check_audit_logs()