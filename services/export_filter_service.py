"""
Export Filter Service

Handles query building and filtering for export operations including:
- Hotel data filtering with multiple criteria
- Provider mapping filtering
- Supplier summary filtering
- Result count estimation
- Query optimization
"""

from typing import List, Optional
from sqlalchemy.orm import Session, Query, joinedload
from sqlalchemy import func, and_, or_
from datetime import datetime
import logging

from models import Hotel, Location, ProviderMapping, Contact, SupplierSummary
from export_schemas import HotelExportFilters, MappingExportFilters, SupplierSummaryFilters

# Configure logging
logger = logging.getLogger(__name__)


class ExportFilterService:
    """
    Service for building filtered queries for export operations.
    
    Handles:
    - Hotel query building with multiple filter types
    - Provider mapping query building
    - Supplier summary query building
    - Result count estimation
    - Query optimization with selective loading
    """
    
    def __init__(self, db: Session):
        """
        Initialize ExportFilterService with database session.
        
        Args:
            db: SQLAlchemy database session
        """
        self.db = db
        logger.info("ExportFilterService initialized")

    def build_hotel_query(
        self,
        filters: HotelExportFilters,
        allowed_suppliers: List[str],
        include_locations: bool = True,
        include_contacts: bool = True,
        include_mappings: bool = True
    ) -> Query:
        """
        Build optimized query for hotel export with filters.
        
        Applies filters for:
        - Suppliers (provider names)
        - Countries (country codes)
        - Ratings (min/max range)
        - Dates (created_at/updated_at range)
        - ITTIDs (specific hotel IDs)
        - Property types
        
        Args:
            filters: HotelExportFilters object with filter criteria
            allowed_suppliers: List of supplier names user has access to
            include_locations: Whether to eager load location data
            include_contacts: Whether to eager load contact data
            include_mappings: Whether to eager load provider mappings
            
        Returns:
            SQLAlchemy Query object with filters applied
            
        Raises:
            Exception: If query building fails
        """
        logger.info("Building hotel query with filters")
        logger.debug(f"Filters: suppliers={filters.suppliers}, countries={filters.country_codes}, "
                    f"ratings={filters.min_rating}-{filters.max_rating}, "
                    f"dates={filters.date_from} to {filters.date_to}")
        
        try:
            # Start with base query
            query = self.db.query(Hotel)
        
        # Apply eager loading for relationships if requested
        if include_locations:
            query = query.options(joinedload(Hotel.locations))
            logger.debug("Added eager loading for locations")
        
        if include_contacts:
            query = query.options(joinedload(Hotel.contacts))
            logger.debug("Added eager loading for contacts")
        
        if include_mappings:
            query = query.options(joinedload(Hotel.provider_mappings))
            logger.debug("Added eager loading for provider_mappings")
        
        # Filter by suppliers (required - user must have access)
        # Join with provider_mappings to filter by supplier
        query = query.join(Hotel.provider_mappings)
        
        # Determine which suppliers to filter by
        if filters.suppliers and len(filters.suppliers) > 0:
            # User specified specific suppliers - use intersection with allowed
            requested_suppliers = set(filters.suppliers)
            allowed_set = set(allowed_suppliers)
            effective_suppliers = list(requested_suppliers.intersection(allowed_set))
            
            if not effective_suppliers:
                logger.warning("No overlap between requested and allowed suppliers")
                # Return empty query
                query = query.filter(Hotel.ittid == None)
                return query
            
            logger.debug(f"Filtering by {len(effective_suppliers)} suppliers: {effective_suppliers}")
            query = query.filter(ProviderMapping.provider_name.in_(effective_suppliers))
        else:
            # No specific suppliers requested - use all allowed
            logger.debug(f"Filtering by all {len(allowed_suppliers)} allowed suppliers")
            query = query.filter(ProviderMapping.provider_name.in_(allowed_suppliers))
        
        # Filter by specific ITTIDs if provided
        if filters.ittids and len(filters.ittids) > 0:
            logger.debug(f"Filtering by {len(filters.ittids)} specific ITTIDs")
            query = query.filter(Hotel.ittid.in_(filters.ittids))
        
        # Filter by country codes if provided
        if filters.country_codes and len(filters.country_codes) > 0:
            logger.debug(f"Filtering by country codes: {filters.country_codes}")
            # Join with locations table to filter by country
            query = query.join(Hotel.locations).filter(
                Location.country_code.in_(filters.country_codes)
            )
        
        # Filter by rating range if provided
        if filters.min_rating is not None:
            logger.debug(f"Filtering by min_rating >= {filters.min_rating}")
            # Convert rating to float for comparison
            query = query.filter(
                func.cast(Hotel.rating, func.Float) >= filters.min_rating
            )
        
        if filters.max_rating is not None:
            logger.debug(f"Filtering by max_rating <= {filters.max_rating}")
            query = query.filter(
                func.cast(Hotel.rating, func.Float) <= filters.max_rating
            )
        
        # Filter by property types if provided
        if filters.property_types and len(filters.property_types) > 0:
            logger.debug(f"Filtering by property types: {filters.property_types}")
            query = query.filter(Hotel.property_type.in_(filters.property_types))
        
        # Filter by date range if provided
        if filters.date_from is not None:
            logger.debug(f"Filtering by date_from >= {filters.date_from}")
            query = query.filter(Hotel.updated_at >= filters.date_from)
        
        if filters.date_to is not None:
            logger.debug(f"Filtering by date_to <= {filters.date_to}")
            query = query.filter(Hotel.updated_at <= filters.date_to)
        
        # Remove duplicates (hotels may appear multiple times due to joins)
        query = query.distinct()
        
            # Apply pagination
            offset = (filters.page - 1) * filters.page_size
            query = query.offset(offset).limit(filters.page_size)
            
            logger.info(f"Hotel query built successfully with pagination: page={filters.page}, size={filters.page_size}")
            
            return query
            
        except Exception as e:
            logger.error(f"Error building hotel query: {str(e)}")
            raise Exception(f"Failed to build hotel query: {str(e)}")

    def build_mapping_query(
        self,
        filters: MappingExportFilters,
        allowed_suppliers: List[str]
    ) -> Query:
        """
        Build query for provider mapping export with filters.
        
        Applies filters for:
        - Suppliers (provider names)
        - ITTIDs (specific hotel IDs)
        - Dates (created_at/updated_at range)
        
        Args:
            filters: MappingExportFilters object with filter criteria
            allowed_suppliers: List of supplier names user has access to
            
        Returns:
            SQLAlchemy Query object with filters applied
            
        Raises:
            Exception: If query building fails
        """
        logger.info("Building mapping query with filters")
        logger.debug(f"Filters: suppliers={filters.suppliers}, ittids={filters.ittids}, "
                    f"dates={filters.date_from} to {filters.date_to}")
        
        try:
            # Start with base query - eager load hotel relationship
            query = self.db.query(ProviderMapping).options(
                joinedload(ProviderMapping.hotel)
            )
        
        # Filter by suppliers
        if filters.suppliers and len(filters.suppliers) > 0:
            # User specified specific suppliers - use intersection with allowed
            requested_suppliers = set(filters.suppliers)
            allowed_set = set(allowed_suppliers)
            effective_suppliers = list(requested_suppliers.intersection(allowed_set))
            
            if not effective_suppliers:
                logger.warning("No overlap between requested and allowed suppliers")
                # Return empty query
                query = query.filter(ProviderMapping.id == None)
                return query
            
            logger.debug(f"Filtering by {len(effective_suppliers)} suppliers: {effective_suppliers}")
            query = query.filter(ProviderMapping.provider_name.in_(effective_suppliers))
        else:
            # No specific suppliers requested - use all allowed
            logger.debug(f"Filtering by all {len(allowed_suppliers)} allowed suppliers")
            query = query.filter(ProviderMapping.provider_name.in_(allowed_suppliers))
        
        # Filter by specific ITTIDs if provided
        if filters.ittids and len(filters.ittids) > 0:
            logger.debug(f"Filtering by {len(filters.ittids)} specific ITTIDs")
            query = query.filter(ProviderMapping.ittid.in_(filters.ittids))
        
        # Filter by date range if provided
        if filters.date_from is not None:
            logger.debug(f"Filtering by date_from >= {filters.date_from}")
            query = query.filter(ProviderMapping.updated_at >= filters.date_from)
        
        if filters.date_to is not None:
            logger.debug(f"Filtering by date_to <= {filters.date_to}")
            query = query.filter(ProviderMapping.updated_at <= filters.date_to)
        
            # Order by provider_name and ittid for consistent results
            query = query.order_by(ProviderMapping.provider_name, ProviderMapping.ittid)
            
            logger.info("Mapping query built successfully")
            
            return query
            
        except Exception as e:
            logger.error(f"Error building mapping query: {str(e)}")
            raise Exception(f"Failed to build mapping query: {str(e)}")

    def build_supplier_summary_query(
        self,
        filters: SupplierSummaryFilters,
        allowed_suppliers: Optional[List[str]] = None
    ) -> Query:
        """
        Build query for supplier summary export.
        
        Applies filters for:
        - Suppliers (specific supplier names)
        
        Args:
            filters: SupplierSummaryFilters object with filter criteria
            allowed_suppliers: Optional list of supplier names user has access to
            
        Returns:
            SQLAlchemy Query object with filters applied
            
        Raises:
            Exception: If query building fails
        """
        logger.info("Building supplier summary query with filters")
        logger.debug(f"Filters: suppliers={filters.suppliers}, "
                    f"include_country_breakdown={filters.include_country_breakdown}")
        
        try:
            # Start with base query
            query = self.db.query(SupplierSummary)
        
        # Filter by suppliers if provided
        if filters.suppliers and len(filters.suppliers) > 0:
            if allowed_suppliers:
                # User specified specific suppliers - use intersection with allowed
                requested_suppliers = set(filters.suppliers)
                allowed_set = set(allowed_suppliers)
                effective_suppliers = list(requested_suppliers.intersection(allowed_set))
                
                if not effective_suppliers:
                    logger.warning("No overlap between requested and allowed suppliers")
                    # Return empty query
                    query = query.filter(SupplierSummary.id == None)
                    return query
                
                logger.debug(f"Filtering by {len(effective_suppliers)} suppliers: {effective_suppliers}")
                query = query.filter(SupplierSummary.provider_name.in_(effective_suppliers))
            else:
                # No allowed suppliers restriction (admin/super user)
                logger.debug(f"Filtering by {len(filters.suppliers)} requested suppliers")
                query = query.filter(SupplierSummary.provider_name.in_(filters.suppliers))
        elif allowed_suppliers:
            # No specific suppliers requested but user has restrictions
            logger.debug(f"Filtering by all {len(allowed_suppliers)} allowed suppliers")
            query = query.filter(SupplierSummary.provider_name.in_(allowed_suppliers))
        
            # Order by provider_name for consistent results
            query = query.order_by(SupplierSummary.provider_name)
            
            logger.info("Supplier summary query built successfully")
            
            return query
            
        except Exception as e:
            logger.error(f"Error building supplier summary query: {str(e)}")
            raise Exception(f"Failed to build supplier summary query: {str(e)}")

    def estimate_result_count(self, query: Query) -> int:
        """
        Estimate number of results for a query using COUNT.
        
        This is used to determine whether to process export synchronously
        or asynchronously based on result size.
        
        Args:
            query: SQLAlchemy Query object to count results for
            
        Returns:
            Estimated number of results
            
        Raises:
            Exception: If count query fails completely
        """
        logger.debug("Estimating result count for query")
        
        try:
            # Remove any limit/offset for counting
            count_query = query.statement.with_only_columns(
                [func.count()]
            ).order_by(None)
            
            count = self.db.execute(count_query).scalar()
            
            logger.info(f"Estimated result count: {count}")
            return count
            
        except Exception as e:
            logger.error(f"Error estimating result count: {str(e)}")
            # Fall back to slower count method
            try:
                count = query.count()
                logger.info(f"Fallback result count: {count}")
                return count
            except Exception as e2:
                logger.error(f"Error in fallback count: {str(e2)}")
                # If all else fails, raise exception
                raise Exception(f"Failed to estimate result count: {str(e2)}")

    def get_country_breakdown(
        self,
        allowed_suppliers: List[str]
    ) -> dict:
        """
        Get hotel count breakdown by country for each supplier.
        
        Used for supplier summary exports with country breakdown.
        
        Args:
            allowed_suppliers: List of supplier names to include
            
        Returns:
            Dictionary mapping supplier -> country_code -> count
        """
        logger.info("Building country breakdown for supplier summary")
        
        try:
            # Query to get counts grouped by supplier and country
            results = self.db.query(
                ProviderMapping.provider_name,
                Location.country_code,
                func.count(func.distinct(Hotel.ittid)).label('hotel_count')
            ).join(
                Hotel, ProviderMapping.ittid == Hotel.ittid
            ).join(
                Location, Hotel.ittid == Location.ittid
            ).filter(
                ProviderMapping.provider_name.in_(allowed_suppliers),
                Location.country_code.isnot(None)
            ).group_by(
                ProviderMapping.provider_name,
                Location.country_code
            ).all()
            
            # Build nested dictionary structure
            breakdown = {}
            for provider_name, country_code, count in results:
                if provider_name not in breakdown:
                    breakdown[provider_name] = {}
                breakdown[provider_name][country_code] = count
            
            logger.info(f"Country breakdown built for {len(breakdown)} suppliers")
            return breakdown
            
        except Exception as e:
            logger.error(f"Error building country breakdown: {str(e)}")
            return {}

    def validate_filters(self, filters) -> tuple[bool, Optional[str]]:
        """
        Validate filter parameters for consistency and correctness.
        
        Validates:
        - Date ranges (from < to, not in future)
        - Rating ranges (0-5, min <= max)
        - Pagination parameters
        - Maximum export size (100,000 records)
        - Empty list validations
        
        Args:
            filters: Filter object (HotelExportFilters, MappingExportFilters, etc.)
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        logger.debug("Validating filters")
        
        try:
            # Check date range validity
            if hasattr(filters, 'date_from') and hasattr(filters, 'date_to'):
                if filters.date_from and filters.date_to:
                    if filters.date_from > filters.date_to:
                        return False, "date_from must be before date_to"
                
                # Check dates are not in the future
                current_time = datetime.utcnow()
                if filters.date_from and filters.date_from > current_time:
                    return False, "date_from cannot be in the future"
                if filters.date_to and filters.date_to > current_time:
                    return False, "date_to cannot be in the future"
            
            # Check rating range validity
            if hasattr(filters, 'min_rating') and hasattr(filters, 'max_rating'):
                if filters.min_rating is not None:
                    if filters.min_rating < 0 or filters.min_rating > 5:
                        return False, "min_rating must be between 0 and 5"
                
                if filters.max_rating is not None:
                    if filters.max_rating < 0 or filters.max_rating > 5:
                        return False, "max_rating must be between 0 and 5"
                    
                    if filters.min_rating is not None and filters.max_rating < filters.min_rating:
                        return False, "max_rating must be greater than or equal to min_rating"
            
            # Check pagination validity
            if hasattr(filters, 'page') and hasattr(filters, 'page_size'):
                if filters.page < 1:
                    return False, "page must be >= 1"
                if filters.page_size < 1 or filters.page_size > 10000:
                    return False, "page_size must be between 1 and 10000"
            
            # Check maximum export size
            if hasattr(filters, 'max_records'):
                if filters.max_records is not None:
                    if filters.max_records < 1:
                        return False, "max_records must be at least 1"
                    if filters.max_records > 100000:
                        return False, "max_records cannot exceed 100,000. Please use more specific filters or pagination."
            
            # Check that list filters are not empty if provided
            if hasattr(filters, 'suppliers'):
                if filters.suppliers is not None and len(filters.suppliers) == 0:
                    return False, "suppliers list cannot be empty if provided"
            
            if hasattr(filters, 'country_codes'):
                if filters.country_codes is not None and len(filters.country_codes) == 0:
                    return False, "country_codes list cannot be empty if provided"
            
            if hasattr(filters, 'ittids'):
                if filters.ittids is not None and len(filters.ittids) == 0:
                    return False, "ittids list cannot be empty if provided"
            
            if hasattr(filters, 'property_types'):
                if filters.property_types is not None and len(filters.property_types) == 0:
                    return False, "property_types list cannot be empty if provided"
            
            logger.debug("Filters validated successfully")
            return True, None
            
        except Exception as e:
            logger.error(f"Error validating filters: {str(e)}")
            return False, f"Filter validation error: {str(e)}"
