"""
Export Permission Service

Handles permission validation for export operations including:
- Role-based access control
- Supplier permission validation
- IP whitelist verification
- Temporarily deactivated supplier handling
"""

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from fastapi import Request, HTTPException, status
from datetime import datetime
import logging

from models import User, UserProviderPermission, UserIPWhitelist, ProviderMapping, UserRole
from middleware.ip_middleware import get_client_ip

# Configure logging
logger = logging.getLogger(__name__)


class PermissionValidationResult:
    """Result object for permission validation"""
    
    def __init__(
        self,
        is_authorized: bool,
        allowed_suppliers: List[str],
        denied_suppliers: List[str] = None,
        deactivated_suppliers: List[str] = None,
        error_message: Optional[str] = None
    ):
        self.is_authorized = is_authorized
        self.allowed_suppliers = allowed_suppliers
        self.denied_suppliers = denied_suppliers or []
        self.deactivated_suppliers = deactivated_suppliers or []
        self.error_message = error_message


class ExportPermissionService:
    """
    Service for validating export permissions.
    
    Handles:
    - Role-based access control (SUPER_USER, ADMIN_USER, GENERAL_USER)
    - Supplier permission validation
    - IP whitelist verification
    - Temporarily deactivated supplier filtering
    """
    
    def __init__(self, db: Session):
        """
        Initialize ExportPermissionService with database session.
        
        Args:
            db: SQLAlchemy database session
        """
        self.db = db
        logger.info("ExportPermissionService initialized")

    def validate_export_access(
        self,
        user: User,
        request: Request,
        requested_suppliers: Optional[List[str]] = None
    ) -> PermissionValidationResult:
        """
        Validates user has permission to export data for requested suppliers.
        
        Validation steps:
        1. Check IP whitelist
        2. Get user's active suppliers (excluding TEMP_DEACTIVATED_)
        3. Validate requested suppliers against user permissions
        4. Apply role-based access rules
        
        Args:
            user: User object from authentication
            request: FastAPI request object for IP extraction
            requested_suppliers: List of supplier names requested (None = all accessible)
            
        Returns:
            PermissionValidationResult with authorization status and supplier lists
            
        Raises:
            HTTPException: If IP is not whitelisted or user has no permissions
        """
        logger.info(f"Validating export access for user {user.id} (role: {user.role})")
        
        # Step 1: IP Whitelist Validation
        if not self.check_ip_whitelist(user.id, request):
            client_ip = get_client_ip(request) or "unknown"
            error_msg = f"IP address {client_ip} is not whitelisted for user {user.username}"
            logger.warning(f"IP whitelist check failed: {error_msg}")
            
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "IP_NOT_WHITELISTED",
                    "message": error_msg,
                    "client_ip": client_ip
                }
            )
        
        # Step 2: Get user's active suppliers
        user_suppliers = self.get_user_suppliers(user.id, user.role)
        deactivated_suppliers = self._get_deactivated_suppliers(user.id)
        
        logger.debug(f"User {user.id} has {len(user_suppliers)} active suppliers")
        logger.debug(f"User {user.id} has {len(deactivated_suppliers)} deactivated suppliers")
        
        # Step 3: Determine allowed suppliers based on request
        if requested_suppliers is None or len(requested_suppliers) == 0:
            # No specific suppliers requested - return all accessible
            allowed_suppliers = user_suppliers
            denied_suppliers = []
        else:
            # Validate each requested supplier
            allowed_suppliers = []
            denied_suppliers = []
            
            for supplier in requested_suppliers:
                # Check if supplier is temporarily deactivated
                if supplier in deactivated_suppliers:
                    denied_suppliers.append(supplier)
                    logger.warning(f"Supplier {supplier} is temporarily deactivated for user {user.id}")
                # Check if user has access to supplier
                elif supplier in user_suppliers:
                    allowed_suppliers.append(supplier)
                else:
                    denied_suppliers.append(supplier)
                    logger.warning(f"User {user.id} does not have access to supplier {supplier}")
        
        # Step 4: Check if user has any allowed suppliers
        if not allowed_suppliers:
            error_msg = "No accessible suppliers found for export"
            if denied_suppliers:
                error_msg += f". Denied suppliers: {', '.join(denied_suppliers)}"
            
            logger.warning(f"Export access denied for user {user.id}: {error_msg}")
            
            return PermissionValidationResult(
                is_authorized=False,
                allowed_suppliers=[],
                denied_suppliers=denied_suppliers,
                deactivated_suppliers=deactivated_suppliers,
                error_message=error_msg
            )
        
        logger.info(f"Export access granted for user {user.id} with {len(allowed_suppliers)} suppliers")
        
        return PermissionValidationResult(
            is_authorized=True,
            allowed_suppliers=allowed_suppliers,
            denied_suppliers=denied_suppliers,
            deactivated_suppliers=deactivated_suppliers
        )

    def check_ip_whitelist(self, user_id: str, request: Request) -> bool:
        """
        Check if user's IP is whitelisted.
        
        Uses the same logic as the existing check_ip_whitelist function
        from routes/contents.py.
        
        Args:
            user_id: User ID to check whitelist for
            request: FastAPI request object to extract IP
            
        Returns:
            bool: True if IP is whitelisted, False if blocked
        """
        logger.debug(f"Checking IP whitelist for user {user_id}")
        
        try:
            # Extract client IP using middleware helper
            client_ip = get_client_ip(request)
            
            logger.debug(f"Detected client IP: {client_ip}")
            
            if not client_ip:
                logger.warning("Could not determine client IP, allowing access (fail open)")
                return True
            
            # Check if user has any IP whitelist entries
            whitelist_entries = self.db.query(UserIPWhitelist).filter(
                UserIPWhitelist.user_id == user_id,
                UserIPWhitelist.is_active == True
            ).all()
            
            logger.debug(f"Found {len(whitelist_entries)} whitelist entries for user {user_id}")
            
            # REQUIRE IP WHITELIST: If no whitelist entries exist, DENY access
            if not whitelist_entries:
                logger.warning(f"No whitelist entries found for user {user_id}, DENYING access")
                return False
            
            # Check if current IP is in whitelist
            whitelisted_ips = [entry.ip_address for entry in whitelist_entries]
            logger.debug(f"Whitelisted IPs for user {user_id}: {whitelisted_ips}")
            
            is_whitelisted = client_ip in whitelisted_ips
            logger.debug(f"IP {client_ip} whitelisted: {is_whitelisted}")
            
            return is_whitelisted
            
        except Exception as e:
            # If there's an error checking whitelist, fail open (allow access)
            logger.error(f"Error checking IP whitelist for user {user_id}: {str(e)}")
            return True

    def get_user_suppliers(self, user_id: str, user_role: UserRole) -> List[str]:
        """
        Get list of active suppliers for user based on role.
        
        Role-based logic:
        - SUPER_USER / ADMIN_USER: All suppliers in system (excluding TEMP_DEACTIVATED_)
        - GENERAL_USER: Only assigned suppliers (excluding TEMP_DEACTIVATED_)
        
        Args:
            user_id: User ID to get suppliers for
            user_role: User's role (SUPER_USER, ADMIN_USER, GENERAL_USER)
            
        Returns:
            List of active supplier names
        """
        logger.debug(f"Getting suppliers for user {user_id} with role {user_role}")
        
        try:
            # Get temporarily deactivated suppliers for this user
            deactivated_suppliers = self._get_deactivated_suppliers(user_id)
            
            # Super users and admin users get all system suppliers
            if user_role in [UserRole.SUPER_USER, UserRole.ADMIN_USER]:
                logger.debug(f"User {user_id} is admin/super user, fetching all system suppliers")
                
                # Get all unique suppliers from provider_mappings table
                all_suppliers = [
                    row.provider_name
                    for row in self.db.query(ProviderMapping.provider_name).distinct().all()
                ]
                
                # Filter out temporarily deactivated suppliers
                active_suppliers = [
                    supplier for supplier in all_suppliers 
                    if supplier not in deactivated_suppliers
                ]
                
                logger.info(f"Admin/Super user {user_id} has access to {len(active_suppliers)} suppliers")
                return active_suppliers
            
            # General users get only their assigned suppliers
            else:
                logger.debug(f"User {user_id} is general user, fetching assigned suppliers")
                
                # Get user's assigned suppliers (excluding TEMP_DEACTIVATED_ prefix)
                permissions = self.db.query(UserProviderPermission).filter(
                    UserProviderPermission.user_id == user_id,
                    ~UserProviderPermission.provider_name.like("TEMP_DEACTIVATED_%")
                ).all()
                
                suppliers = [perm.provider_name for perm in permissions]
                unique_suppliers = list(set(suppliers))
                
                # Filter out temporarily deactivated suppliers
                active_suppliers = [
                    supplier for supplier in unique_suppliers 
                    if supplier not in deactivated_suppliers
                ]
                
                logger.info(f"General user {user_id} has access to {len(active_suppliers)} suppliers")
                return active_suppliers
                
        except Exception as e:
            logger.error(f"Error getting suppliers for user {user_id}: {str(e)}")
            raise

    def _get_deactivated_suppliers(self, user_id: str) -> List[str]:
        """
        Get list of temporarily deactivated suppliers for user.
        
        Suppliers with TEMP_DEACTIVATED_ prefix are considered deactivated.
        
        Args:
            user_id: User ID to get deactivated suppliers for
            
        Returns:
            List of deactivated supplier names (without prefix)
        """
        try:
            deactivated_perms = self.db.query(UserProviderPermission).filter(
                UserProviderPermission.user_id == user_id,
                UserProviderPermission.provider_name.like("TEMP_DEACTIVATED_%")
            ).all()
            
            # Extract original supplier names by removing prefix
            deactivated_suppliers = [
                perm.provider_name.replace("TEMP_DEACTIVATED_", "")
                for perm in deactivated_perms
            ]
            
            return list(set(deactivated_suppliers))
            
        except Exception as e:
            logger.error(f"Error getting deactivated suppliers for user {user_id}: {str(e)}")
            return []

    def get_all_system_suppliers(self) -> List[str]:
        """
        Get list of all suppliers available in the system.
        
        Returns:
            List of all unique supplier names from provider_mappings
        """
        try:
            suppliers = self.db.query(ProviderMapping.provider_name).distinct().all()
            supplier_names = [supplier.provider_name for supplier in suppliers]
            
            logger.debug(f"Found {len(supplier_names)} suppliers in system")
            return supplier_names
            
        except Exception as e:
            logger.error(f"Error getting all system suppliers: {str(e)}")
            raise

    def validate_suppliers_exist(self, supplier_names: List[str]) -> Dict[str, bool]:
        """
        Validate that requested suppliers exist in the system.
        
        Args:
            supplier_names: List of supplier names to validate
            
        Returns:
            Dictionary mapping supplier name to existence status
        """
        try:
            all_suppliers = self.get_all_system_suppliers()
            
            validation_result = {
                supplier: supplier in all_suppliers
                for supplier in supplier_names
            }
            
            logger.debug(f"Validated {len(supplier_names)} suppliers")
            return validation_result
            
        except Exception as e:
            logger.error(f"Error validating suppliers: {str(e)}")
            raise
