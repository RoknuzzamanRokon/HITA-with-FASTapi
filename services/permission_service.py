from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from datetime import datetime
import logging

from models import User, UserProviderPermission, ProviderMapping

# Configure logging
logger = logging.getLogger(__name__)


class PermissionService:
    """
    Service for managing user provider permissions.
    Handles supplier access control and permission management.
    """
    
    def __init__(self, db: Session):
        """
        Initialize PermissionService with database session.
        
        Args:
            db: SQLAlchemy database session
        """
        self.db = db
        logger.info("PermissionService initialized")

    def get_user_permissions(self, user_id: str) -> List[str]:
        """
        Get list of provider permissions for a user.
        
        Args:
            user_id: User ID to get permissions for
            
        Returns:
            List of provider names the user has access to
        """
        try:
            permissions = self.db.query(UserProviderPermission).filter(
                UserProviderPermission.user_id == user_id
            ).all()
            
            provider_names = [perm.provider_name for perm in permissions]
            logger.debug(f"User {user_id} has permissions for {len(provider_names)} providers")
            
            return provider_names
            
        except Exception as e:
            logger.error(f"Error getting permissions for user {user_id}: {str(e)}")
            raise

    def add_user_permission(self, user_id: str, provider_name: str) -> bool:
        """
        Add a provider permission for a user.
        
        Args:
            user_id: User ID to add permission for
            provider_name: Provider name to grant access to
            
        Returns:
            True if permission was added successfully
        """
        try:
            # Check if permission already exists
            existing_permission = self.db.query(UserProviderPermission).filter(
                UserProviderPermission.user_id == user_id,
                UserProviderPermission.provider_name == provider_name
            ).first()
            
            if existing_permission:
                logger.info(f"Permission already exists for user {user_id} and provider {provider_name}")
                return True
            
            # Verify provider exists
            if not self._provider_exists(provider_name):
                logger.warning(f"Provider {provider_name} does not exist in system")
                return False
            
            # Create new permission
            new_permission = UserProviderPermission(
                user_id=user_id,
                provider_name=provider_name
            )
            
            self.db.add(new_permission)
            self.db.commit()
            
            logger.info(f"Added permission for user {user_id} to access provider {provider_name}")
            return True
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error adding permission: {str(e)}")
            raise

    def remove_user_permission(self, user_id: str, provider_name: str) -> bool:
        """
        Remove a provider permission for a user.
        
        Args:
            user_id: User ID to remove permission from
            provider_name: Provider name to revoke access to
            
        Returns:
            True if permission was removed successfully
        """
        try:
            permission = self.db.query(UserProviderPermission).filter(
                UserProviderPermission.user_id == user_id,
                UserProviderPermission.provider_name == provider_name
            ).first()
            
            if not permission:
                logger.info(f"Permission does not exist for user {user_id} and provider {provider_name}")
                return True
            
            self.db.delete(permission)
            self.db.commit()
            
            logger.info(f"Removed permission for user {user_id} to access provider {provider_name}")
            return True
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error removing permission: {str(e)}")
            raise

    def set_user_permissions(self, user_id: str, provider_names: List[str]) -> bool:
        """
        Set the complete list of provider permissions for a user.
        This will replace all existing permissions.
        
        Args:
            user_id: User ID to set permissions for
            provider_names: List of provider names to grant access to
            
        Returns:
            True if permissions were set successfully
        """
        try:
            logger.info(f"Setting permissions for user {user_id} to {len(provider_names)} providers")
            
            # Remove all existing permissions
            existing_permissions = self.db.query(UserProviderPermission).filter(
                UserProviderPermission.user_id == user_id
            ).all()
            
            for permission in existing_permissions:
                self.db.delete(permission)
            
            # Add new permissions
            for provider_name in provider_names:
                if self._provider_exists(provider_name):
                    new_permission = UserProviderPermission(
                        user_id=user_id,
                        provider_name=provider_name
                    )
                    self.db.add(new_permission)
                else:
                    logger.warning(f"Skipping non-existent provider: {provider_name}")
            
            self.db.commit()
            
            logger.info(f"Successfully set permissions for user {user_id}")
            return True
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error setting permissions: {str(e)}")
            raise

    def get_available_providers(self) -> List[str]:
        """
        Get list of all available providers in the system.
        
        Returns:
            List of provider names
        """
        try:
            providers = self.db.query(ProviderMapping.provider_name).distinct().all()
            provider_names = [provider.provider_name for provider in providers]
            
            logger.debug(f"Found {len(provider_names)} available providers")
            return provider_names
            
        except Exception as e:
            logger.error(f"Error getting available providers: {str(e)}")
            raise

    def get_users_with_provider_access(self, provider_name: str) -> List[str]:
        """
        Get list of user IDs that have access to a specific provider.
        
        Args:
            provider_name: Provider name to check access for
            
        Returns:
            List of user IDs with access to the provider
        """
        try:
            permissions = self.db.query(UserProviderPermission).filter(
                UserProviderPermission.provider_name == provider_name
            ).all()
            
            user_ids = [perm.user_id for perm in permissions]
            logger.debug(f"Found {len(user_ids)} users with access to provider {provider_name}")
            
            return user_ids
            
        except Exception as e:
            logger.error(f"Error getting users with provider access: {str(e)}")
            raise

    def user_has_provider_access(self, user_id: str, provider_name: str) -> bool:
        """
        Check if a user has access to a specific provider.
        
        Args:
            user_id: User ID to check
            provider_name: Provider name to check access for
            
        Returns:
            True if user has access to the provider
        """
        try:
            permission = self.db.query(UserProviderPermission).filter(
                UserProviderPermission.user_id == user_id,
                UserProviderPermission.provider_name == provider_name
            ).first()
            
            has_access = permission is not None
            logger.debug(f"User {user_id} {'has' if has_access else 'does not have'} access to provider {provider_name}")
            
            return has_access
            
        except Exception as e:
            logger.error(f"Error checking provider access: {str(e)}")
            return False

    def bulk_add_permissions(self, user_provider_pairs: List[tuple]) -> int:
        """
        Add multiple permissions in bulk.
        
        Args:
            user_provider_pairs: List of (user_id, provider_name) tuples
            
        Returns:
            Number of permissions successfully added
        """
        try:
            added_count = 0
            
            for user_id, provider_name in user_provider_pairs:
                # Check if permission already exists
                existing = self.db.query(UserProviderPermission).filter(
                    UserProviderPermission.user_id == user_id,
                    UserProviderPermission.provider_name == provider_name
                ).first()
                
                if not existing and self._provider_exists(provider_name):
                    new_permission = UserProviderPermission(
                        user_id=user_id,
                        provider_name=provider_name
                    )
                    self.db.add(new_permission)
                    added_count += 1
            
            self.db.commit()
            
            logger.info(f"Bulk added {added_count} permissions")
            return added_count
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error bulk adding permissions: {str(e)}")
            raise

    def bulk_remove_permissions(self, user_provider_pairs: List[tuple]) -> int:
        """
        Remove multiple permissions in bulk.
        
        Args:
            user_provider_pairs: List of (user_id, provider_name) tuples
            
        Returns:
            Number of permissions successfully removed
        """
        try:
            removed_count = 0
            
            for user_id, provider_name in user_provider_pairs:
                permission = self.db.query(UserProviderPermission).filter(
                    UserProviderPermission.user_id == user_id,
                    UserProviderPermission.provider_name == provider_name
                ).first()
                
                if permission:
                    self.db.delete(permission)
                    removed_count += 1
            
            self.db.commit()
            
            logger.info(f"Bulk removed {removed_count} permissions")
            return removed_count
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error bulk removing permissions: {str(e)}")
            raise

    def get_permission_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about provider permissions.
        
        Returns:
            Dictionary with permission statistics
        """
        try:
            # Total permissions
            total_permissions = self.db.query(UserProviderPermission).count()
            
            # Unique users with permissions
            users_with_permissions = self.db.query(
                UserProviderPermission.user_id
            ).distinct().count()
            
            # Permissions per provider
            provider_stats = self.db.query(
                UserProviderPermission.provider_name,
                self.db.func.count(UserProviderPermission.user_id).label('user_count')
            ).group_by(UserProviderPermission.provider_name).all()
            
            provider_distribution = {
                provider: count for provider, count in provider_stats
            }
            
            # Available providers
            total_providers = len(self.get_available_providers())
            
            return {
                "total_permissions": total_permissions,
                "users_with_permissions": users_with_permissions,
                "total_available_providers": total_providers,
                "provider_distribution": provider_distribution
            }
            
        except Exception as e:
            logger.error(f"Error getting permission statistics: {str(e)}")
            raise

    def cleanup_user_permissions(self, user_id: str) -> int:
        """
        Clean up all permissions for a user (used during user deletion).
        
        Args:
            user_id: User ID to clean up permissions for
            
        Returns:
            Number of permissions removed
        """
        try:
            permissions = self.db.query(UserProviderPermission).filter(
                UserProviderPermission.user_id == user_id
            ).all()
            
            removed_count = len(permissions)
            
            for permission in permissions:
                self.db.delete(permission)
            
            self.db.commit()
            
            logger.info(f"Cleaned up {removed_count} permissions for user {user_id}")
            return removed_count
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error cleaning up permissions for user {user_id}: {str(e)}")
            raise

    def _provider_exists(self, provider_name: str) -> bool:
        """
        Check if a provider exists in the system.
        
        Args:
            provider_name: Provider name to check
            
        Returns:
            True if provider exists
        """
        try:
            provider = self.db.query(ProviderMapping).filter(
                ProviderMapping.provider_name == provider_name
            ).first()
            
            return provider is not None
            
        except Exception as e:
            logger.error(f"Error checking if provider exists: {str(e)}")
            return False