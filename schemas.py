from pydantic import BaseModel, EmailStr, Field, validator, RootModel
from typing import Optional, List, Dict, Any, Optional
from datetime import datetime


# --- User Schemas ---
class UserCreate(BaseModel):
    username: str = Field(..., max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)

    @validator("username")
    def validate_username(cls, value):
        if not value.isalnum():
            raise ValueError("Username must be alphanumeric.")
        return value

class CreatedByInfo(BaseModel):
    title: str
    email: str


class User(BaseModel):
    id: str
    username: str
    email: EmailStr
    role: str
    created_by: List[CreatedByInfo]

    class Config:
        from_attributes = True

class SuperUserResponse(BaseModel):
    id: str
    username: str
    email: str
    role: str
    created_by: List[CreatedByInfo]


class AdminUserResponse(BaseModel):
    id: str
    username: str
    email: str
    role: str
    created_by: List[CreatedByInfo]

class Token(BaseModel):
    access_token: str
    token_type: str

class SupplierInfo(BaseModel):
    total_active: int
    active_list: List[str]
    temporary_off: int
    temporary_off_supplier: List[str]

class UserResponse(BaseModel):
    id: str
    username: str
    email: str
    user_status: str
    available_points: int
    total_points: int
    supplier_info: SupplierInfo
    created_at: datetime
    updated_at: Optional[datetime]
    need_to_next_upgrade: str

    class Config:
        from_attributes = True

# --- Hotel Schemas ---
class LocationCreate(BaseModel):
    city_name: Optional[str] = Field(None, max_length=100)
    state_name: Optional[str] = Field(None, max_length=100)
    state_code: Optional[str] = Field(None, max_length=10)
    country_name: Optional[str] = Field(None, max_length=100)
    country_code: Optional[str] = Field(None, max_length=2)
    master_city_name: Optional[str] = Field(None, max_length=100)
    city_code: Optional[str] = Field(None, max_length=50)
    city_location_id: Optional[str] = Field(None, max_length=50)

class ProviderMappingCreate(BaseModel):
    provider_name: str = Field(..., max_length=50)
    provider_id: str = Field(..., max_length=50)
    system_type: str = Field(..., max_length=20)
    vervotech_id: Optional[str] = Field(None, max_length=50)
    giata_code: Optional[str] = Field(None, max_length=50)

class ContactCreate(BaseModel):
    contact_type: str = Field(..., max_length=20)
    value: str = Field(..., max_length=255)

class ChainCreate(BaseModel):
    chain_name: Optional[str] = Field(None, max_length=100)
    chain_code: Optional[str] = Field(None, max_length=50)
    brand_name: Optional[str] = Field(None, max_length=100)


class HotelCreateDemo(BaseModel):
    ittid: str = Field(..., max_length=50)
    name: str = Field(..., max_length=255)
    latitude: Optional[str] = Field(None, max_length=50)
    longitude: Optional[str] = Field(None, max_length=50)
    rating: Optional[str] = Field(None, max_length=10)
    address_line1: Optional[str] = Field(None, max_length=255)
    address_line2: Optional[str] = Field(None, max_length=255)
    city_name: Optional[str] = Field(None, max_length=100)
    state_name: Optional[str] = Field(None, max_length=100)
    state_code: Optional[str] = Field(None, max_length=10)
    country_name: Optional[str] = Field(None, max_length=100)
    country_code: Optional[str] = Field(None, max_length=10)
    postal_code: Optional[str] = Field(None, max_length=20)
    city_code: Optional[str] = Field(None, max_length=50)
    city_location_id: Optional[str] = Field(None, max_length=50)
    master_city_name: Optional[str] = Field(None, max_length=100)
    location_ids: Optional[str] = Field(None, max_length=255)


class HotelReadDemo(HotelCreateDemo):
    id: int

    class Config:
        from_attributes = True


class HotelCreate(BaseModel):
    ittid: str = Field(..., max_length=50)
    name: str = Field(..., max_length=255)
    latitude: Optional[str] = Field(None, max_length=50)
    longitude: Optional[str] = Field(None, max_length=50)
    address_line1: Optional[str] = Field(None, max_length=255)
    address_line2: Optional[str] = Field(None, max_length=255)
    postal_code: Optional[str] = Field(None, max_length=20)
    rating: Optional[str] = Field(None, max_length=10)
    primary_photo: Optional[str] = Field(None, max_length=500)
    property_type: Optional[str] = Field(None, max_length=100)
    map_status: Optional[str] = Field(None, max_length=20)
    content_update_status: Optional[str] = Field(None, max_length=20)
    locations: List[LocationCreate] = []
    provider_mappings: List[ProviderMappingCreate] = []
    contacts: List[ContactCreate] = []
    chains: List[ChainCreate] = []

