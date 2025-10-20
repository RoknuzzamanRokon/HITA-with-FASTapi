# Active Supplier Validation System for Hotel ITTID Endpoint

## Overview

The `/v1.0/content/get_hotel_with_ittid/{ittid}` endpoint now requires that hotels have **active suppliers** (provider mappings) to be accessible. If no active suppliers are found for a given ITTID, the endpoint returns a clear error message: "Cannot active supplier with this ittid".

## 🔍 Validation Logic

### Active Supplier Check Process

1. **Hotel Existence**: Verify hotel exists in database
2. **Supplier Validation**: Check for active provider mappings
3. **User Permission**: Validate user access to suppliers (for general users)
4. **Response Generation**: Return hotel data with supplier information

### Validation Flow

```python
# 1. Check if hotel exists
hotel = db.query(models.Hotel).filter(models.Hotel.ittid == ittid).first()
if not hotel:
    raise HTTPException(404, detail=f"Hotel with id '{ittid}' not found.")

# 2. Check for ANY provider mappings (active suppliers)
all_provider_mappings = db.query(models.ProviderMapping).filter(
    models.ProviderMapping.ittid == ittid
).all()

if not all_provider_mappings:
    raise HTTPException(404, detail=f"Cannot active supplier with this ittid '{ittid}'. No supplier mappings found for this hotel.")

# 3. Check user-specific access (for general users)
if current_user.role == models.UserRole.GENERAL_USER:
    # Validate user has access to at least one supplier for this hotel
    accessible_mappings = check_user_supplier_access(ittid, user_permissions)
    if not accessible_mappings:
        raise HTTPException(403, detail="Cannot access suppliers for this ittid")
```

## 🚨 Error Scenarios and Messages

### 1. Hotel Not Found

```json
{
  "detail": "Hotel with id '99999' not found."
}
```

**HTTP Status**: 404 Not Found
**Cause**: ITTID doesn't exist in the hotels table

### 2. No Active Suppliers

```json
{
  "detail": "Cannot active supplier with this ittid '12345'. No supplier mappings found for this hotel."
}
```

**HTTP Status**: 404 Not Found
**Cause**: Hotel exists but has no provider mappings (no active suppliers)

### 3. No Accessible Suppliers (General Users)

```json
{
  "detail": "Cannot access suppliers for this ittid '12345'. Available suppliers: Expedia, Booking.com. Contact admin for access."
}
```

**HTTP Status**: 403 Forbidden
**Cause**: Hotel has suppliers but user doesn't have permission to access any of them

### 4. No User Permissions

```json
{
  "detail": "Do not have permission or not active"
}
```

**HTTP Status**: 403 Forbidden
**Cause**: General user has no supplier permissions at all

## ✅ Successful Response Format

### Enhanced Response Structure

```json
{
  "hotel": {
    "id": 123,
    "ittid": "12345",
    "name": "Example Hotel",
    "property_type": "Hotel",
    "rating": 4.5,
    "created_at": "2024-01-01T10:00:00.000Z",
    "updated_at": "2024-01-01T12:00:00.000Z"
  },
  "provider_mappings": [
    {
      "id": 456,
      "provider_id": "EXP123",
      "provider_name": "Expedia",
      "system_type": "OTA",
      "giata_code": "789",
      "vervotech_id": "VT456"
    }
  ],
  "locations": [...],
  "chains": [...],
  "contacts": [...],
  "supplier_info": {
    "total_active_suppliers": 3,
    "accessible_suppliers": 2,
    "supplier_names": ["Expedia", "Booking.com"]
  }
}
```

### New Response Fields

- **`provider_mappings`**: Now included in response (was previously excluded)
- **`supplier_info`**: New section with supplier statistics
  - `total_active_suppliers`: Total number of suppliers for this hotel
  - `accessible_suppliers`: Number of suppliers user can access
  - `supplier_names`: List of accessible supplier names

## 🔒 User Role Behavior

### Access Control Matrix

