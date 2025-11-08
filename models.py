from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Enum as SQLEnum, Boolean, ForeignKey, JSON, Text, func, case, or_
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, Mapped
from sqlalchemy import MetaData
from sqlalchemy.ext.hybrid import hybrid_property
from datetime import datetime, timedelta
from database import Base
from enum import Enum

# User Roles
class UserRole(str, Enum):
    SUPER_USER = "super_user"
    ADMIN_USER = "admin_user"
    GENERAL_USER = "general_user"


# Point Allocation Type
class PointAllocationType(str, Enum):
    ADMIN_USER_PACKAGE = "admin_user_package"
    ONE_YEAR_PACKAGE = "one_year_package"
    ONE_MONTH_PACKAGE = "one_month_package"
    PER_REQUEST_POINT = "per_request_point"
    GUEST_POINT = "guest_point"

# User Model
class User(Base):
    __tablename__ = "users"

    id = Column(String(10), primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True)
    email = Column(String(100), unique=True, index=True)
    hashed_password = Column(String(255))
    role = Column(SQLEnum(*[role.value for role in UserRole], name="user_role_enum", native_enum=False), default=UserRole.GENERAL_USER.value, nullable=False)  # Fixed SQLEnum initialization
    api_key = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)
    created_by = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    sent_transactions = relationship("PointTransaction", foreign_keys="[PointTransaction.giver_id]", back_populates="giver")
    received_transactions = relationship("PointTransaction", foreign_keys="[PointTransaction.receiver_id]", back_populates="receiver")
    user_points = relationship("UserPoint", back_populates="user", foreign_keys="[UserPoint.user_id]")  # Explicitly specify foreign_keys
    provider_permissions = relationship("UserProviderPermission", back_populates="user")
    activity_logs = relationship("UserActivityLog", back_populates="user")
    sessions = relationship("UserSession", back_populates="user")

    # Computed properties and hybrid properties
    @hybrid_property
    def activity_status(self):
        """Determine if user is active based on recent transactions"""
        from sqlalchemy.orm import object_session
        session = object_session(self)
        if session is None:
            return "Unknown"
        
        recent_activity = session.query(PointTransaction).filter(
            or_(
                PointTransaction.giver_id == self.id,
                PointTransaction.receiver_id == self.id
            ),
            PointTransaction.created_at >= datetime.utcnow() - timedelta(days=7)
        ).first()
        return "Active" if recent_activity else "Inactive"

    @hybrid_property
    def current_point_balance(self):
        """Get current point balance"""
        user_points = self.user_points[0] if self.user_points else None
        return user_points.current_points if user_points else 0

    @hybrid_property
    def total_point_balance(self):
        """Get total point balance"""
        user_points = self.user_points[0] if self.user_points else None
        return user_points.total_points if user_points else 0

    @hybrid_property
    def active_supplier_list(self):
        """Get list of active suppliers"""
        return [perm.provider_name for perm in self.provider_permissions]

    @hybrid_property
    def total_requests(self):
        """Get total number of requests (transactions) made by user"""
        return len(self.sent_transactions) + len(self.received_transactions)

    @hybrid_property
    def paid_status(self):
        """Determine paid status based on point balance and transactions"""
        if self.current_point_balance > 0:
            return "Paid"
        elif self.total_point_balance > 0:
            return "Used"
        else:
            return "Unpaid"

    @hybrid_property
    def last_login(self):
        """Get last login time from most recent session"""
        if self.sessions:
            latest_session = max(self.sessions, key=lambda s: s.last_activity)
            return latest_session.last_activity
        return None


# User Activity Log Model
class UserActivityLog(Base):
    __tablename__ = "user_activity_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(10), ForeignKey("users.id"), nullable=True)  # Allow null for unauthenticated requests
    action = Column(String(50), nullable=False)  # login, logout, create_user, update_user, delete_user, etc.
    details = Column(JSON, nullable=True)  # Additional details about the action
    ip_address = Column(String(45), nullable=True)  # Support both IPv4 and IPv6
    user_agent = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="activity_logs")


