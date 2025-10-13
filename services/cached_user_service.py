"""
Cached user service for improved performance
"""

from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func, case, or_, and_
from datetime import datetime, timedelta
import logging

from models import User, UserPoint, PointTransaction, UserProviderPermission, UserActivityLog, UserSession
from cache_config import cached, CacheConfig, CacheKeys, cache
# Import existing schemas - we'll use dict responses for now
# from schemas import UserResponse

logger = logging.getLogger(__name__)

class CachedUserService:
    """User service with caching layer for improved performance"""
    
    def __init__(self, db: Session):
        self.db = db
    
    @cached(ttl=CacheConfig.USER_STATS_TTL, key_prefix=CacheKeys.USER_STATS)
    def get_user_statistics(self) -> Dict[str, Any]:
        """Get user statistics with caching"""
        logger.info("Fetching user statistics from database")
        
        # Get basic user counts by role and status
        user_stats = self.db.query(
            func.count(User.id).label('total_users'),
            func.sum(case((User.role == 'super_user', 1), else_=0)).label('super_users'),
            func.sum(case((User.role == 'admin_user', 1), else_=0)).label('admin_users'),
            func.sum(case((User.role == 'general_user', 1), else_=0)).label('general_users'),
            func.sum(case((User.is_active == True, 1), else_=0)).label('active_users'),
            func.sum(case((User.is_active == False, 1), else_=0)).label('inactive_users')
        ).first()
        
        # Get point statistics
        point_stats = self.db.query(
            func.sum(UserPoint.total_points).label('total_points_distributed'),
            func.sum(UserPoint.current_points).label('current_points_balance')
        ).first()
        
        # Get recent signups (last 7 days)
        recent_signups = self.db.query(func.count(User.id)).filter(
            User.created_at >= datetime.utcnow() - timedelta(days=7)
        ).scalar()
        
        return {
            'total_users': user_stats.total_users or 0,
            'super_users': user_stats.super_users or 0,
            'admin_users': user_stats.admin_users or 0,
            'general_users': user_stats.general_users or 0,
            'active_users': user_stats.active_users or 0,
            'inactive_users': user_stats.inactive_users or 0,
            'total_points_distributed': point_stats.total_points_distributed or 0,
            'current_points_balance': point_stats.current_points_balance or 0,
            'recent_signups': recent_signups or 0,
            'last_updated': datetime.utcnow().isoformat()
        }
    
    def get_users_paginated(
        self, 
        page: int = 1, 
        limit: int = 25,
        search: Optional[str] = None,
        role: Optional[str] = None,
        is_active: Optional[bool] = None,
        sort_by: str = "created_at",
        sort_order: str = "desc"
    ) -> Dict[str, Any]:
        """Get paginated users with caching"""
        
        # Build filters for cache key
        filters = {
            'search': search,
            'role': role,
            'is_active': is_active,
            'sort_by': sort_by,
            'sort_order': sort_order
        }
        
        # Try to get from cache
        cache_key = CacheKeys.user_list_key(page, limit, filters)
        cached_result = cache.get(cache_key)
        
        if cached_result:
            logger.debug(f"Cache hit for user list: {cache_key}")
            return cached_result
        
        logger.info(f"Fetching user list from database: page={page}, limit={limit}")
        
        # Build query
        query = self.db.query(User)
        
        # Apply filters
        if search:
            search_term = f"%{search}%"
            query = query.filter(
                or_(
                    User.username.like(search_term),
                    User.email.like(search_term)
                )
            )
        
        if role:
            query = query.filter(User.role == role)
        
        if is_active is not None:
            query = query.filter(User.is_active == is_active)
        
        # Apply sorting
        if sort_order.lower() == 'desc':
            query = query.order_by(getattr(User, sort_by).desc())
        else:
            query = query.order_by(getattr(User, sort_by).asc())
        
        # Get total count
        total = query.count()
        
        # Apply pagination
        users = query.offset((page - 1) * limit).limit(limit).all()
        
        # Convert to response format
        user_list = []
        for user in users:
            # Get user points
            user_points = self.db.query(UserPoint).filter(UserPoint.user_id == user.id).first()
            
            # Get active suppliers
            active_suppliers = self.db.query(UserProviderPermission.provider_name).filter(
                UserProviderPermission.user_id == user.id
            ).all()
            
            # Get recent activity
            recent_activity = self.db.query(PointTransaction).filter(
                or_(
                    PointTransaction.giver_id == user.id,
                    PointTransaction.receiver_id == user.id
                ),
                PointTransaction.created_at >= datetime.utcnow() - timedelta(days=7)
            ).first()
            
            # Get last login from sessions
            last_session = self.db.query(UserSession).filter(
                UserSession.user_id == user.id
            ).order_by(UserSession.last_activity.desc()).first()
            
            user_data = {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'role': user.role,
                'is_active': user.is_active,
                'created_at': user.created_at.isoformat() if user.created_at else None,
                'updated_at': user.updated_at.isoformat() if user.updated_at else None,
                'created_by': user.created_by,
                'point_balance': user_points.current_points if user_points else 0,
                'total_points': user_points.total_points if user_points else 0,
                'paid_status': 'Paid' if (user_points and user_points.current_points > 0) else 'Unpaid',
                'total_requests': len(user.sent_transactions) + len(user.received_transactions),
                'activity_status': 'Active' if recent_activity else 'Inactive',
                'active_suppliers': [supplier[0] for supplier in active_suppliers],
                'last_login': last_session.last_activity.isoformat() if last_session else None
            }
            user_list.append(user_data)
        
        # Build pagination metadata
        total_pages = (total + limit - 1) // limit
        pagination = {
            'page': page,
            'limit': limit,
            'total': total,
            'total_pages': total_pages,
            'has_next': page < total_pages,
            'has_prev': page > 1
        }
        
        result = {
            'users': user_list,
            'pagination': pagination,
            'statistics': self.get_user_statistics()
        }
        
        # Cache the result
        cache.set(cache_key, result, CacheConfig.USER_LIST_TTL)
        logger.debug(f"Cached user list: {cache_key}")
        
        return result
    
    def get_user_details(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed user information with caching"""
        
        cache_key = CacheKeys.user_details_key(user_id)
        cached_result = cache.get(cache_key)
        
        if cached_result:
            logger.debug(f"Cache hit for user details: {cache_key}")
            return cached_result
        
        logger.info(f"Fetching user details from database: {user_id}")
        
        # Get user
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            return None
        
        # Get user points
        user_points = self.db.query(UserPoint).filter(UserPoint.user_id == user_id).first()
        
        # Get provider permissions
        permissions = self.db.query(UserProviderPermission).filter(
            UserProviderPermission.user_id == user_id
        ).all()
        
        # Get recent transactions
        recent_transactions = self.db.query(PointTransaction).filter(
            or_(
                PointTransaction.giver_id == user_id,
                PointTransaction.receiver_id == user_id
            )
        ).order_by(PointTransaction.created_at.desc()).limit(10).all()
        
        # Get recent activity logs
        recent_activities = self.db.query(UserActivityLog).filter(
            UserActivityLog.user_id == user_id
        ).order_by(UserActivityLog.created_at.desc()).limit(10).all()
        
        # Get active sessions
        active_sessions = self.db.query(UserSession).filter(
            UserSession.user_id == user_id,
            UserSession.is_active == True,
            UserSession.expires_at > datetime.utcnow()
        ).all()
        
        user_details = {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'role': user.role,
            'is_active': user.is_active,
            'created_at': user.created_at.isoformat() if user.created_at else None,
            'updated_at': user.updated_at.isoformat() if user.updated_at else None,
            'created_by': user.created_by,
            'point_balance': user_points.current_points if user_points else 0,
            'total_points': user_points.total_points if user_points else 0,
            'used_points': user_points.total_used_points if user_points else 0,
            'provider_permissions': [
                {
                    'provider_name': perm.provider_name,
                    'id': perm.id
                } for perm in permissions
            ],
            'recent_transactions': [
                {
                    'id': trans.id,
                    'points': trans.points,
                    'transaction_type': trans.transaction_type,
                    'created_at': trans.created_at.isoformat() if trans.created_at else None,
                    'giver_id': trans.giver_id,
                    'receiver_id': trans.receiver_id
                } for trans in recent_transactions
            ],
            'recent_activities': [
                {
                    'id': activity.id,
                    'action': activity.action,
                    'details': activity.details,
                    'created_at': activity.created_at.isoformat() if activity.created_at else None,
                    'ip_address': activity.ip_address
                } for activity in recent_activities
            ],
            'active_sessions': len(active_sessions),
            'last_activity': max([session.last_activity for session in active_sessions]).isoformat() if active_sessions else None
        }
        
        # Cache the result
        cache.set(cache_key, user_details, CacheConfig.USER_DETAILS_TTL)
        logger.debug(f"Cached user details: {cache_key}")
        
        return user_details
    
    @cached(ttl=CacheConfig.DASHBOARD_STATS_TTL, key_prefix=CacheKeys.DASHBOARD_STATS)
    def get_dashboard_statistics(self) -> Dict[str, Any]:
        """Get comprehensive dashboard statistics with caching"""
        logger.info("Fetching dashboard statistics from database")
        
        # Get user statistics
        user_stats = self.get_user_statistics()
        
        # Get point distribution by role
        point_distribution = self.db.query(
            User.role,
            func.sum(UserPoint.current_points).label('total_points'),
            func.count(User.id).label('user_count')
        ).join(UserPoint, User.id == UserPoint.user_id, isouter=True)\
         .group_by(User.role).all()
        
        # Get recent activity trends (last 30 days)
        activity_trends = self.db.query(
            func.date(PointTransaction.created_at).label('date'),
            func.count(PointTransaction.id).label('transaction_count'),
            func.sum(PointTransaction.points).label('points_transferred')
        ).filter(
            PointTransaction.created_at >= datetime.utcnow() - timedelta(days=30)
        ).group_by(func.date(PointTransaction.created_at)).all()
        
        # Get top active users (by transaction count)
        top_users = self.db.query(
            User.id,
            User.username,
            User.email,
            func.count(PointTransaction.id).label('transaction_count')
        ).join(
            PointTransaction, 
            or_(
                PointTransaction.giver_id == User.id,
                PointTransaction.receiver_id == User.id
            )
        ).group_by(User.id, User.username, User.email)\
         .order_by(func.count(PointTransaction.id).desc())\
         .limit(10).all()
        
        return {
            **user_stats,
            'point_distribution': [
                {
                    'role': dist.role,
                    'total_points': dist.total_points or 0,
                    'user_count': dist.user_count or 0
                } for dist in point_distribution
            ],
            'activity_trends': [
                {
                    'date': trend.date.isoformat() if trend.date else None,
                    'transaction_count': trend.transaction_count or 0,
                    'points_transferred': trend.points_transferred or 0
                } for trend in activity_trends
            ],
            'top_active_users': [
                {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'transaction_count': user.transaction_count or 0
                } for user in top_users
            ]
        }
    
    def invalidate_user_caches(self, user_id: str = None):
        """Invalidate user-related caches"""
        logger.info(f"Invalidating user caches for user_id: {user_id}")
        CacheKeys.invalidate_user_caches(user_id)
    
    def warm_cache(self):
        """Warm up frequently accessed caches"""
        logger.info("Warming up caches...")
        
        try:
            # Warm user statistics
            self.get_user_statistics()
            
            # Warm dashboard statistics
            self.get_dashboard_statistics()
            
            # Warm first page of users
            self.get_users_paginated(page=1, limit=25)
            
            logger.info("Cache warming completed successfully")
            
        except Exception as e:
            logger.error(f"Cache warming failed: {e}")