| User Role        | Hotel Access                     | Supplier Access          | Error Handling          |
| ---------------- | -------------------------------- | ------------------------ | ----------------------- |
| **Super User**   | All hotels with suppliers        | All suppliers            | Standard validation     |
| **Admin User**   | All hotels with suppliers        | All suppliers            | Standard validation     |
| **General User** | Hotels with accessible suppliers | Permitted suppliers only | Enhanced error messages |

### Role-Specific Logic

```python
if current_user.role == models.UserRole.GENERAL_USER:
    # Check user has supplier permissions
    allowed_providers = get_user_provider_permissions(current_user.id)

    # Check user can access at least one supplier for this hotel
    accessible_mappings = filter_accessible_suppliers(ittid, allowed_providers)

    if not accessible_mappings:
        # Provide helpful error with available suppliers
        available_suppliers = [pm.provider_name for pm in all_provider_mappings]
        raise HTTPException(403, detail=f"Cannot access suppliers for this ittid '{ittid}'. Available suppliers: {', '.join(available_suppliers)}. Contact admin for access.")
else:
    # Super/Admin users get all suppliers
    accessible_mappings = all_provider_mappings
```

## 🧪 Testing

### Test Script

Use `test_active_supplier_validation.py` to verify the validation:

```bash
cd backend
python test_active_supplier_validation.py
```

### Test Scenarios

1. **Valid Hotel with Suppliers**

   - ✅ Should return hotel data with supplier information
   - ✅ Should include provider mappings in response
   - ✅ Should show supplier statistics

2. **Valid Hotel without Suppliers**

   - ❌ Should return 404 with "Cannot active supplier with this ittid" message
   - ✅ Should clearly indicate no suppliers found

3. **Non-existent Hotel**

   - ❌ Should return 404 with "Hotel not found" message
   - ✅ Should distinguish from supplier validation errors

4. **General User Access Control**
   - ✅ Should allow access if user has supplier permissions
   - ❌ Should deny access with helpful error if no permissions
   - ✅ Should list available suppliers in error message

## 📊 Database Queries

### Supplier Validation Queries

```sql
-- Check for any provider mappings for ITTID
SELECT COUNT(*) FROM provider_mappings WHERE ittid = '12345';

-- Get all provider mappings for ITTID
SELECT * FROM provider_mappings WHERE ittid = '12345';

-- Get user-accessible provider mappings
SELECT pm.* FROM provider_mappings pm
JOIN user_provider_permissions upp ON pm.provider_name = upp.provider_name
WHERE pm.ittid = '12345' AND upp.user_id = 'user123';
```

### Performance Considerations

- **Indexed Lookups**: Uses indexed ITTID lookups for efficiency
- **Permission Caching**: User permissions cached per request
- **Minimal Queries**: Optimized query structure to minimize database calls

## 🔧 Implementation Details

### Key Code Changes

```python
# NEW: Active supplier validation
all_provider_mappings = db.query(models.ProviderMapping).filter(
    models.ProviderMapping.ittid == ittid
).all()

if not all_provider_mappings:
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Cannot active supplier with this ittid '{ittid}'. No supplier mappings found for this hotel."
    )

# NEW: Enhanced response with supplier info
response_data = {
    "hotel": serialize_datetime_objects(hotel),
    "provider_mappings": [serialize_datetime_objects(pm) for pm in provider_mappings],  # NOW INCLUDED
    "locations": [serialize_datetime_objects(loc) for loc in locations],
    "chains": [serialize_datetime_objects(chain) for chain in chains],
    "contacts": [serialize_datetime_objects(contact) for contact in contacts],
    "supplier_info": {  # NEW SECTION
        "total_active_suppliers": len(all_provider_mappings),
        "accessible_suppliers": len(provider_mappings),
        "supplier_names": [pm.provider_name for pm in provider_mappings]
    }
}
```

### Error Message Improvements

- **Specific Messages**: Different messages for different failure scenarios
- **Helpful Information**: Include available suppliers in permission errors
- **Admin Guidance**: Clear instructions for resolving access issues

## 🔍 Monitoring and Logging

