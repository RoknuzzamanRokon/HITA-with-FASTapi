from typing import List, Tuple, Optional, Dict, Any
from sqlalchemy.orm import Session, selectinload, joinedload
from sqlalchemy import func, case, or_, and_, desc, asc, text
from datetime import datetime, timedelta
from models import User, UserPoint, PointTransaction, UserProviderPermission, UserRole
from dataclasses import dataclass
from .repository_config import (
    RepositoryConfig, cached_query, monitor_performance, 
    repository_metrics, performance_monitor
)
from .query_builders import QueryBuilder, AdvancedSorting, QueryOptimizer


@dataclass
class UserFilters:
    """Data class for user filtering parameters"""
    search: Optional[str] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None
    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None
    has_points: Optional[bool] = None
    activity_status: Optional[str] = None  # "Active" or "Inactive"


@dataclass
class SortConfig:
    """Data class for sorting configuration"""
    sort_by: str = "created_at"
    sort_order: str = "desc"  # "asc" or "desc"


class UserRepository:
    """Enhanced repository for user data access with optimized queries"""
    
    def __init__(self, db: Session):
        self.db = db
        self.query_builder = QueryBuilder()
        self.advanced_sorting = AdvancedSorting()
        self.query_optimizer = QueryOptimizer()

    @monitor_performance("get_users_with_pagination")
    @cached_query(['page', 'limit', 'filters', 'sort_config'])
    def get_users_with_pagination(
        self,
        page: int,
        limit: int,
        filters: UserFilters,
        sort_config: SortConfig
    ) -> Tuple[List[User], int]:
        """
        Get users with pagination, filtering, and sorting using optimized queries.
        Returns tuple of (users, total_count)
        """
        repository_metrics.increment_query_count()
        
        # Validate and adjust pagination parameters
        limit = min(limit, RepositoryConfig.MAX_PAGE_SIZE)
        page = max(1, page)
        
        # Base query with optimized joins and eager loading
        query = self.db.query(User).options(
            selectinload(User.user_points),
            selectinload(User.provider_permissions)
            # Note: sessions and activity_logs relationships disabled until tables are created
        )

        # Apply filters
        query = self._apply_filters(query, filters)

        # Get total count before pagination
        total = query.count()

        # Apply sorting
        query = self._apply_sorting(query, sort_config)

        # Apply pagination
        users = query.offset((page - 1) * limit).limit(limit).all()

        return users, total

    def search_users(self, search_query: str, limit: int = 50) -> List[User]:
        """
        Search users by username, email with database indexes
        """
        if not search_query:
            return []

        search_pattern = f"%{search_query}%"
        
        query = self.db.query(User).options(
            selectinload(User.user_points),
            selectinload(User.provider_permissions)
        ).filter(
            or_(
                User.username.ilike(search_pattern),
                User.email.ilike(search_pattern)
            )
        ).limit(limit)

        return query.all()

    @monitor_performance("get_user_statistics")
    @cached_query([])  # Cache with no parameters (global stats)
    def get_user_statistics(self) -> Dict[str, int]:
        """
        Get user statistics using efficient database aggregation functions
        """
        repository_metrics.increment_query_count()
        
        # Use database-level aggregation for better performance
        stats_query = self.db.query(
            func.count(User.id).label('total_users'),
            func.sum(case((User.role == UserRole.SUPER_USER, 1), else_=0)).label('super_users'),
            func.sum(case((User.role == UserRole.ADMIN_USER, 1), else_=0)).label('admin_users'),
            func.sum(case((User.role == UserRole.GENERAL_USER, 1), else_=0)).label('general_users'),
            func.sum(case((User.is_active == True, 1), else_=0)).label('active_users'),
            func.sum(case((User.is_active == False, 1), else_=0)).label('inactive_users')
        ).first()

        # Get point statistics
        point_stats = self.db.query(
            func.coalesce(func.sum(UserPoint.total_points), 0).label('total_points_distributed'),
            func.count(UserPoint.user_id).label('users_with_points')
        ).first()

        # Get recent signups (last 7 days)
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        recent_signups = self.db.query(func.count(User.id)).filter(
            User.created_at >= seven_days_ago
        ).scalar()

        return {
            'total_users': stats_query.total_users or 0,
            'super_users': stats_query.super_users or 0,
            'admin_users': stats_query.admin_users or 0,
            'general_users': stats_query.general_users or 0,
            'active_users': stats_query.active_users or 0,
            'inactive_users': stats_query.inactive_users or 0,
            'total_points_distributed': point_stats.total_points_distributed or 0,
            'users_with_points': point_stats.users_with_points or 0,
            'recent_signups': recent_signups or 0
        }

    def get_user_with_details(self, user_id: str) -> Optional[User]:
        """
        Get a single user with all related data using optimized joins
        """
        return self.db.query(User).options(
            selectinload(User.user_points),
            selectinload(User.provider_permissions),
            selectinload(User.sent_transactions),
            selectinload(User.received_transactions)
            # Note: sessions and activity_logs relationships disabled until tables are created
        ).filter(User.id == user_id).first()

    def get_users_by_creator(self, creator_email: str, creator_role: UserRole) -> List[User]:
        """
        Get users created by a specific creator with optimized loading
        """
        created_by_str = f"{creator_role.value}: {creator_email}"
        
        return self.db.query(User).options(
            selectinload(User.user_points),
            selectinload(User.provider_permissions)
        ).filter(User.created_by == created_by_str).all()

    def get_active_users_in_period(self, days: int = 7) -> List[User]:
        """
        Get users who have been active in the specified period
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # Users with recent transactions
        active_user_ids = self.db.query(PointTransaction.giver_id).filter(
            PointTransaction.created_at >= cutoff_date
        ).union(
            self.db.query(PointTransaction.receiver_id).filter(
                PointTransaction.created_at >= cutoff_date
            )
        ).distinct().subquery()

        return self.db.query(User).options(
            selectinload(User.user_points),
            selectinload(User.provider_permissions)
        ).filter(User.id.in_(active_user_ids)).all()

    def _apply_filters(self, query, filters: UserFilters):
        """Apply filters to the query"""
        if filters.search:
            search_pattern = f"%{filters.search}%"
            query = query.filter(
                or_(
                    User.username.ilike(search_pattern),
                    User.email.ilike(search_pattern)
                )
            )

        if filters.role is not None:
            query = query.filter(User.role == filters.role)

        if filters.is_active is not None:
            query = query.filter(User.is_active == filters.is_active)

        if filters.created_after:
            query = query.filter(User.created_at >= filters.created_after)

        if filters.created_before:
            query = query.filter(User.created_at <= filters.created_before)

        if filters.has_points is not None:
            if filters.has_points:
                # Users with points > 0
                query = query.join(UserPoint).filter(UserPoint.current_points > 0)
            else:
                # Users with no points or 0 points
                query = query.outerjoin(UserPoint).filter(
                    or_(
                        UserPoint.current_points == 0,
                        UserPoint.current_points.is_(None)
                    )
                )

        if filters.activity_status:
            # Filter by activity status (Active/Inactive based on recent transactions)
            seven_days_ago = datetime.utcnow() - timedelta(days=7)
            
            if filters.activity_status == "Active":
                # Users with recent transactions
                active_user_ids = self.db.query(PointTransaction.giver_id).filter(
                    PointTransaction.created_at >= seven_days_ago
                ).union(
                    self.db.query(PointTransaction.receiver_id).filter(
                        PointTransaction.created_at >= seven_days_ago
                    )
                ).distinct().subquery()
                
                query = query.filter(User.id.in_(active_user_ids))
            
            elif filters.activity_status == "Inactive":
                # Users without recent transactions
                active_user_ids = self.db.query(PointTransaction.giver_id).filter(
                    PointTransaction.created_at >= seven_days_ago
                ).union(
                    self.db.query(PointTransaction.receiver_id).filter(
                        PointTransaction.created_at >= seven_days_ago
                    )
                ).distinct().subquery()
                
                query = query.filter(~User.id.in_(active_user_ids))

        return query

    def _apply_sorting(self, query, sort_config: SortConfig):
        """Apply sorting to the query"""
        sort_column = None
        
        if sort_config.sort_by == "username":
            sort_column = User.username
        elif sort_config.sort_by == "email":
            sort_column = User.email
        elif sort_config.sort_by == "role":
            sort_column = User.role
        elif sort_config.sort_by == "created_at":
            sort_column = User.created_at
        elif sort_config.sort_by == "updated_at":
            sort_column = User.updated_at
        elif sort_config.sort_by == "is_active":
            sort_column = User.is_active
        elif sort_config.sort_by == "points":
            # Join with UserPoint for sorting by points
            query = query.outerjoin(UserPoint)
            sort_column = UserPoint.current_points
        else:
            # Default to created_at
            sort_column = User.created_at

        if sort_config.sort_order.lower() == "asc":
            query = query.order_by(asc(sort_column))
        else:
            query = query.order_by(desc(sort_column))

        return query

    def bulk_update_users(self, user_updates: List[Dict[str, Any]]) -> int:
        """
        Perform bulk updates on users for better performance
        Returns number of updated users
        """
        updated_count = 0
        
        for update_data in user_updates:
            user_id = update_data.pop('id', None)
            if not user_id:
                continue
                
            result = self.db.query(User).filter(User.id == user_id).update(
                update_data,
                synchronize_session=False
            )
            updated_count += result

        self.db.commit()
        return updated_count

    def get_user_activity_summary(self, user_id: str, days: int = 30) -> Dict[str, Any]:
        """
        Get user activity summary for the specified period
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # Transaction counts
        sent_transactions = self.db.query(func.count(PointTransaction.id)).filter(
            PointTransaction.giver_id == user_id,
            PointTransaction.created_at >= cutoff_date
        ).scalar()

        received_transactions = self.db.query(func.count(PointTransaction.id)).filter(
            PointTransaction.receiver_id == user_id,
            PointTransaction.created_at >= cutoff_date
        ).scalar()

        # Points summary
        points_sent = self.db.query(func.coalesce(func.sum(PointTransaction.points), 0)).filter(
            PointTransaction.giver_id == user_id,
            PointTransaction.created_at >= cutoff_date
        ).scalar()

        points_received = self.db.query(func.coalesce(func.sum(PointTransaction.points), 0)).filter(
            PointTransaction.receiver_id == user_id,
            PointTransaction.created_at >= cutoff_date
        ).scalar()

        return {
            'period_days': days,
            'sent_transactions': sent_transactions or 0,
            'received_transactions': received_transactions or 0,
            'total_transactions': (sent_transactions or 0) + (received_transactions or 0),
            'points_sent': points_sent or 0,
            'points_received': points_received or 0,
            'net_points': (points_received or 0) - (points_sent or 0)
        }

    def get_users_with_advanced_filters(
        self,
        page: int = 1,
        limit: int = 25,
        search: Optional[str] = None,
        role: Optional[UserRole] = None,
        is_active: Optional[bool] = None,
        created_after: Optional[datetime] = None,
        created_before: Optional[datetime] = None,
        has_points: Optional[bool] = None,
        activity_status: Optional[str] = None,
        min_points: Optional[int] = None,
        max_points: Optional[int] = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
        include_suppliers: bool = True
    ) -> Tuple[List[User], int, Dict[str, Any]]:
        """
        Advanced user filtering with multiple criteria and metadata
        Returns tuple of (users, total_count, metadata)
        """
        filters = UserFilters(
            search=search,
            role=role,
            is_active=is_active,
            created_after=created_after,
            created_before=created_before,
            has_points=has_points,
            activity_status=activity_status
        )
        
        sort_config = SortConfig(sort_by=sort_by, sort_order=sort_order)
        
        # Base query with conditional eager loading
        query = self.db.query(User)
        
        if include_suppliers:
            query = query.options(
                selectinload(User.user_points),
                selectinload(User.provider_permissions)
                # Note: sessions relationship disabled until table is created
            )
        else:
            query = query.options(
                selectinload(User.user_points)
            )

        # Apply filters
        query = self._apply_filters(query, filters)
        
        # Apply point range filters
        if min_points is not None or max_points is not None:
            query = query.join(UserPoint)
            if min_points is not None:
                query = query.filter(UserPoint.current_points >= min_points)
            if max_points is not None:
                query = query.filter(UserPoint.current_points <= max_points)

        # Get total count and filter metadata
        total = query.count()
        
        # Apply sorting
        query = self._apply_sorting(query, sort_config)

        # Apply pagination
        users = query.offset((page - 1) * limit).limit(limit).all()

        # Generate metadata
        metadata = self._generate_filter_metadata(filters, total, page, limit)

        return users, total, metadata

    def get_users_by_role_hierarchy(
        self,
        requesting_user_role: UserRole,
        requesting_user_email: str,
        page: int = 1,
        limit: int = 25
    ) -> Tuple[List[User], int]:
        """
        Get users based on role hierarchy permissions
        """
        query = self.db.query(User).options(
            selectinload(User.user_points),
            selectinload(User.provider_permissions)
        )

        if requesting_user_role == UserRole.SUPER_USER:
            # Super users can see all users
            pass
        elif requesting_user_role == UserRole.ADMIN_USER:
            # Admin users can see users they created
            created_by_str = f"{requesting_user_role.value}: {requesting_user_email}"
            query = query.filter(User.created_by == created_by_str)
        else:
            # General users can only see themselves
            query = query.filter(User.email == requesting_user_email)

        total = query.count()
        users = query.offset((page - 1) * limit).limit(limit).all()

        return users, total

    def build_dynamic_query(self, query_params: Dict[str, Any]) -> Tuple[List[User], int]:
        """
        Build dynamic query based on arbitrary parameters
        """
        query = self.db.query(User).options(
            selectinload(User.user_points),
            selectinload(User.provider_permissions)
        )

        # Dynamic filter building
        conditions = []

        # Text search across multiple fields
        if query_params.get('q'):
            search_term = f"%{query_params['q']}%"
            conditions.append(
                or_(
                    User.username.ilike(search_term),
                    User.email.ilike(search_term),
                    User.id.ilike(search_term)
                )
            )

        # Role filtering with multiple values
        if query_params.get('roles'):
            roles = query_params['roles']
            if isinstance(roles, str):
                roles = [roles]
            conditions.append(User.role.in_(roles))

        # Date range filtering
        if query_params.get('date_from'):
            conditions.append(User.created_at >= query_params['date_from'])
        
        if query_params.get('date_to'):
            conditions.append(User.created_at <= query_params['date_to'])

        # Status filtering
        if 'active' in query_params:
            conditions.append(User.is_active == query_params['active'])

        # Apply all conditions
        if conditions:
            query = query.filter(and_(*conditions))

        # Handle sorting
        sort_field = query_params.get('sort', 'created_at')
        sort_direction = query_params.get('order', 'desc')
        
        sort_config = SortConfig(sort_by=sort_field, sort_order=sort_direction)
        query = self._apply_sorting(query, sort_config)

        # Pagination
        page = int(query_params.get('page', 1))
        limit = int(query_params.get('limit', 25))
        
        total = query.count()
        users = query.offset((page - 1) * limit).limit(limit).all()

        return users, total

    def get_user_statistics_by_filters(self, filters: UserFilters) -> Dict[str, Any]:
        """
        Get statistics for filtered user set
        """
        query = self.db.query(User)
        query = self._apply_filters(query, filters)

        # Basic counts
        total_filtered = query.count()
        
        # Role distribution
        role_stats = query.with_entities(
            User.role,
            func.count(User.id).label('count')
        ).group_by(User.role).all()

        # Activity distribution
        active_count = query.filter(User.is_active == True).count()
        inactive_count = query.filter(User.is_active == False).count()

        # Point statistics for filtered users
        point_query = query.join(UserPoint, isouter=True)
        point_stats = point_query.with_entities(
            func.coalesce(func.sum(UserPoint.current_points), 0).label('total_points'),
            func.coalesce(func.avg(UserPoint.current_points), 0).label('avg_points'),
            func.count(case((UserPoint.current_points > 0, 1))).label('users_with_points')
        ).first()

        return {
            'total_filtered': total_filtered,
            'role_distribution': {role: count for role, count in role_stats},
            'active_users': active_count,
            'inactive_users': inactive_count,
            'total_points': float(point_stats.total_points or 0),
            'average_points': float(point_stats.avg_points or 0),
            'users_with_points': point_stats.users_with_points or 0
        }

    def _generate_filter_metadata(
        self, 
        filters: UserFilters, 
        total: int, 
        page: int, 
        limit: int
    ) -> Dict[str, Any]:
        """Generate metadata about the current filter state"""
        total_pages = (total + limit - 1) // limit
        
        return {
            'pagination': {
                'page': page,
                'limit': limit,
                'total': total,
                'total_pages': total_pages,
                'has_next': page < total_pages,
                'has_prev': page > 1
            },
            'filters_applied': {
                'search': filters.search is not None,
                'role': filters.role is not None,
                'is_active': filters.is_active is not None,
                'date_range': filters.created_after is not None or filters.created_before is not None,
                'has_points': filters.has_points is not None,
                'activity_status': filters.activity_status is not None
            },
            'query_performance': {
                'total_results': total,
                'page_size': limit,
                'results_on_page': min(limit, max(0, total - (page - 1) * limit))
            }
        }

    def optimize_query_for_large_datasets(
        self,
        page: int,
        limit: int,
        filters: UserFilters,
        sort_config: SortConfig,
        use_cursor_pagination: bool = False,
        cursor_id: Optional[str] = None
    ) -> Tuple[List[User], int, Optional[str]]:
        """
        Optimized query for large datasets with optional cursor-based pagination
        Returns tuple of (users, total_count, next_cursor)
        """
        if use_cursor_pagination and cursor_id:
            # Cursor-based pagination for better performance on large datasets
            query = self.db.query(User).options(
                selectinload(User.user_points)
            )
            
            # Apply filters
            query = self._apply_filters(query, filters)
            
            # Apply cursor condition
            if sort_config.sort_order.lower() == "desc":
                query = query.filter(User.id < cursor_id)
            else:
                query = query.filter(User.id > cursor_id)
            
            # Apply sorting
            query = self._apply_sorting(query, sort_config)
            
            # Get results
            users = query.limit(limit + 1).all()  # +1 to check if there are more results
            
            has_more = len(users) > limit
            if has_more:
                users = users[:limit]
                next_cursor = users[-1].id if users else None
            else:
                next_cursor = None
            
            # For cursor pagination, we don't calculate total count for performance
            return users, -1, next_cursor
        
        else:
            # Standard offset-based pagination with optimizations
            query = self.db.query(User).options(
                selectinload(User.user_points)
            )
            
            # Apply filters
            query = self._apply_filters(query, filters)
            
            # Use window functions for better performance on large datasets
            if page > 100:  # For very deep pagination, use different strategy
                # Use a more efficient approach for deep pagination
                query = query.order_by(User.id)  # Use indexed column for consistent ordering
                
                # Get total count with a separate optimized query
                count_query = self.db.query(func.count(User.id))
                count_query = self._apply_filters(count_query, filters)
                total = count_query.scalar()
                
                # Apply pagination
                users = query.offset((page - 1) * limit).limit(limit).all()
            else:
                # Standard approach for reasonable pagination depths
                total = query.count()
                query = self._apply_sorting(query, sort_config)
                users = query.offset((page - 1) * limit).limit(limit).all()
            
            return users, total, None