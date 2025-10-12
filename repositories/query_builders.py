from typing import List, Dict, Any, Optional, Union
from sqlalchemy.orm import Query
from sqlalchemy import and_, or_, func, case, text
from datetime import datetime, timedelta
from models import User, UserPoint, PointTransaction, UserProviderPermission, UserRole
from dataclasses import dataclass


@dataclass
class QueryBuilder:
    """Advanced query builder for complex user queries"""
    
    @staticmethod
    def build_search_query(
        base_query: Query,
        search_term: str,
        search_fields: List[str] = None
    ) -> Query:
        """
        Build search query across multiple fields with ranking
        """
        if not search_term:
            return base_query
            
        if search_fields is None:
            search_fields = ['username', 'email', 'id']
        
        search_pattern = f"%{search_term}%"
        conditions = []
        
        for field in search_fields:
            if hasattr(User, field):
                column = getattr(User, field)
                conditions.append(column.ilike(search_pattern))
        
        if conditions:
            base_query = base_query.filter(or_(*conditions))
        
        return base_query

    @staticmethod
    def build_date_range_query(
        base_query: Query,
        date_field: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        relative_days: Optional[int] = None
    ) -> Query:
        """
        Build date range queries with relative date support
        """
        if not hasattr(User, date_field):
            return base_query
            
        column = getattr(User, date_field)
        
        if relative_days:
            cutoff_date = datetime.utcnow() - timedelta(days=relative_days)
            base_query = base_query.filter(column >= cutoff_date)
        
        if start_date:
            base_query = base_query.filter(column >= start_date)
            
        if end_date:
            base_query = base_query.filter(column <= end_date)
        
        return base_query

    @staticmethod
    def build_point_range_query(
        base_query: Query,
        min_points: Optional[int] = None,
        max_points: Optional[int] = None,
        point_type: str = "current"  # "current", "total", "used"
    ) -> Query:
        """
        Build point range queries with different point types
        """
        base_query = base_query.join(UserPoint, isouter=True)
        
        point_column = None
        if point_type == "current":
            point_column = UserPoint.current_points
        elif point_type == "total":
            point_column = UserPoint.total_points
        elif point_type == "used":
            point_column = UserPoint.total_used_points
        
        if point_column is not None:
            if min_points is not None:
                base_query = base_query.filter(
                    func.coalesce(point_column, 0) >= min_points
                )
            if max_points is not None:
                base_query = base_query.filter(
                    func.coalesce(point_column, 0) <= max_points
                )
        
        return base_query

    @staticmethod
    def build_activity_query(
        base_query: Query,
        activity_period_days: int = 7,
        activity_type: str = "any"  # "any", "sent", "received"
    ) -> Query:
        """
        Build activity-based queries
        """
        cutoff_date = datetime.utcnow() - timedelta(days=activity_period_days)
        
        if activity_type == "sent":
            active_users = base_query.session.query(PointTransaction.giver_id).filter(
                PointTransaction.created_at >= cutoff_date
            ).distinct().subquery()
            base_query = base_query.filter(User.id.in_(active_users))
            
        elif activity_type == "received":
            active_users = base_query.session.query(PointTransaction.receiver_id).filter(
                PointTransaction.created_at >= cutoff_date
            ).distinct().subquery()
            base_query = base_query.filter(User.id.in_(active_users))
            
        else:  # "any"
            active_users_sent = base_query.session.query(PointTransaction.giver_id).filter(
                PointTransaction.created_at >= cutoff_date
            )
            active_users_received = base_query.session.query(PointTransaction.receiver_id).filter(
                PointTransaction.created_at >= cutoff_date
            )
            active_users = active_users_sent.union(active_users_received).distinct().subquery()
            base_query = base_query.filter(User.id.in_(active_users))
        
        return base_query

    @staticmethod
    def build_supplier_query(
        base_query: Query,
        supplier_names: List[str] = None,
        has_suppliers: Optional[bool] = None,
        min_suppliers: Optional[int] = None
    ) -> Query:
        """
        Build supplier-based queries
        """
        if supplier_names:
            base_query = base_query.join(UserProviderPermission).filter(
                UserProviderPermission.provider_name.in_(supplier_names)
            )
        
        if has_suppliers is not None:
            if has_suppliers:
                base_query = base_query.join(UserProviderPermission)
            else:
                base_query = base_query.outerjoin(UserProviderPermission).filter(
                    UserProviderPermission.id.is_(None)
                )
        
        if min_suppliers is not None:
            supplier_counts = base_query.session.query(
                UserProviderPermission.user_id,
                func.count(UserProviderPermission.id).label('supplier_count')
            ).group_by(UserProviderPermission.user_id).having(
                func.count(UserProviderPermission.id) >= min_suppliers
            ).subquery()
            
            base_query = base_query.filter(User.id.in_(
                base_query.session.query(supplier_counts.c.user_id)
            ))
        
        return base_query

    @staticmethod
    def build_complex_filter_query(
        base_query: Query,
        filter_conditions: List[Dict[str, Any]]
    ) -> Query:
        """
        Build complex queries from filter condition dictionaries
        
        Example filter_conditions:
        [
            {"field": "role", "operator": "in", "value": ["admin_user", "general_user"]},
            {"field": "created_at", "operator": ">=", "value": datetime(2024, 1, 1)},
            {"field": "current_points", "operator": ">", "value": 1000}
        ]
        """
        conditions = []
        
        for filter_condition in filter_conditions:
            field = filter_condition.get('field')
            operator = filter_condition.get('operator', '==')
            value = filter_condition.get('value')
            
            if not field or value is None:
                continue
            
            # Handle User model fields
            if hasattr(User, field):
                column = getattr(User, field)
                condition = QueryBuilder._build_condition(column, operator, value)
                if condition is not None:
                    conditions.append(condition)
            
            # Handle UserPoint fields
            elif field in ['current_points', 'total_points', 'total_used_points']:
                base_query = base_query.join(UserPoint, isouter=True)
                column = getattr(UserPoint, field)
                condition = QueryBuilder._build_condition(column, operator, value)
                if condition is not None:
                    conditions.append(condition)
        
        if conditions:
            base_query = base_query.filter(and_(*conditions))
        
        return base_query

    @staticmethod
    def _build_condition(column, operator: str, value):
        """Build individual filter condition"""
        try:
            if operator == '==':
                return column == value
            elif operator == '!=':
                return column != value
            elif operator == '>':
                return column > value
            elif operator == '>=':
                return column >= value
            elif operator == '<':
                return column < value
            elif operator == '<=':
                return column <= value
            elif operator == 'in':
                return column.in_(value if isinstance(value, list) else [value])
            elif operator == 'not_in':
                return ~column.in_(value if isinstance(value, list) else [value])
            elif operator == 'like':
                return column.like(f"%{value}%")
            elif operator == 'ilike':
                return column.ilike(f"%{value}%")
            elif operator == 'is_null':
                return column.is_(None)
            elif operator == 'is_not_null':
                return column.isnot(None)
            else:
                return None
        except Exception:
            return None