### Validation Logging

```python
print(f"✅ Active suppliers found for ITTID {ittid}: {len(all_provider_mappings)} suppliers")
print(f"🔓 Point deduction skipped for {current_user.role}: {current_user.email}")
```

### Key Metrics to Monitor

- **Supplier Validation Failures**: Track hotels without active suppliers
- **Permission Denials**: Monitor access control effectiveness
- **Response Times**: Ensure validation doesn't impact performance
- **Error Patterns**: Identify common validation issues

## 🚀 Benefits

### For System Administrators

- **Data Quality**: Ensures only hotels with active suppliers are accessible
- **Clear Diagnostics**: Specific error messages for different failure scenarios
- **Access Control**: Maintains proper supplier-based permissions

### For API Consumers

- **Reliable Data**: Only returns hotels with valid supplier connections
- **Rich Information**: Enhanced response with supplier statistics
- **Clear Errors**: Helpful error messages for troubleshooting

### For General Users

- **Controlled Access**: Only see hotels they have supplier permissions for
- **Helpful Errors**: Clear guidance on how to get access to restricted suppliers
- **Consistent Experience**: Predictable behavior across all requests

## 🔧 Troubleshooting

### Common Issues

#### "Cannot active supplier with this ittid" Error

**Cause**: Hotel exists but has no provider mappings
**Solution**:

1. Check if hotel should have suppliers
2. Add provider mappings if needed
3. Verify supplier data integrity

#### "Cannot access suppliers for this ittid" Error

**Cause**: User lacks permissions for hotel's suppliers
**Solution**:

1. Check user's provider permissions
2. Grant access to required suppliers
3. Verify supplier names match exactly

#### Hotel Not Found Error

**Cause**: ITTID doesn't exist in database
**Solution**:

1. Verify ITTID is correct
2. Check if hotel was deleted
3. Confirm data synchronization

### Debug Commands

```sql
-- Check if hotel exists
SELECT * FROM hotels WHERE ittid = '12345';

-- Check supplier mappings for hotel
SELECT * FROM provider_mappings WHERE ittid = '12345';

-- Check user permissions
SELECT * FROM user_provider_permissions WHERE user_id = 'user123';

-- Check accessible suppliers for user
SELECT pm.provider_name, pm.provider_id
FROM provider_mappings pm
JOIN user_provider_permissions upp ON pm.provider_name = upp.provider_name
WHERE pm.ittid = '12345' AND upp.user_id = 'user123';
```

## 📈 Future Enhancements

### Potential Improvements

- **Supplier Status**: Add active/inactive status to provider mappings
- **Supplier Metadata**: Include supplier-specific information in responses
- **Caching**: Cache supplier validation results for better performance
- **Analytics**: Track supplier usage patterns and access requests

### Monitoring Enhancements

- **Dashboard**: Supplier validation metrics dashboard
- **Alerts**: Notifications for hotels losing all suppliers
- **Reports**: Regular reports on supplier coverage and access patterns

## 🔄 Migration Notes

### Breaking Changes

- **Response Format**: Now includes `provider_mappings` and `supplier_info`
- **Error Messages**: New error message for hotels without suppliers
- **Validation Logic**: Additional validation step for supplier existence

### Backward Compatibility

- **HTTP Status Codes**: Maintained for existing error scenarios
- **Core Response Structure**: Hotel, locations, chains, contacts remain the same
- **Authentication**: No changes to authentication or authorization flow

## Summary

The active supplier validation system ensures:

- ✅ **Data Quality**: Only hotels with active suppliers are accessible
- ✅ **Clear Error Messages**: Specific messages for different failure scenarios
- ✅ **Enhanced Response**: Includes supplier information and statistics
- ✅ **Access Control**: Maintains role-based and permission-based access
- ✅ **Point Exemption**: Super/admin users remain exempt from point deductions
- ✅ **Helpful Diagnostics**: Error messages include actionable information

This system provides better data integrity, clearer error handling, and enhanced information for API consumers while maintaining all existing security and access control features.
