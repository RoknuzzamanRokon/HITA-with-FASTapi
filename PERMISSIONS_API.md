# Permissions API Documentation

## Overview

The Permissions API provides endpoints for managing user permissions, supplier access control, and IP whitelist management in the HITA system. These endpoints are restricted to admin and super users for security purposes.

**Base Path**: `/v1.0/permissions`

**Authentication**: All endpoints require JWT Bearer token authentication

---

## Table of Contents

1. [Supplier Permission Management](#supplier-permission-management)
2. [Supplier Toggle (Turn On/Off)](#supplier-toggle-turn-onoff)
3. [IP Whitelist Management](#ip-whitelist-management)

---

## Supplier Permission Management

### Grant Provider Permissions

Grants provider/supplier permissions to a general user.

**Endpoint**: `POST /v1.0/permissions/admin/check_activate_supplier`

**Access**: Super User, Admin User only

**Note**: This endpoint is hidden from API documentation (`include_in_schema=False`)

#### Request Body

```json
{
  "provider_activision_list": ["agoda", "booking", "ean"]
}
```

#### Parameters

| Field                      | Type          | Required | Description                               |
| -------------------------- | ------------- | -------- | ----------------------------------------- |
| `user_id`                  | string        | Yes      | Target user ID (query parameter)          |
| `provider_activision_list` | array[string] | Yes      | List of provider names to grant access to |

#### Example Request

```bash
curl -X POST "https://api.example.com/v1.0/permissions/admin/check_activate_supplier?user_id=USER123456" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "provider_activision_list": ["agoda", "booking", "ean"]
  }'
```

#### Response

```json
{
  "message": "Successfully updated permissions for user USER123456 with providers: ['agoda', 'booking', 'ean']"
}
```

#### Error Responses

- **403 Forbidden**: Only super_user or admin_user can grant permissions
- **404 Not Found**: User not found
- **400 Bad Request**: Can only grant permissions to general users

---

### Remove Provider Permissions

Removes provider/supplier permissions from a general user.

**Endpoint**: `POST /v1.0/permissions/admin/deactivate_supplier/{user_id}`

**Access**: Super User, Admin User only

**Note**: This endpoint is hidden from API documentation (`include_in_schema=False`)

#### Request Body

```json
{
  "provider_deactivation_list": ["agoda", "booking"]
}
```

#### Parameters

| Field                        | Type          | Required | Description                                  |
| ---------------------------- | ------------- | -------- | -------------------------------------------- |
| `user_id`                    | string        | Yes      | Target user ID (path parameter)              |
| `provider_deactivation_list` | array[string] | Yes      | List of provider names to remove access from |

#### Example Request

```bash
curl -X POST "https://api.example.com/v1.0/permissions/admin/deactivate_supplier/USER123456" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "provider_deactivation_list": ["agoda", "booking"]
  }'
```

#### Response

```json
{
  "message": "Successfully removed permissions for user USER123456 for providers: ['agoda', 'booking']"
}
```

#### Error Responses

- **403 Forbidden**: Only super_user or admin_user can remove permissions
- **404 Not Found**: User not found
- **400 Bad Request**: Can only remove permissions from general users

---

## Supplier Toggle (Turn On/Off)

### Turn Off Suppliers

Temporarily deactivates specified suppliers for the current authenticated user. This allows users to exclude certain suppliers from their searches without permanently removing permissions.

**Endpoint**: `POST /v1.0/permissions/turn-off-supplier`

**Access**: All authenticated users

#### Request Body

```json
{
  "supplier_name": ["agoda", "booking"]
}
```

#### Parameters

| Field           | Type          | Required | Description                                      |
| --------------- | ------------- | -------- | ------------------------------------------------ |
| `supplier_name` | array[string] | Yes      | List of supplier names to temporarily deactivate |

#### Example Request

```bash
curl -X POST "https://api.example.com/v1.0/permissions/turn-off-supplier" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "supplier_name": ["agoda", "booking"]
  }'
```

#### Response

```json
{
  "message": "Successfully deactivated suppliers: agoda, booking",
  "deactivated_suppliers": ["agoda", "booking"],
  "total_deactivated": 2
}
```

#### Error Responses

- **400 Bad Request**:
  - At least one supplier name is required
  - Cannot find supplier: [supplier_names]
  - This hotel already off (all suppliers already deactivated)
  - These suppliers are already off: [supplier_names]
- **500 Internal Server Error**: Database error occurred

#### Business Logic

- **Admin/Super Users**: Can deactivate any system supplier
- **General Users**: Can only deactivate suppliers they have permission for
- Deactivation is temporary and stored with `TEMP_DEACTIVATED_` prefix
- Already deactivated suppliers will trigger an error
- Suppliers not found or not accessible will trigger an error

---

### Turn On Suppliers

Reactivates previously deactivated suppliers for the current authenticated user.

**Endpoint**: `POST /v1.0/permissions/turn-on-supplier`

**Access**: All authenticated users

#### Request Body

```json
{
  "supplier_name": ["agoda", "booking"]
}
```

#### Parameters

| Field           | Type          | Required | Description                          |
| --------------- | ------------- | -------- | ------------------------------------ |
| `supplier_name` | array[string] | Yes      | List of supplier names to reactivate |

#### Example Request

```bash
curl -X POST "https://api.example.com/v1.0/permissions/turn-on-supplier" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "supplier_name": ["agoda", "booking"]
  }'
```

#### Response

```json
{
  "message": "Successfully activated suppliers: agoda, booking",
  "activated_suppliers": ["agoda", "booking"],
  "total_activated": 2
}
```

#### Error Responses

- **400 Bad Request**:
  - At least one supplier name is required
  - All suppliers are already active: [supplier_names]
  - These suppliers are not turned off: [supplier_names]. Only turned off suppliers can be activated.
- **500 Internal Server Error**: Database error occurred

#### Business Logic

- Only suppliers that were previously turned off can be turned on
- Attempting to activate already active suppliers will trigger an error
- Removes the `TEMP_DEACTIVATED_` prefix from supplier permissions

---

## IP Whitelist Management

### Add IP Addresses to Whitelist

Allows super users and admin users to whitelist IP addresses for specific users. Once configured, users can only access APIs from whitelisted IP addresses.

**Endpoint**: `POST /v1.0/permissions/ip/active-permission`

**Access**: Super User, Admin User only

#### Request Body

```json
{
  "id": "USER123456",
  "ip": [
    "192.168.1.100",
    "10.0.0.50",
    "2001:0db8:85a3:0000:0000:8a2e:0370:7334"
  ]
}
```

#### Parameters

| Field | Type          | Required | Description                                             |
| ----- | ------------- | -------- | ------------------------------------------------------- |
| `id`  | string        | Yes      | Target user ID to whitelist IPs for                     |
| `ip`  | array[string] | Yes      | List of IP addresses to whitelist (IPv4/IPv6 supported) |

#### Example Request

```bash
curl -X POST "https://api.example.com/v1.0/permissions/ip/active-permission" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "id": "USER123456",
    "ip": ["192.168.1.100", "10.0.0.50"]
  }'
```

#### Response

```json
{
  "message": "Successfully processed IP whitelist for user 'john_doe'",
  "target_user": {
    "id": "USER123456",
    "username": "john_doe",
    "email": "john@example.com"
  },
  "ip_summary": {
    "total_requested": 2,
    "newly_added": 2,
    "already_existing": 0,
    "total_active_ips": 2
  },
  "ip_details": {
    "newly_added": ["192.168.1.100", "10.0.0.50"],
    "already_existing": [],
    "all_active_ips": ["192.168.1.100", "10.0.0.50"]
  },
  "created_by": {
    "id": "ADMIN001",
    "username": "admin_user",
    "role": "admin_user"
  },
  "timestamp": "2025-11-17T10:30:00.000000"
}
```

#### Error Responses

- **401 Unauthorized**: User authentication required
- **403 Forbidden**: Only super users and admin users can manage IP whitelists
- **400 Bad Request**:
  - User ID is required
  - At least one IP address is required
  - Invalid IP addresses: [ip_addresses]
- **404 Not Found**: User with ID not found
- **500 Internal Server Error**: Database error occurred

#### Features

- Supports both IPv4 and IPv6 addresses
- Validates IP address format before adding
- Prevents duplicate IP addresses for the same user
- Provides detailed summary of added vs existing IPs
- Audit logging for security tracking

---

### Get User IP Whitelist

Retrieves all active IP whitelist entries for a specific user.

**Endpoint**: `GET /v1.0/permissions/ip/list/{user_id}`

**Access**: Super User, Admin User only

#### Parameters

| Field     | Type   | Required | Description                     |
| --------- | ------ | -------- | ------------------------------- |
| `user_id` | string | Yes      | Target user ID (path parameter) |

#### Example Request

```bash
curl -X GET "https://api.example.com/v1.0/permissions/ip/list/USER123456" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

#### Response

```json
{
  "success": true,
  "user": {
    "id": "USER123456",
    "username": "john_doe",
    "email": "john@example.com"
  },
  "ip_whitelist": {
    "total_entries": 2,
    "entries": [
      {
        "id": 1,
        "ip_address": "192.168.1.100",
        "created_at": "2025-11-17T10:30:00.000000",
        "updated_at": null
      },
      {
        "id": 2,
        "ip_address": "10.0.0.50",
        "created_at": "2025-11-17T10:30:00.000000",
        "updated_at": null
      }
    ]
  },
  "managed_by": {
    "id": "ADMIN001",
    "username": "admin_user"
  }
}
```

#### Error Responses

- **403 Forbidden**: Only super users and admin users can view IP whitelists
- **404 Not Found**: User with ID not found
- **500 Internal Server Error**: Database error occurred

---

### Remove Specific IP Addresses

Removes specific IP addresses from a user's whitelist.

**Endpoint**: `DELETE /v1.0/permissions/ip/remove`

**Access**: Super User, Admin User only

#### Request Body

```json
{
  "user_id": "USER123456",
  "ip_addresses": ["192.168.1.100", "10.0.0.50"]
}
```

#### Parameters

| Field          | Type          | Required | Description                       |
| -------------- | ------------- | -------- | --------------------------------- |
| `user_id`      | string        | Yes      | Target user ID to remove IPs from |
| `ip_addresses` | array[string] | Yes      | List of IP addresses to remove    |

#### Example Request

```bash
curl -X DELETE "https://api.example.com/v1.0/permissions/ip/remove" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "USER123456",
    "ip_addresses": ["192.168.1.100"]
  }'
```

#### Response

```json
{
  "success": true,
  "message": "Successfully removed 1 IP address(es) from whitelist",
  "target_user": {
    "id": "USER123456",
    "username": "john_doe"
  },
  "removed_ips": ["192.168.1.100"],
  "managed_by": {
    "id": "ADMIN001",
    "username": "admin_user"
  }
}
```

#### Error Responses

- **403 Forbidden**: Only super users and admin users can manage IP whitelists
- **404 Not Found**:
  - User with ID not found
  - No matching IP addresses found in whitelist
- **400 Bad Request**: Invalid IP addresses: [ip_addresses]
- **500 Internal Server Error**: Database error occurred

#### Business Logic

- Uses soft delete (sets `is_active = False`)
- Validates IP address format before removal
- Only removes IPs that exist in the whitelist
- Returns list of successfully removed IPs

---

### Clear All IP Whitelist Entries

Removes all IP whitelist entries for a specific user.

**Endpoint**: `DELETE /v1.0/permissions/ip/clear/{user_id}`

**Access**: Super User, Admin User only

#### Parameters

| Field     | Type   | Required | Description                     |
| --------- | ------ | -------- | ------------------------------- |
| `user_id` | string | Yes      | Target user ID (path parameter) |

#### Example Request

```bash
curl -X DELETE "https://api.example.com/v1.0/permissions/ip/clear/USER123456" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

#### Response

```json
{
  "success": true,
  "message": "Successfully cleared 2 IP whitelist entries",
  "target_user": {
    "id": "USER123456",
    "username": "john_doe"
  },
  "cleared_ips": ["192.168.1.100", "10.0.0.50"],
  "cleared_count": 2,
  "managed_by": {
    "id": "ADMIN001",
    "username": "admin_user"
  }
}
```

#### Response (No Entries)

```json
{
  "success": true,
  "message": "No active IP whitelist entries found for user",
  "target_user": {
    "id": "USER123456",
    "username": "john_doe"
  },
  "cleared_count": 0
}
```

#### Error Responses

- **403 Forbidden**: Only super users and admin users can manage IP whitelists
- **404 Not Found**: User with ID not found
- **500 Internal Server Error**: Database error occurred

#### Business Logic

- Uses soft delete (sets `is_active = False`)
- Clears all active IP whitelist entries for the user
- Returns count and list of cleared IPs
- Safe to call even if no entries exist

---

## Common Error Responses

All endpoints may return the following common errors:

### 401 Unauthorized

```json
{
  "detail": "Not authenticated"
}
```

### 403 Forbidden

```json
{
  "detail": "Only super_user or admin_user can grant permissions."
}
```

### 404 Not Found

```json
{
  "detail": "User not found."
}
```

### 500 Internal Server Error

```json
{
  "detail": "An error occurred while processing request: [error details]"
}
```

---

## Security Considerations

1. **Authentication Required**: All endpoints require valid JWT Bearer token
2. **Role-Based Access Control**: Most endpoints restricted to Super User and Admin User roles
3. **IP Validation**: All IP addresses are validated before being added to whitelist
4. **Audit Logging**: All permission changes are logged for security tracking
5. **Soft Deletes**: IP whitelist entries use soft delete for audit trail
6. **Input Sanitization**: All inputs are validated and sanitized

---

## Best Practices

1. **Supplier Management**:

   - Use turn-off/turn-on for temporary supplier exclusions
   - Use grant/remove permissions for permanent access control
   - Always verify supplier names before granting permissions

2. **IP Whitelist**:

   - Use specific IP addresses rather than ranges when possible
   - Regularly review and clean up unused IP entries
   - Document the purpose of each whitelisted IP
   - Use IPv6 when available for better security

3. **Error Handling**:
   - Always check response status codes
   - Handle 403 errors gracefully (insufficient permissions)
   - Validate user IDs before making requests
   - Implement retry logic for 500 errors

---

## Related Documentation

- [User Management API](./USER_API.md)
- [Authentication API](./AUTH_API.md)
- [Security Guidelines](./security/README.md)
- [Product Overview](./product.md)
