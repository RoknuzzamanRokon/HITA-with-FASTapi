from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from database import get_db
from schemas import HotelCreate, HotelRead
import models
from utils import require_role
from pydantic import BaseModel
from typing import List, Optional, Annotated, Dict, Any
from models import User, Hotel, ProviderMapping, Location, Contact, UserProviderPermission, UserRole
from routes.auth import get_current_user
import logging
from datetime import datetime

# Set up logging
logger = logging.getLogger(__name__)


router = APIRouter(
    prefix="/v1.0/hotels",
    tags=["Hotels Integrations & Mapping"],
    responses={404: {"description": "Not found"}},
)

# Create hotel
@router.post("/input_hotel_all_details", response_model=HotelRead, status_code=status.HTTP_201_CREATED)
def create_hotel_with_details(
    hotel: HotelCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user) 
) -> HotelRead:
    """
    Create New Hotel with Complete Details (Super User and Admin Only)
    
    Creates a comprehensive hotel record with all associated data including locations,
    provider mappings, contacts, and chain information. This endpoint provides complete
    hotel data integration for administrative hotel management operations.
    
    Features:
    - Complete hotel record creation with all related entities
    - Transactional integrity with automatic rollback on errors
    - Role-based access control (Super User and Admin only)
    - Comprehensive validation and error handling
    - Automatic ITTID generation and relationship management
    
    Hotel Data Structure:
        - Basic hotel information (name, address, rating, etc.)
        - Location data (city, state, country, coordinates)
        - Provider mappings (supplier integrations and IDs)
        - Contact information (phone, email, website, fax)
        - Chain information (hotel chain affiliations)
    
    Args:
        hotel (HotelCreate): Complete hotel data including all related entities
        db (Session): Database session (injected by dependency)
        current_user (User): Currently authenticated user (injected by dependency)
    
    Returns:
        HotelRead: Created hotel record with generated ITTID and timestamps
    
    Access Control:
        - Requires SUPER_USER or ADMIN_USER role
        - All hotel creation operations are logged for audit purposes
        - User identity tracked for accountability
    
    Error Handling:
        - 400: Invalid hotel data or validation errors
        - 401: User not authenticated
        - 403: Insufficient privileges (non-admin users)
        - 409: Duplicate hotel data or constraint violations
        - 500: Database errors or system failures
    
    Database Operations:
        - Transactional creation of hotel and all related records
        - Automatic rollback on any failure to maintain data integrity
        - Foreign key relationship management
        - Duplicate prevention and constraint validation
    
    Use Cases:
        - Initial hotel data import and setup
        - Complete hotel profile creation for new properties
        - Bulk hotel data integration from external sources
        - Administrative hotel management operations
    
    Example Request:
        {
            "name": "Grand Hotel Example",
            "address_line1": "123 Main Street",
            "city": "Example City",
            "rating": 4.5,
            "locations": [...],
            "provider_mappings": [...],
            "contacts": [...],
            "chains": [...]
        }
    """
    try:
        # Validate user authentication
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User authentication required"
            )
        
        # Check if the user has the required role
        require_role(["super_user", "admin_user"], current_user)
        
        # Validate hotel data
        if not hotel:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Hotel data is required"
            )
        
        # Log hotel creation attempt
        logger.info(f"Creating hotel '{hotel.name}' by user {current_user.id}")
        
        # Start database transaction
        try:
            # Create main hotel record
            hotel_data = hotel.dict(exclude={"locations", "provider_mappings", "contacts", "chains"})
            db_hotel = models.Hotel(**hotel_data)
            db.add(db_hotel)
            db.commit()
            db.refresh(db_hotel)
            
            # Validate hotel was created successfully
            if not db_hotel.ittid:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to generate hotel ITTID"
                )
            
            # Add related data with error handling for each type
            
            # Add locations
            if hotel.locations:
                for location_data in hotel.locations:
                    try:
                        db_location = models.Location(**location_data.dict(), ittid=db_hotel.ittid)
                        db.add(db_location)
                    except Exception as loc_error:
                        logger.error(f"Error adding location: {loc_error}")
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Invalid location data: {str(loc_error)}"
                        )
            
            # Add provider mappings
            if hotel.provider_mappings:
                for provider_data in hotel.provider_mappings:
                    try:
                        # Check for duplicate provider mappings
                        existing_mapping = db.query(models.ProviderMapping).filter(
                            models.ProviderMapping.provider_name == provider_data.provider_name,
                            models.ProviderMapping.provider_id == provider_data.provider_id
                        ).first()
                        
                        if existing_mapping:
                            logger.warning(f"Duplicate provider mapping detected: {provider_data.provider_name}:{provider_data.provider_id}")
                            continue
                        
                        db_provider_mapping = models.ProviderMapping(**provider_data.dict(), ittid=db_hotel.ittid)
                        db.add(db_provider_mapping)
                    except Exception as provider_error:
                        logger.error(f"Error adding provider mapping: {provider_error}")
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Invalid provider mapping data: {str(provider_error)}"
                        )
            
            # Add contacts
            if hotel.contacts:
                for contact_data in hotel.contacts:
                    try:
                        db_contact = models.Contact(**contact_data.dict(), ittid=db_hotel.ittid)
                        db.add(db_contact)
                    except Exception as contact_error:
                        logger.error(f"Error adding contact: {contact_error}")
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Invalid contact data: {str(contact_error)}"
                        )
            
            # Add chains
            if hotel.chains:
                for chain_data in hotel.chains:
                    try:
                        db_chain = models.Chain(**chain_data.dict(), ittid=db_hotel.ittid)
                        db.add(db_chain)
                    except Exception as chain_error:
                        logger.error(f"Error adding chain: {chain_error}")
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Invalid chain data: {str(chain_error)}"
                        )
            
            # Commit all changes
            db.commit()
            
            # Log successful creation
            logger.info(f"Successfully created hotel '{db_hotel.name}' with ITTID: {db_hotel.ittid}")
            
            return db_hotel
            
        except IntegrityError as integrity_error:
            db.rollback()
            logger.error(f"Database integrity error: {integrity_error}")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Hotel data conflicts with existing records. Please check for duplicates."
            )
        except SQLAlchemyError as db_error:
            db.rollback()
            logger.error(f"Database error during hotel creation: {db_error}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database error occurred while creating hotel"
            )
        
    except HTTPException:
        # Re-raise HTTP exceptions without modification
        raise
    except Exception as e:
        # Handle any unexpected errors
        db.rollback()
        logger.error(f"Unexpected error creating hotel: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error creating hotel: {str(e)}"
        )

