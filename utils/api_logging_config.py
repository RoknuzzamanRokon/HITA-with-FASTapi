"""
API Logging Configuration Manager

This module provides a centralized way to manage which API endpoints should be
counted in usage logs and which should be excluded.

Usage:
    from utils.api_logging_config import APILoggingConfig

    config = APILoggingConfig()

    # Check if an endpoint should be counted
    if config.should_count_endpoint("/v1.0/user/all-general-user"):
        # Log this API call
        pass

    # Check if an endpoint should NOT be counted
    if config.should_exclude_endpoint("/v1.0/auth/check-me"):
        # Skip logging this API call
        pass
"""

import json
import os
from typing import List, Set
from pathlib import Path


class APILoggingConfig:
    """
    Manages API logging configuration for counting endpoint usage.

    This class loads configuration from a JSON file that defines which endpoints
    should be counted in usage logs and which should be excluded.
    """

    def __init__(self, config_file: str = None):
        """
        Initialize the API logging configuration.

        Args:
            config_file (str, optional): Path to the configuration file.
                                       Defaults to 'config/api_logging_config.json'
        """
        if config_file is None:
            # Default config file path relative to project root
            project_root = Path(__file__).parent.parent
            config_file = project_root / "config" / "api_logging_config.json"

        self.config_file = config_file
        self.count_endpoints: Set[str] = set()
        self.exclude_endpoints: Set[str] = set()
        self._load_config()

    def _load_config(self):
        """Load configuration from the JSON file."""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, "r", encoding="utf-8") as f:
                    config = json.load(f)

                # Load endpoints that should be counted
                self.count_endpoints = set(config.get("count_log_endpoints", []))

                # Load endpoints that should NOT be counted
                self.exclude_endpoints = set(
                    config.get("cannot_count_log_endpoints", [])
                )

                print(
                    f"✅ API Logging Config loaded: {len(self.count_endpoints)} count, {len(self.exclude_endpoints)} exclude"
                )
            else:
                print(f"⚠️ API Logging Config file not found: {self.config_file}")
                # Use default empty sets

        except Exception as e:
            print(f"❌ Error loading API logging config: {e}")
            # Use default empty sets if config fails to load

    def should_count_endpoint(self, endpoint_path: str) -> bool:
        """
        Check if an endpoint should be counted in usage logs.
        Supports both exact matching and pattern matching for dynamic endpoints.

        Args:
            endpoint_path (str): The API endpoint path (e.g., "/v1.0/content/get-hotel-with-ittid/11639309")

        Returns:
            bool: True if the endpoint should be counted, False otherwise
        """
        # First check if it's explicitly excluded
        if self.should_exclude_endpoint(endpoint_path):
            return False

        # Check for exact match first
        if endpoint_path in self.count_endpoints:
            return True

        # Check for pattern matching for dynamic endpoints
        for count_endpoint in self.count_endpoints:
            # Handle dynamic path parameters like /v1.0/content/get-hotel-with-ittid/{ittid}
            if "{" in count_endpoint and "}" in count_endpoint:
                # Convert pattern to regex-like matching
                pattern_parts = count_endpoint.split("/")
                path_parts = endpoint_path.split("/")

                if len(pattern_parts) == len(path_parts):
                    match = True
                    for i, (pattern_part, path_part) in enumerate(
                        zip(pattern_parts, path_parts)
                    ):
                        # Skip empty parts
                        if not pattern_part and not path_part:
                            continue
                        # Check if pattern part is a parameter (contains {})
                        if "{" in pattern_part and "}" in pattern_part:
                            # This is a parameter, so it matches any value
                            continue
                        # Exact match required for non-parameter parts
                        elif pattern_part != path_part:
                            match = False
                            break

                    if match:
                        return True

            # Handle prefix matching for endpoints that start with a base path
            elif endpoint_path.startswith(count_endpoint + "/"):
                return True

        return False

    def should_exclude_endpoint(self, endpoint_path: str) -> bool:
        """
        Check if an endpoint should be excluded from usage logs.

        Args:
            endpoint_path (str): The API endpoint path (e.g., "/v1.0/auth/check-me")

        Returns:
            bool: True if the endpoint should be excluded, False otherwise
        """
        return endpoint_path in self.exclude_endpoints

    def add_count_endpoint(self, endpoint_path: str):
        """
        Add an endpoint to the count list.

        Args:
            endpoint_path (str): The API endpoint path to add
        """
        self.count_endpoints.add(endpoint_path)
        self._save_config()

    def add_exclude_endpoint(self, endpoint_path: str):
        """
        Add an endpoint to the exclude list.

        Args:
            endpoint_path (str): The API endpoint path to add
        """
        self.exclude_endpoints.add(endpoint_path)
        self._save_config()

    def remove_count_endpoint(self, endpoint_path: str):
        """
        Remove an endpoint from the count list.

        Args:
            endpoint_path (str): The API endpoint path to remove
        """
        self.count_endpoints.discard(endpoint_path)
        self._save_config()

    def remove_exclude_endpoint(self, endpoint_path: str):
        """
        Remove an endpoint from the exclude list.

        Args:
            endpoint_path (str): The API endpoint path to remove
        """
        self.exclude_endpoints.discard(endpoint_path)
        self._save_config()

    def _save_config(self):
        """Save the current configuration back to the JSON file."""
        try:
            config = {
                "count_log_endpoints": sorted(list(self.count_endpoints)),
                "cannot_count_log_endpoints": sorted(list(self.exclude_endpoints)),
                "description": {
                    "count_log_endpoints": "API endpoints that should be counted in usage logs and analytics",
                    "cannot_count_log_endpoints": "API endpoints that should NOT be counted (health checks, auth, docs, etc.)",
                },
            }

            # Ensure config directory exists
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)

            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2, ensure_ascii=False)

            print(f"✅ API Logging Config saved to {self.config_file}")

        except Exception as e:
            print(f"❌ Error saving API logging config: {e}")

    def get_count_endpoints(self) -> List[str]:
        """Get list of endpoints that should be counted."""
        return sorted(list(self.count_endpoints))

    def get_exclude_endpoints(self) -> List[str]:
        """Get list of endpoints that should be excluded."""
        return sorted(list(self.exclude_endpoints))

    def reload_config(self):
        """Reload configuration from file."""
        self._load_config()

    def get_config_summary(self) -> dict:
        """Get a summary of the current configuration."""
        return {
            "total_count_endpoints": len(self.count_endpoints),
            "total_exclude_endpoints": len(self.exclude_endpoints),
            "count_endpoints": self.get_count_endpoints(),
            "exclude_endpoints": self.get_exclude_endpoints(),
        }


# Global instance for easy access
api_logging_config = APILoggingConfig()
