# Utils package initialization
# Import all functions from main.py to make them available at package level
from .main import (
    is_exempt_from_point_deduction,
    create_user,
    generate_unique_id,
    generate_user_id,
    hash_password,
    authenticate_user,
    create_access_token,
    require_role,
    deduct_points_for_general_user,
    pwd_context,
    SECRET_KEY,
    ALGORITHM,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    oauth2_scheme,
    blacklist,
    PER_REQUEST_POINT_DEDUCTION,
)

# Make these available when importing from utils package
__all__ = [
    "is_exempt_from_point_deduction",
    "create_user",
    "generate_unique_id",
    "generate_user_id",
    "hash_password",
    "authenticate_user",
    "create_access_token",
    "require_role",
    "deduct_points_for_general_user",
    "pwd_context",
    "SECRET_KEY",
    "ALGORITHM",
    "ACCESS_TOKEN_EXPIRE_MINUTES",
    "oauth2_scheme",
    "blacklist",
    "PER_REQUEST_POINT_DEDUCTION",
]