class AdvancedSorting:
    """Advanced sorting utilities for user queries"""
    
    @staticmethod
    def apply_multi_field_sort(
        query: Query,
        sort_fields: List[Dict[str, str]]
    ) -> Query:
        """
        Apply multi-field sorting
        
        Example sort_fields:
        [
            {"field": "role", "order": "asc"},
            {"field": "created_at", "order": "desc"}
        ]
        """
        order_clauses = []
        
        for sort_field in sort_fields:
            field_name = sort_field.get('field')
            order = sort_field.get('order', 'asc').lower()
            
            column = None
            if hasattr(User, field_name):
                column = getattr(User, field_name)
            elif field_name in ['current_points', 'total_points', 'total_used_points']:
                query = query.join(UserPoint, isouter=True)
                column = getattr(UserPoint, field_name)
            
            if column is not None:
                if order == 'desc':
                    order_clauses.append(column.desc())
                else:
                    order_clauses.append(column.asc())
        
        if order_clauses:
            query = query.order_by(*order_clauses)
        
        return query

    @staticmethod
    def apply_custom_sort(
        query: Query,
        sort_expression: str
    ) -> Query:
        """
        Apply custom sorting using SQL expressions
        
        Example: "CASE WHEN role = 'super_user' THEN 1 ELSE 2 END, created_at DESC"
        """
        try:
            query = query.order_by(text(sort_expression))
        except Exception:
            # Fallback to default sorting if custom expression fails
            query = query.order_by(User.created_at.desc())
        
        return query


class QueryOptimizer:
    """Query optimization utilities"""
    
    @staticmethod
    def add_query_hints(query: Query, hints: List[str]) -> Query:
        """Add database-specific query hints for optimization"""
        # This would be database-specific implementation
        # For SQLite, we can add PRAGMA statements
        # For PostgreSQL, we might use query hints
        # For now, return the query as-is
        return query

    @staticmethod
    def optimize_for_count(query: Query) -> Query:
        """Optimize query specifically for count operations"""
        # Remove unnecessary joins and selections for count queries
        return query.with_entities(func.count(User.id))

    @staticmethod
    def add_index_hints(query: Query, index_names: List[str]) -> Query:
        """Add index hints to guide query planner"""
        # Database-specific implementation would go here
        return query