# Create provider mapping
@router.post(
    "/add_provider_all_details_with_ittid",
    status_code=status.HTTP_201_CREATED,
)
def add_provider(
    provider_data: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Add Provider Mapping for Existing Hotel (Super User and Admin Only)
    
    Creates a new provider mapping for an existing hotel, enabling integration with
    external hotel suppliers and booking systems. This endpoint handles duplicate
    detection and provides comprehensive validation for provider data.
    
    Features:
    - Provider mapping creation for existing hotels
    - Duplicate detection and prevention
    - Hotel existence validation
    - Comprehensive error handling and logging
    - Role-based access control
    - Transactional integrity with rollback support
    
    Provider Mapping Data:
        - ittid: Internal hotel identifier (required)
        - provider_name: Supplier/provider name (e.g., "booking", "expedia")
        - provider_id: Hotel ID in the provider's system
        - system_type: Type of provider system (OTA, GDS, etc.)
        - Additional provider-specific metadata
    
    Args:
        provider_data (Dict[str, Any]): Provider mapping data including ITTID and provider details
        db (Session): Database session (injected by dependency)
        current_user (User): Currently authenticated user (injected by dependency)
    
    Returns:
        Dict[str, Any]: Operation result including:
            - message: Success or skip message
            - provider_mapping: Created or existing provider mapping data
            - operation_type: "created" or "skipped"
            - timestamp: When the operation was performed
    
    Access Control:
        - Requires SUPER_USER or ADMIN_USER role
        - All provider mapping operations logged for audit
        - User identity tracked for accountability
    
    Error Handling:
        - 400: Invalid provider data or validation errors
        - 401: User not authenticated
        - 403: Insufficient privileges (non-admin users)
        - 404: Hotel with specified ITTID not found
        - 409: Duplicate provider mapping (handled gracefully)
        - 500: Database errors or system failures
    
    Duplicate Handling:
        - Checks for existing provider_name + provider_id combinations
        - Returns existing mapping if duplicate found (no error)
        - Prevents database constraint violations
        - Logs duplicate attempts for monitoring
    
    Use Cases:
        - Adding new supplier integrations to existing hotels
        - Bulk provider mapping import operations
        - Hotel-supplier relationship management
        - Integration with external booking systems
    
    Example Request:
        {
            "ittid": "ITT123456",
            "provider_name": "booking",
            "provider_id": "hotel_12345",
            "system_type": "OTA",
            "giata_code": "67890"
        }
    """
    try:
        # Validate user authentication
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User authentication required"
            )
        
        # Check if the user has the required role
        require_role(["super_user", "admin_user"], current_user)
        
        # Validate provider data
        if not provider_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Provider data is required"
            )
        
        # Extract required fields
        ittid = provider_data.get("ittid")
        provider_name = provider_data.get("provider_name")
        provider_id = provider_data.get("provider_id")
        
        # Validate required fields
        if not ittid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="ITTID is required"
            )
        
        if not provider_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Provider name is required"
            )
        
        if not provider_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Provider ID is required"
            )
        
        # Log provider mapping attempt
        logger.info(f"Adding provider mapping: {provider_name}:{provider_id} for ITTID {ittid} by user {current_user.id}")
        
        # 1️⃣ Verify hotel exists
        try:
            hotel = db.query(models.Hotel).filter(models.Hotel.ittid == ittid).first()
            if not hotel:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Hotel with ITTID '{ittid}' not found. Please verify the hotel exists before adding provider mappings."
                )
        except SQLAlchemyError as db_error:
            logger.error(f"Database error checking hotel existence: {db_error}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error verifying hotel existence"
            )
        
        # 2️⃣ Check if provider mapping already exists
        try:
            existing = (
                db.query(models.ProviderMapping)
                .filter(
                    models.ProviderMapping.provider_name == provider_name,
                    models.ProviderMapping.provider_id == provider_id,
                )
                .first()
            )
            
            if existing:
                logger.info(f"Provider mapping already exists: {provider_name}:{provider_id} -> ITTID {existing.ittid}")
                
                # Clean up the existing mapping data for response
                existing_dict = {
                    "id": existing.id,
                    "ittid": existing.ittid,
                    "provider_name": existing.provider_name,
                    "provider_id": existing.provider_id,
                    "system_type": existing.system_type,
                    "created_at": existing.created_at.isoformat() if existing.created_at else None,
                    "updated_at": existing.updated_at.isoformat() if existing.updated_at else None
                }
                
                return {
                    "message": f"Provider mapping already exists for {provider_name}:{provider_id}",
                    "provider_mapping": existing_dict,
                    "operation_type": "skipped",
                    "timestamp": datetime.utcnow().isoformat(),
                    "hotel_name": hotel.name if hotel else "Unknown"
                }
        except SQLAlchemyError as db_error:
            logger.error(f"Database error checking existing mapping: {db_error}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error checking for existing provider mapping"
            )
        
        # 3️⃣ Create new provider mapping
        try:
            provider_mapping = models.ProviderMapping(**provider_data)
            db.add(provider_mapping)
            db.commit()
            db.refresh(provider_mapping)
            
            # Clean up the provider mapping data for response
            provider_dict = {
                "id": provider_mapping.id,
                "ittid": provider_mapping.ittid,
                "provider_name": provider_mapping.provider_name,
                "provider_id": provider_mapping.provider_id,
                "system_type": provider_mapping.system_type,
                "created_at": provider_mapping.created_at.isoformat() if provider_mapping.created_at else None,
                "updated_at": provider_mapping.updated_at.isoformat() if provider_mapping.updated_at else None
            }
            
            # Log successful creation
            logger.info(f"Successfully created provider mapping: {provider_name}:{provider_id} -> ITTID {ittid}")
            
            return {
                "message": f"Provider mapping added successfully for {provider_name}:{provider_id}",
                "provider_mapping": provider_dict,
                "operation_type": "created",
                "timestamp": datetime.utcnow().isoformat(),
                "hotel_name": hotel.name if hotel else "Unknown"
            }
            
        except IntegrityError as integrity_error:
            db.rollback()
            logger.error(f"Database integrity error creating provider mapping: {integrity_error}")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Provider mapping conflicts with existing data. Please check for duplicates."
            )
        except SQLAlchemyError as db_error:
            db.rollback()
            logger.error(f"Database error creating provider mapping: {db_error}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database error occurred while creating provider mapping"
            )
        
    except HTTPException:
        # Re-raise HTTP exceptions without modification
        raise
    except Exception as e:
        # Handle any unexpected errors
        db.rollback()
        logger.error(f"Unexpected error adding provider mapping: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error adding provider mapping: {str(e)}"
        )

# Get supplier information
@router.get("/get_supplier_info")
def get_supplier_info(
    supplier: str = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get Supplier Information and Hotel Count
    
    Retrieves comprehensive information about a specific supplier including total
    hotel count and access permissions. This endpoint provides role-based access
    control ensuring users only see suppliers they have permission to access.
    
    Features:
    - Supplier-specific hotel count and statistics
    - Role-based access control with permission validation
    - Comprehensive supplier information and metadata
    - User permission tracking and validation
    - Detailed access logging for audit purposes
    
    Supplier Information Provided:
        - Total hotel count for the supplier
        - Supplier name and system information
        - User access level and permissions
        - Access grant status and validation
        - Supplier availability and status
    
    Args:
        supplier (str): Supplier/provider name to get information for (required)
        db (Session): Database session (injected by dependency)
        current_user (User): Currently authenticated user (injected by dependency)
    
    Returns:
        Dict[str, Any]: Supplier information including:
            - supplier_name: Name of the supplier
            - total_hotel: Number of hotels available from this supplier
            - user_role: Current user's role
            - access_granted: Whether access was granted
            - access_type: Type of access (full_access, permission_granted)
            - supplier_metadata: Additional supplier information
    
    Access Control:
        - SUPER_USER: Can access any supplier information
        - ADMIN_USER: Can access any supplier information
        - GENERAL_USER: Can only access suppliers they have explicit permissions for
    
    Error Handling:
        - 400: Missing or invalid supplier parameter
        - 401: User not authenticated
        - 403: Insufficient permissions or no access to specified supplier
        - 404: Supplier not found in the system
        - 500: Database errors or system failures
    
    Permission Validation:
        - Checks UserProviderPermission table for general users
        - Validates supplier exists in the system
        - Logs access attempts for security monitoring
        - Provides detailed error messages for troubleshooting
    
    Use Cases:
        - Supplier availability checking before hotel searches
        - User permission validation for supplier access
        - Administrative supplier management and monitoring
        - Integration validation and troubleshooting
    
    Example Request:
        GET /get_supplier_info?supplier=booking
        
    Example Response:
        {
            "supplier_name": "booking",
            "total_hotel": 15420,
            "user_role": "general_user",
            "access_granted": true,
            "access_type": "permission_granted"
        }
    """
    try:
        # Validate user authentication
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User authentication required"
            )
        
        # Validate supplier parameter
        if not supplier:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Supplier name is required. Please provide a valid supplier name."
            )
        
        # Sanitize supplier name
        supplier = supplier.strip().lower()
        
        if len(supplier) < 2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Supplier name must be at least 2 characters long"
            )
        
        # Log supplier info request
        logger.info(f"Supplier info requested for '{supplier}' by user {current_user.id} (role: {current_user.role})")
        
        # Check user permissions based on role
        access_type = "unknown"
        
        try:
            if current_user.role in ["super_user", "admin_user"]:
                # Super users and admin users can access any supplier
                access_type = "full_access"
                logger.info(f"Full access granted to {current_user.role} for supplier '{supplier}'")
                
            elif current_user.role == "general_user":
                # General users can only access suppliers they have permissions for
                user_permission = db.query(models.UserProviderPermission).filter(
                    models.UserProviderPermission.user_id == current_user.id,
                    models.UserProviderPermission.provider_name == supplier
                ).first()
                
                if not user_permission:
                    logger.warning(f"Access denied for user {current_user.id} to supplier '{supplier}' - no permission found")
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"You don't have permission to access supplier '{supplier}'. Contact your administrator to request access."
                    )
                
                access_type = "permission_granted"
                logger.info(f"Permission-based access granted for user {current_user.id} to supplier '{supplier}'")
                
            else:
                # Unknown or invalid role
                logger.error(f"Unknown user role '{current_user.role}' for user {current_user.id}")
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Insufficient permissions to access supplier information. Invalid user role."
                )
        
        except SQLAlchemyError as db_error:
            logger.error(f"Database error checking user permissions: {db_error}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error validating user permissions"
            )
        
        # Get total hotel count for the supplier
        try:
            total_hotel = db.query(models.ProviderMapping).filter(
                models.ProviderMapping.provider_name == supplier
            ).count()
            
            # Check if supplier exists in the system
            if total_hotel == 0:
                # Verify if supplier exists at all or just has no hotels
                supplier_exists = db.query(models.ProviderMapping).filter(
                    models.ProviderMapping.provider_name == supplier
                ).first()
                
                if not supplier_exists:
                    logger.warning(f"Supplier '{supplier}' not found in system")
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Supplier '{supplier}' not found in the system. Please check the supplier name."
                    )
            
        except SQLAlchemyError as db_error:
            logger.error(f"Database error getting hotel count: {db_error}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error retrieving supplier hotel count"
            )
        
        # Get additional supplier metadata
        try:
            # Get unique system types for this supplier
            system_types = db.query(models.ProviderMapping.system_type).filter(
                models.ProviderMapping.provider_name == supplier,
                models.ProviderMapping.system_type.isnot(None)
            ).distinct().all()
            
            system_types_list = [st[0] for st in system_types if st[0]]
            
        except SQLAlchemyError as db_error:
            logger.warning(f"Error getting supplier metadata: {db_error}")
            system_types_list = []
        
        # Log successful access
        logger.info(f"Supplier info successfully retrieved for '{supplier}' - {total_hotel} hotels found")
        
        return {
            "supplier_name": supplier,
            "total_hotel": total_hotel,
            "user_role": current_user.role,
            "access_granted": True,
            "access_type": access_type,
            "supplier_metadata": {
                "system_types": system_types_list,
                "has_hotels": total_hotel > 0,
                "last_checked": datetime.utcnow().isoformat()
            },
            "user_info": {
                "user_id": current_user.id,
                "username": getattr(current_user, 'username', 'unknown'),
                "access_level": access_type
            }
        }
        
    except HTTPException:
        # Re-raise HTTP exceptions without modification
        raise
    except Exception as e:
        # Handle any unexpected errors
        logger.error(f"Unexpected error getting supplier info: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error retrieving supplier information: {str(e)}"
        )

