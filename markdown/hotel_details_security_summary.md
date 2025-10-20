# 🔒 Hotel Details Endpoint Security Implementation

## 📋 Endpoint Overview

### `/v1.0/hotel/details` - Get Hotel Details with Supplier Filtering

- **File**: `backend/routes/hotelFormattingData.py`
- **Method**: POST
- **Access**: All authenticated users (with supplier-based filtering)
- **Purpose**: Get formatted hotel details from raw supplier data
- **Security Model**: Supplier permission-based access control

## 🔐 Security Implementation

### Access Control Logic

#### For General Users:

```python
# Check if user has permission for the requested supplier
user_supplier_permission = db.query(models.UserProviderPermission).filter(
    models.UserProviderPermission.user_id == current_user.id,
    models.UserProviderPermission.provider_name == supplier_code
).first()

if not user_supplier_permission:
    # Access denied - supplier not active for user
    raise HTTPException(status_code=403, detail="Supplier not active")
```

#### For Super Users & Admin Users:

```python
# Super users and admin users bypass supplier permission checks
if current_user.role in [UserRole.SUPER_USER, UserRole.ADMIN_USER]:
    # Full access to all suppliers
    pass
```

### Response Codes

- **200**: Success (User has supplier permission + hotel data found)
- **403**: Forbidden (Supplier not active for user)
- **404**: Not Found (Hotel data file not found)
- **401**: Unauthorized (No valid authentication token)
- **500**: Internal Server Error (File processing issues)

## 🎯 User Access Matrix

| User Role           | Access Level      | Supplier Filtering         | Notes                    |
| ------------------- | ----------------- | -------------------------- | ------------------------ |
| **Super User**      | ✅ Full Access    | ❌ No Filtering            | Can access all suppliers |
| **Admin User**      | ✅ Full Access    | ❌ No Filtering            | Can access all suppliers |
| **General User**    | ✅ Limited Access | ✅ Filtered by Permissions | Only active suppliers    |
| **Unauthenticated** | ❌ No Access      | N/A                        | Must authenticate first  |

## 📝 Audit Logging

### Success Access (MEDIUM Security Level)

```json
{
  "endpoint": "/v1.0/hotel/details",
  "action": "access_hotel_details",
  "supplier_code": "hotelbeds",
  "hotel_id": "123456",
  "user_role": "general_user",
  "security_level": "medium"
}
```

### Denied Access (HIGH Security Level)

```json
{
  "endpoint": "/v1.0/hotel/details",
  "action": "access_denied_supplier_not_active",
  "supplier_code": "booking",
  "hotel_id": "789012",
  "reason": "User does not have permission for this supplier",
  "security_level": "high"
}
```

## 🧪 Testing Scenarios

### Test Script: `test_hotel_details_supplier_permissions.py`

#### Scenario 1: Unauthenticated Access

```bash
# Expected: 401 Unauthorized
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{"supplier_code": "hotelbeds", "hotel_id": "123456"}' \
  http://localhost:8000/v1.0/hotel/details
```

#### Scenario 2: General User - Inactive Supplier

```bash
# Expected: 403 Forbidden
curl -X POST \
  -H "Authorization: Bearer <general_user_token>" \
  -H "Content-Type: application/json" \
  -d '{"supplier_code": "booking", "hotel_id": "123456"}' \
  http://localhost:8000/v1.0/hotel/details
```

#### Scenario 3: General User - Active Supplier

```bash
# Expected: 200 Success or 404 Not Found
curl -X POST \
  -H "Authorization: Bearer <general_user_token>" \
  -H "Content-Type: application/json" \
  -d '{"supplier_code": "hotelbeds", "hotel_id": "123456"}' \
  http://localhost:8000/v1.0/hotel/details
```

#### Scenario 4: Admin User - Any Supplier

```bash
# Expected: 200 Success or 404 Not Found (never 403)
curl -X POST \
  -H "Authorization: Bearer <admin_user_token>" \
  -H "Content-Type: application/json" \
  -d '{"supplier_code": "any_supplier", "hotel_id": "123456"}' \
  http://localhost:8000/v1.0/hotel/details
```

## 🔧 Supplier Permission Management

### Grant Supplier Permission

To allow a general user to access a specific supplier:

```bash
POST /v1.0/permissions/activate_supplier
{
  "user_id": "general_user_id",
  "provider_names": ["hotelbeds", "booking"]
}
```

### Check User's Active Suppliers

```bash
GET /v1.0/user/active_my_supplier
Authorization: Bearer <user_token>
```

## 📊 Error Response Examples

### 403 Forbidden (Supplier Not Active)

```json
{
  "detail": "Access denied. You do not have permission to access data from supplier 'booking'. Please contact your administrator to activate this supplier."
}
```

### 404 Not Found (Hotel Data Missing)

```json
{
  "detail": "Hotel data not found for supplier 'hotelbeds' and hotel ID '123456'"
}
```

### 401 Unauthorized (No Token)

```json
{
  "detail": "Not authenticated"
}
```

## 🔍 Request/Response Examples

### Request Format

```json
{
  "supplier_code": "hotelbeds",
  "hotel_id": "1622759"
}
```

### Success Response (200)

```json
{
  "hotel_id": "1622759",
  "name": "Hotel Example",
  "address": "123 Main St",
  "city": "Barcelona",
  "country": "Spain",
  "formatted_data": {
    // ... formatted hotel details
  }
}
```

## 🛡️ Security Features

### 1. **Authentication Required**

- All requests must include valid JWT token
- Token expiration and blacklist checks

### 2. **Supplier-Based Authorization**

- General users filtered by active supplier permissions
- Admin/Super users have unrestricted access
- Clear error messages for denied access

### 3. **Comprehensive Audit Logging**

- Success access: MEDIUM security level
- Denied access: HIGH security level
- Detailed parameter tracking

### 4. **SecurityMiddleware Protection**

- Rate limiting
- Input sanitization
- IP address validation

## ✅ Implementation Benefits

### For General Users:

- ✅ Can access hotel details for their active suppliers
- ✅ Clear error messages when supplier not active
- ✅ Self-service access to permitted data

### For Administrators:

- ✅ Full audit trail of access attempts
- ✅ Granular supplier permission control
- ✅ Security event monitoring for unauthorized access

### For System Security:

- ✅ Prevents data leakage across suppliers
- ✅ Maintains supplier data segregation
- ✅ Comprehensive logging for compliance

## 🎉 Implementation Status: COMPLETE

### Security Features: All Implemented ✅

- ✅ Authentication required for all access
- ✅ Supplier-based permission filtering
- ✅ Role-based access control
- ✅ Comprehensive audit logging
- ✅ Clear error messaging
- ✅ SecurityMiddleware integration

### Access Control: Properly Implemented ✅

- ✅ **General Users**: Access filtered by supplier permissions
- ✅ **Admin Users**: Full access to all suppliers
- ✅ **Super Users**: Full access to all suppliers
- ✅ **Unauthenticated**: Access denied

The `/v1.0/hotel/details` endpoint now provides secure, permission-based access to hotel data while maintaining proper audit trails and user experience!