class HotelRead(HotelCreate):
    id: int
    primary_photo: Optional[str] 

    class Config:
        from_attributes = True

class HotelUpdate(BaseModel):
    ittid: Optional[str] = Field(None, max_length=50)
    name: Optional[str] = Field(None, max_length=255)
    latitude: Optional[str]
    longitude: Optional[str]
    address_line1: Optional[str]
    address_line2: Optional[str]
    postal_code: Optional[str]
    rating: Optional[str]
    property_type: Optional[str]
    primary_photo: Optional[str] 
    map_status: Optional[str]
    content_update_status: Optional[str]
    locations: Optional[List[LocationCreate]] = []
    provider_mappings: Optional[List[ProviderMappingCreate]] = []
    contacts: Optional[List[ContactCreate]] = []
    chains: Optional[List[ChainCreate]] = []

# Rebuild forward references
UserCreate.model_rebuild()
HotelCreate.model_rebuild()
HotelCreateDemo.model_rebuild()
User.model_rebuild()
Token.model_rebuild()
UserResponse.model_rebuild()

from models import PointAllocationType

class GivePointsRequest(BaseModel):
    receiver_id: str
    allocation_type: PointAllocationType


# --- New schemas for `get-all-basic-info-using-a-supplier` ---

class ProviderProperty(BaseModel):
    provider_name: str = Field(..., description="The supplier/provider name to filter hotels by")

class ProviderItem(BaseModel):
    name: str = Field(..., description="Provider name")
    provider_id: str = Field(..., description="Provider-specific hotel ID")
    status: str = Field(..., description="Status of the mapping (e.g., 'update')")

class LocationItem(BaseModel):
    id: int = Field(..., description="Location record ID")
    name: str = Field(..., description="City name")
    location_id: str = Field(..., description="City location code")
    status: str = Field(..., description="Status (e.g., 'update')")
    latitude: Optional[float] = Field(None, description="Hotel latitude")
    longitude: Optional[float] = Field(None, description="Hotel longitude")
    address: Optional[str] = Field(None, description="Full address")
    postal_code: Optional[str] = Field(None, description="Postal code if available")
    city_id: Optional[int] = Field(None, description="City record ID")
    city_name: Optional[str] = Field(None, description="City name")
    city_code: Optional[str] = Field(None, description="City code")
    state: Optional[str] = Field(None, description="State or region name")
    country_name: Optional[str] = Field(None, description="Country name")
    country_code: Optional[str] = Field(None, description="Country code")

class ContactItem(BaseModel):
    id: int = Field(..., description="Hotel ID for contact grouping")
    phone: List[str] = Field(default_factory=list, description="List of phone numbers")
    email: List[str] = Field(default_factory=list, description="List of email addresses")
    website: List[str] = Field(default_factory=list, description="List of websites")
    fax: List[str] = Field(default_factory=list, description="List of fax numbers")

class HotelItem(BaseModel):
    ittid: str = Field(..., description="Internal travel technology ID")
    name: str = Field(..., description="Hotel name")
    country_name: str = Field(..., description="Country name")
    country_code: str = Field(..., description="Country code")
    type: str = Field(..., description="Record type (should be 'hotel')")
    provider: List[ProviderItem] = Field(..., description="List of provider mappings")
    location: List[LocationItem] = Field(..., description="List of location entries")
    contract: List[ContactItem] = Field(..., description="List containing contact info objects")

class GetAllHotelResponse(BaseModel):
    resume_key: Optional[str] = Field(None, description="Resume key for next page")
    total_hotel: int = Field(..., description="Total number of hotels for this supplier")
    show_hotels_this_page: int
    hotel: List[HotelItem] = Field(..., description="Page of hotel records")


class AddRateTypeRequest(BaseModel):
    ittid: str
    provider_mapping_id: int
    provider_name: str
    provider_id: str
    room_title: str
    rate_name: str
    sell_per_night: float

class UpdateRateTypeRequest(BaseModel):
    ittid: str
    provider_mapping_id: int
    provider_name: str 
    provider_id: str   
    room_title: str
    rate_name: str
    sell_per_night: float


class BasicMappingResponse(BaseModel):
    hotel_name: str
    lon: Optional[float]
    lat: Optional[float]
    room_title: str
    rate_type: str
    star_rating: Optional[str]
    primary_photo: Optional[str]
    address: Optional[str]
    sell_per_night: Optional[float]
    vervotech: Optional[str]
    giata: Optional[str]

    class Config:
        extra = "allow"


# --- New User Dashboard Schemas ---

class TimeSeriesDataPoint(BaseModel):
    """Single data point in a time-series"""
    date: str = Field(..., description="Date in YYYY-MM-DD format", example="2024-11-15")
    value: int = Field(..., description="Value for this date", example=5)