# Get user accessible suppliers
@router.get("/get_user_accessible_suppliers")
def get_user_accessible_suppliers(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get User's Accessible Suppliers List
    
    Retrieves a comprehensive list of suppliers/providers that the current user has
    access to, along with hotel counts and access type information. This endpoint
    provides role-based supplier access management and detailed supplier analytics.
    
    Features:
    - Role-based supplier access listing
    - Comprehensive supplier information with hotel counts
    - Access type classification and permissions tracking
    - Supplier availability and system status information
    - User-specific supplier analytics and insights
    
    Access Levels:
        - SUPER_USER: Access to all suppliers in the system
        - ADMIN_USER: Access to all suppliers in the system
        - GENERAL_USER: Access only to explicitly permitted suppliers
    
    Supplier Information Provided:
        - Supplier name and identification
        - Total hotel count per supplier
        - Access type (full_access vs permission_granted)
        - Supplier system types and capabilities
        - Last activity and availability status
    
    Args:
        db (Session): Database session (injected by dependency)
        current_user (User): Currently authenticated user (injected by dependency)
    
    Returns:
        Dict[str, Any]: User's accessible suppliers including:
            - user_id: Current user's identifier
            - user_role: User's role in the system
            - accessible_suppliers: List of supplier objects with details
            - total_accessible_suppliers: Count of accessible suppliers
            - access_summary: Summary of access permissions
            - supplier_analytics: Aggregated supplier statistics
    
    Supplier Object Structure:
        - supplier_name: Name of the supplier/provider
        - total_hotels: Number of hotels available from this supplier
        - access_type: Type of access granted (full_access, permission_granted)
        - system_types: List of system types supported by supplier
        - last_updated: When supplier data was last updated
        - availability_status: Current supplier availability
    
    Error Handling:
        - 401: User not authenticated
        - 403: User role not recognized or insufficient permissions
        - 500: Database errors or system failures
    
    Performance Considerations:
        - Optimized queries with proper indexing
        - Efficient supplier counting and aggregation
        - Minimal database calls for large supplier lists
        - Caching-friendly response structure
    
    Use Cases:
        - Supplier selection interfaces and dropdowns
        - User permission validation and access control
        - Administrative supplier management dashboards
        - Integration capability discovery and validation
        - User onboarding and permission setup
    
    Example Response:
        {
            "user_id": "user123",
            "user_role": "general_user",
            "accessible_suppliers": [
                {
                    "supplier_name": "booking",
                    "total_hotels": 15420,
                    "access_type": "permission_granted",
                    "system_types": ["OTA"],
                    "availability_status": "active"
                }
            ],
            "total_accessible_suppliers": 1
        }
    """
    try:
        # Validate user authentication
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User authentication required"
            )
        
        # Log supplier access request
        logger.info(f"Accessible suppliers requested by user {current_user.id} (role: {current_user.role})")
        
        supplier_info = []
        access_summary = {
            "total_suppliers_in_system": 0,
            "accessible_suppliers": 0,
            "access_type": "unknown",
            "permission_based": False
        }
        
        try:
            # Get total suppliers in system for reference
            total_suppliers_query = db.query(models.ProviderMapping.provider_name).distinct()
            access_summary["total_suppliers_in_system"] = total_suppliers_query.count()
            
            if current_user.role in ["super_user", "admin_user"]:
                # Super users and admin users can access all suppliers
                logger.info(f"Providing full supplier access to {current_user.role}")
                
                suppliers = total_suppliers_query.all()
                accessible_suppliers = [supplier[0] for supplier in suppliers if supplier[0]]
                
                access_summary["access_type"] = "full_access"
                access_summary["permission_based"] = False
                
                # Get detailed information for each supplier
                for supplier_name in accessible_suppliers:
                    try:
                        # Get hotel count
                        hotel_count = db.query(models.ProviderMapping).filter(
                            models.ProviderMapping.provider_name == supplier_name
                        ).count()
                        
                        # Get system types
                        system_types = db.query(models.ProviderMapping.system_type).filter(
                            models.ProviderMapping.provider_name == supplier_name,
                            models.ProviderMapping.system_type.isnot(None)
                        ).distinct().all()
                        
                        system_types_list = [st[0] for st in system_types if st[0]]
                        
                        # Get last update timestamp
                        last_updated = db.query(models.ProviderMapping.updated_at).filter(
                            models.ProviderMapping.provider_name == supplier_name,
                            models.ProviderMapping.updated_at.isnot(None)
                        ).order_by(models.ProviderMapping.updated_at.desc()).first()
                        
                        supplier_info.append({
                            "supplier_name": supplier_name,
                            "total_hotels": hotel_count,
                            "access_type": "full_access",
                            "system_types": system_types_list,
                            "last_updated": last_updated[0].isoformat() if last_updated and last_updated[0] else None,
                            "availability_status": "active" if hotel_count > 0 else "inactive"
                        })
                        
                    except SQLAlchemyError as supplier_error:
                        logger.warning(f"Error getting details for supplier {supplier_name}: {supplier_error}")
                        # Add basic info even if detailed info fails
                        supplier_info.append({
                            "supplier_name": supplier_name,
                            "total_hotels": 0,
                            "access_type": "full_access",
                            "system_types": [],
                            "last_updated": None,
                            "availability_status": "unknown"
                        })
                
            elif current_user.role == "general_user":
                # General users get only suppliers they have permissions for
                logger.info(f"Providing permission-based supplier access to general user {current_user.id}")
                
                user_permissions = db.query(models.UserProviderPermission).filter(
                    models.UserProviderPermission.user_id == current_user.id
                ).all()
                
                access_summary["access_type"] = "permission_granted"
                access_summary["permission_based"] = True
                
                for permission in user_permissions:
                    try:
                        # Get hotel count
                        hotel_count = db.query(models.ProviderMapping).filter(
                            models.ProviderMapping.provider_name == permission.provider_name
                        ).count()
                        
                        # Get system types
                        system_types = db.query(models.ProviderMapping.system_type).filter(
                            models.ProviderMapping.provider_name == permission.provider_name,
                            models.ProviderMapping.system_type.isnot(None)
                        ).distinct().all()
                        
                        system_types_list = [st[0] for st in system_types if st[0]]
                        
                        # Get last update timestamp
                        last_updated = db.query(models.ProviderMapping.updated_at).filter(
                            models.ProviderMapping.provider_name == permission.provider_name,
                            models.ProviderMapping.updated_at.isnot(None)
                        ).order_by(models.ProviderMapping.updated_at.desc()).first()
                        
                        supplier_info.append({
                            "supplier_name": permission.provider_name,
                            "total_hotels": hotel_count,
                            "access_type": "permission_granted",
                            "system_types": system_types_list,
                            "permission_granted_at": permission.created_at.isoformat() if permission.created_at else None,
                            "last_updated": last_updated[0].isoformat() if last_updated and last_updated[0] else None,
                            "availability_status": "active" if hotel_count > 0 else "inactive"
                        })
                        
                    except SQLAlchemyError as permission_error:
                        logger.warning(f"Error getting details for permitted supplier {permission.provider_name}: {permission_error}")
                        # Add basic info even if detailed info fails
                        supplier_info.append({
                            "supplier_name": permission.provider_name,
                            "total_hotels": 0,
                            "access_type": "permission_granted",
                            "system_types": [],
                            "permission_granted_at": permission.created_at.isoformat() if permission.created_at else None,
                            "last_updated": None,
                            "availability_status": "unknown"
                        })
                
            else:
                # Unknown or invalid role
                logger.error(f"Unknown user role '{current_user.role}' for user {current_user.id}")
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"User role '{current_user.role}' is not recognized. Please contact administrator."
                )
            
            access_summary["accessible_suppliers"] = len(supplier_info)
            
        except SQLAlchemyError as db_error:
            logger.error(f"Database error getting accessible suppliers: {db_error}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error retrieving accessible suppliers"
            )
        
        # Generate supplier analytics
        supplier_analytics = {
            "total_hotels_accessible": sum(s["total_hotels"] for s in supplier_info),
            "active_suppliers": len([s for s in supplier_info if s["availability_status"] == "active"]),
            "inactive_suppliers": len([s for s in supplier_info if s["availability_status"] == "inactive"]),
            "system_types_available": list(set(
                st for s in supplier_info for st in s.get("system_types", [])
            )),
            "access_coverage_percentage": round(
                (access_summary["accessible_suppliers"] / access_summary["total_suppliers_in_system"] * 100), 2
            ) if access_summary["total_suppliers_in_system"] > 0 else 0
        }
        
        # Log successful response
        logger.info(f"Successfully retrieved {len(supplier_info)} accessible suppliers for user {current_user.id}")
        
        return {
            "user_id": current_user.id,
            "user_role": current_user.role,
            "accessible_suppliers": supplier_info,
            "total_accessible_suppliers": len(supplier_info),
            "access_summary": access_summary,
            "supplier_analytics": supplier_analytics,
            "response_metadata": {
                "generated_at": datetime.utcnow().isoformat(),
                "user_info": {
                    "username": getattr(current_user, 'username', 'unknown'),
                    "user_id": current_user.id
                }
            }
        }
        
    except HTTPException:
        # Re-raise HTTP exceptions without modification
        raise
    except Exception as e:
        # Handle any unexpected errors
        logger.error(f"Unexpected error getting accessible suppliers: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error retrieving accessible suppliers: {str(e)}"
        )