# User Session Model
class UserSession(Base):
    __tablename__ = "user_sessions"

    id = Column(String(50), primary_key=True)  # Session token/ID
    user_id = Column(String(10), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_activity = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)

    # Relationships
    user = relationship("User", back_populates="sessions")


# Blacklisted Token Model
class BlacklistedToken(Base):
    __tablename__ = "blacklisted_tokens"

    id = Column(Integer, primary_key=True, index=True)
    token = Column(String(255), unique=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

# Point Transaction Model
class PointTransaction(Base):
    __tablename__ = "point_transactions"

    id = Column(Integer, primary_key=True, index=True)
    giver_id = Column(String(10), ForeignKey("users.id"))
    giver_email = Column(String(100), ForeignKey("users.email"))
    receiver_id = Column(String(10), ForeignKey("users.id"))
    receiver_email = Column(String(100), ForeignKey("users.email"))
    points = Column(Integer, nullable=False)
    transaction_type = Column(String(20), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    giver = relationship("User", foreign_keys=[giver_id], back_populates="sent_transactions")
    receiver = relationship("User", foreign_keys=[receiver_id], back_populates="received_transactions")

# User Point Model
class UserPoint(Base):
    __tablename__ = "user_points"

    user_id = Column(String(10), ForeignKey("users.id"), primary_key=True)
    user_email = Column(String(100), ForeignKey("users.email"))
    total_points = Column(Integer, default=0)
    current_points = Column(Integer, default=0)
    total_used_points = Column(Integer, default=0)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="user_points", foreign_keys=[user_id])  # Explicitly specify foreign_keys


class UserProviderPermission(Base):
    __tablename__ = "user_provider_permissions"

    id: Mapped[int] = Column(Integer, primary_key=True)
    user_id: Mapped[str] = Column(String(50), ForeignKey("users.id"))
    provider_name: Mapped[str] = Column(String(50))

    # Relationships
    user: Mapped["User"] = relationship(back_populates="provider_permissions")


class DemoHotel(Base):
    __tablename__ = "demo_hotel"  # Ensure this matches the table name in your database

    id = Column(Integer, primary_key=True, index=True)  # Primary key
    ittid = Column(String(50), nullable=False)
    name = Column(String(255), nullable=False)
    latitude = Column(String(50), nullable=True)
    longitude = Column(String(50), nullable=True)
    rating = Column(String(10), nullable=True) 
    address_line1 = Column(String(255), nullable=True)
    address_line2 = Column(String(255), nullable=True)
    city_name = Column(String(100), nullable=True)
    state_name = Column(String(100), nullable=True)
    state_code = Column(String(10), nullable=True)
    country_name = Column(String(100), nullable=True)
    country_code = Column(String(10), nullable=True)
    postal_code = Column(String(20), nullable=True)
    city_code = Column(String(50), nullable=True)
    city_location_id = Column(String(50), nullable=True)
    master_city_name = Column(String(100), nullable=True)
    location_ids = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Hotel(Base):
    __tablename__ = "hotels"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ittid = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    latitude = Column(String(50), nullable=True)
    longitude = Column(String(50), nullable=True) 
    address_line1 = Column(String(255), nullable=True)
    address_line2 = Column(String(255), nullable=True)
    postal_code = Column(String(20), nullable=True)
    rating = Column(String(10), nullable=True)  # Adjusted to string for simplicity
    property_type = Column(String(100), nullable=True)
    primary_photo = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    map_status = Column(SQLEnum("new", "pending", "updated", name="map_status_enum"), default="pending")
    content_update_status = Column(String(15), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    locations = relationship("Location", back_populates="hotel")
    provider_mappings = relationship("ProviderMapping", back_populates="hotel")
    contacts = relationship("Contact", back_populates="hotel")
    chains = relationship("Chain", back_populates="hotel")
    rate_types = relationship("RateTypeInfo", back_populates="hotel") 


class Location(Base):
    __tablename__ = "locations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ittid = Column(String(100), ForeignKey("hotels.ittid"), nullable=False)
    city_name = Column(String(100), nullable=True)
    state_name = Column(String(100), nullable=True)
    state_code = Column(String(50), nullable=True)
    country_name = Column(String(100), nullable=True)
    country_code = Column(String(2), nullable=True)
    master_city_name = Column(String(100), nullable=True)
    city_code = Column(String(50), nullable=True)
    city_location_id = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    hotel = relationship("Hotel", back_populates="locations")


class ProviderMapping(Base):
    __tablename__ = "provider_mappings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ittid = Column(String(100), ForeignKey("hotels.ittid"), nullable=False)
    provider_name = Column(String(50), nullable=False)
    provider_id = Column(String(255), nullable=False)
    system_type = Column(
                        SQLEnum('a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', name="system_type_enum"),
                        nullable=False,
                        default='a')
    vervotech_id = Column(String(50), nullable=True)
    giata_code = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    hotel = relationship("Hotel", back_populates="provider_mappings")

    # Existing columns...
    rate_types = relationship("RateTypeInfo", back_populates="provider_mapping")


class RateTypeInfo(Base):
    __tablename__ = "rate_type_info"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ittid = Column(String(100), ForeignKey("hotels.ittid"), nullable=False)
    provider_mapping_id = Column(Integer, ForeignKey("provider_mappings.id"), nullable=False)
    room_title = Column(String(255), nullable=False)
    rate_name = Column(String(255), nullable=False)
    sell_per_night = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    provider_mapping = relationship("ProviderMapping", back_populates="rate_types")
    hotel = relationship("Hotel", back_populates="rate_types")  

class SummaryStatus(Base):
    __tablename__ = "summary_status"

    id = Column(Integer, primary_key=True, autoincrement=True)
    total_supplier_information = Column(Integer, nullable=False, default=0)
    total_hotel_information = Column(Integer, nullable=False, default=0)
    total_supplier_update = Column(Integer, nullable=False, default=0)
    total_hotel_update = Column(Integer, nullable=False, default=0)
    # total_rooms = Column(Integer, nullable=False, default=0)  # New column
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Contact(Base):
    __tablename__ = "contacts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ittid = Column(String(100), ForeignKey("hotels.ittid"), nullable=False)
    contact_type = Column(SQLEnum("phone", "email", "fax", "website", name="contact_type_enum"), nullable=False)
    value = Column(String(255), nullable=False)

    # Relationships
    hotel = relationship("Hotel", back_populates="contacts")


class Chain(Base):
    __tablename__ = "chains"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ittid = Column(String(100), ForeignKey("hotels.ittid"), nullable=False)
    chain_name = Column(String(100), nullable=True)
    chain_code = Column(String(50), nullable=True)
    brand_name = Column(String(100), nullable=True)

    # Relationships
    hotel = relationship("Hotel", back_populates="chains")

class UserIPWhitelist(Base):
    __tablename__ = "user_ip_whitelist"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(50), ForeignKey("users.id"), nullable=False)
    ip_address = Column(String(45), nullable=False)  # Support both IPv4 and IPv6
    created_by = Column(String(50), nullable=False)  # Admin/Super user who added this
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)

    # Relationships
    user = relationship("User", backref="ip_whitelist")


class SupplierSummary(Base):
    __tablename__ = "supplier_summary"

    id = Column(Integer, primary_key=True, autoincrement=True)
    provider_name = Column(String(50), unique=True, nullable=False, index=True)
    total_hotels = Column(Integer, nullable=False, default=0)
    total_mappings = Column(Integer, nullable=False, default=0)
    last_updated = Column(DateTime, nullable=True)
    summary_generated_at = Column(DateTime, nullable=False, default=datetime.utcnow)