class PendingStep(BaseModel):
    """Pending onboarding step"""
    action: str = Field(..., description="Action identifier", example="supplier_assignment")
    description: str = Field(..., description="Human-readable description", example="Contact administrator to request supplier access")
    estimated_time: str = Field(..., description="Estimated time to complete", example="1-2 business days")

class OnboardingProgress(BaseModel):
    """User onboarding progress tracking"""
    completion_percentage: int = Field(..., ge=0, le=100, description="Onboarding completion percentage (0-100)", example=33)
    completed_steps: List[str] = Field(..., description="List of completed onboarding steps", example=["account_created"])
    pending_steps: List[PendingStep] = Field(..., description="List of pending onboarding steps")

class AccountInfo(BaseModel):
    """User account information and status"""
    user_id: str = Field(..., description="User unique identifier", example="abc1234567")
    username: str = Field(..., description="Username", example="john_doe")
    email: str = Field(..., description="User email address", example="john@example.com")
    account_status: str = Field(..., description="Current account status", example="pending_activation")
    created_at: str = Field(..., description="Account creation timestamp (ISO 8601)", example="2024-11-01T10:30:00")
    days_since_registration: int = Field(..., description="Days since account was created", example=14)
    onboarding_progress: OnboardingProgress = Field(..., description="Onboarding progress details")

class SupplierResources(BaseModel):
    """User supplier permissions status"""
    active_count: int = Field(..., description="Number of active supplier permissions", example=0)
    total_available: int = Field(..., description="Total suppliers available in the system", example=5)
    assigned_suppliers: List[str] = Field(..., description="List of assigned supplier names", example=[])
    pending_assignment: bool = Field(..., description="Whether supplier assignment is pending", example=True)

class PointResources(BaseModel):
    """User point allocation status"""
    current_balance: int = Field(..., description="Current point balance", example=0)
    total_allocated: int = Field(..., description="Total points ever allocated", example=0)
    package_type: Optional[str] = Field(None, description="Point package type", example=None)
    pending_allocation: bool = Field(..., description="Whether point allocation is pending", example=True)

class UserResources(BaseModel):
    """User resources (suppliers and points)"""
    suppliers: SupplierResources = Field(..., description="Supplier permission details")
    points: PointResources = Field(..., description="Point allocation details")

class AvailableSupplier(BaseModel):
    """Available supplier information"""
    name: str = Field(..., description="Supplier name", example="Agoda")
    hotel_count: int = Field(..., description="Number of hotels from this supplier", example=12000)
    last_updated: str = Field(..., description="Last update timestamp (ISO 8601)", example="2024-11-15T08:00:00")

class AvailablePackage(BaseModel):
    """Available point package information"""
    type: str = Field(..., description="Package type identifier", example="one_year_package")
    description: str = Field(..., description="Package description", example="Annual subscription with high point allocation")
    example_points: str = Field(..., description="Example point allocation", example="100000")

class PlatformOverview(BaseModel):
    """Platform-wide statistics and available resources"""
    total_users: int = Field(..., description="Total registered users", example=150)
    total_hotels: int = Field(..., description="Total hotels in the system", example=50000)
    total_mappings: int = Field(..., description="Total provider mappings", example=45000)
    available_suppliers: List[AvailableSupplier] = Field(..., description="List of available suppliers")
    available_packages: List[AvailablePackage] = Field(..., description="List of available point packages")

class UserLoginMetrics(BaseModel):
    """User login activity metrics"""
    total_count: int = Field(..., description="Total login count", example=5)
    last_login: Optional[str] = Field(None, description="Last login timestamp (ISO 8601)", example="2024-11-15T09:30:00")
    time_series: List[TimeSeriesDataPoint] = Field(..., description="30-day login time-series data")

class APIRequestMetrics(BaseModel):
    """User API request metrics"""
    total_count: int = Field(..., description="Total API request count", example=0)
    time_series: List[TimeSeriesDataPoint] = Field(..., description="30-day API request time-series data")

class ActivityMetrics(BaseModel):
    """User activity metrics and timeline"""
    user_logins: UserLoginMetrics = Field(..., description="User login activity")
    api_requests: APIRequestMetrics = Field(..., description="User API request activity")

class TrendData(BaseModel):
    """Platform trend data with metadata"""
    title: str = Field(..., description="Trend title", example="New User Registrations")
    unit: str = Field(..., description="Data unit", example="users")
    data_type: str = Field(..., description="Data type", example="count")
    time_series: List[TimeSeriesDataPoint] = Field(..., description="30-day trend time-series data")

class PlatformTrends(BaseModel):
    """Platform-wide trend data"""
    user_registrations: TrendData = Field(..., description="User registration trends")
    hotel_updates: TrendData = Field(..., description="Hotel update trends")

class RecommendationStep(BaseModel):
    """Recommended next step for user"""
    priority: int = Field(..., description="Priority order (1 = highest)", example=1)
    action: str = Field(..., description="Action title", example="Request Supplier Access")
    description: str = Field(..., description="Detailed description", example="Contact your administrator to request access to hotel suppliers")
    contact_info: str = Field(..., description="Contact information", example="admin@hita-system.com")
    estimated_time: str = Field(..., description="Estimated completion time", example="1-2 business days")

class Recommendations(BaseModel):
    """Personalized recommendations for user"""
    next_steps: List[RecommendationStep] = Field(..., description="List of recommended next steps")
    estimated_activation_time: str = Field(..., description="Estimated time to full activation", example="2-3 business days")

class DashboardMetadata(BaseModel):
    """Dashboard response metadata"""
    timestamp: str = Field(..., description="Response generation timestamp (ISO 8601)", example="2024-11-15T10:00:00")
    cache_status: str = Field(..., description="Cache status (cached/fresh)", example="cached")
    data_freshness: Dict[str, str] = Field(..., description="Data freshness timestamps for each component")

class NewUserDashboardResponse(BaseModel):
    """Complete new user dashboard response"""
    account_info: AccountInfo = Field(..., description="User account information and onboarding progress")
    user_resources: UserResources = Field(..., description="User supplier and point resources")
    platform_overview: PlatformOverview = Field(..., description="Platform-wide statistics and available resources")
    activity_metrics: ActivityMetrics = Field(..., description="User activity metrics and timeline")
    platform_trends: PlatformTrends = Field(..., description="Platform-wide trend data")
    recommendations: Recommendations = Field(..., description="Personalized recommendations for account activation")
    metadata: DashboardMetadata = Field(..., description="Response metadata and cache information")
    
    class Config:
        json_schema_extra = {
            "example": {
                "account_info": {
                    "user_id": "abc1234567",
                    "username": "john_doe",
                    "email": "john@example.com",
                    "account_status": "pending_activation",
                    "created_at": "2024-11-01T10:30:00",
                    "days_since_registration": 14,
                    "onboarding_progress": {
                        "completion_percentage": 33,
                        "completed_steps": ["account_created"],
                        "pending_steps": [
                            {
                                "action": "supplier_assignment",
                                "description": "Contact administrator to request supplier access",
                                "estimated_time": "1-2 business days"
                            }
                        ]
                    }
                },
                "user_resources": {
                    "suppliers": {
                        "active_count": 0,
                        "total_available": 5,
                        "assigned_suppliers": [],
                        "pending_assignment": True
                    },
                    "points": {
                        "current_balance": 0,
                        "total_allocated": 0,
                        "package_type": None,
                        "pending_allocation": True
                    }
                },
                "platform_overview": {
                    "total_users": 150,
                    "total_hotels": 50000,
                    "total_mappings": 45000,
                    "available_suppliers": [
                        {
                            "name": "Agoda",
                            "hotel_count": 12000,
                            "last_updated": "2024-11-15T08:00:00"
                        }
                    ],
                    "available_packages": [
                        {
                            "type": "one_year_package",
                            "description": "Annual subscription",
                            "example_points": "100000"
                        }
                    ]
                },
                "activity_metrics": {
                    "user_logins": {
                        "total_count": 5,
                        "last_login": "2024-11-15T09:30:00",
                        "time_series": [
                            {"date": "2024-10-16", "value": 0},
                            {"date": "2024-11-15", "value": 2}
                        ]
                    },
                    "api_requests": {
                        "total_count": 0,
                        "time_series": [
                            {"date": "2024-10-16", "value": 0}
                        ]
                    }
                },
                "platform_trends": {
                    "user_registrations": {
                        "title": "New User Registrations",
                        "unit": "users",
                        "data_type": "count",
                        "time_series": [
                            {"date": "2024-10-16", "value": 2}
                        ]
                    },
                    "hotel_updates": {
                        "title": "Hotel Data Updates",
                        "unit": "hotels",
                        "data_type": "count",
                        "time_series": [
                            {"date": "2024-10-16", "value": 150}
                        ]
                    }
                },
                "recommendations": {
                    "next_steps": [
                        {
                            "priority": 1,
                            "action": "Request Supplier Access",
                            "description": "Contact your administrator",
                            "contact_info": "admin@hita-system.com",
                            "estimated_time": "1-2 business days"
                        }
                    ],
                    "estimated_activation_time": "2-3 business days"
                },
                "metadata": {
                    "timestamp": "2024-11-15T10:00:00",
                    "cache_status": "cached",
                    "data_freshness": {
                        "account_info": "2024-11-15T10:00:00"
                    }
                }
            }
        }
