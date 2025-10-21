# Delete Operations Documentation

## Overview

The Delete Operations system provides secure deletion capabilities for users and hotel data within the ITT Hotel API (HITA). These operations are restricted to super users only and include comprehensive data cleanup to maintain database integrity.

## Architecture

### Core Components

- **Delete Router**: `/v1.0/delete` prefix
- **Super User Only Access**: Highest security level operations
- **Cascading Deletes**: Comprehensive related data cleanup
- **Data Integrity**: Safe deletion with validation
- **Audit Trail**: Operation logging and tracking

### Security Model

- **Super User Only**: All delete operations require super user privileges
- **Hidden from Schema**: Endpoints excluded from public API documentation
- **Validation Required**: Existence checks before deletion
- **Transaction Safety**: Database transaction management

### Route Prefix

```
/v1.0/delete
```

## User Deletion Endpoints

### Delete User by ID

#### Endpoint

```http
DELETE /v1.0/delete/delete_user/{user_id}
Authorization: Bearer <super_user_token>
```

#### Parameters

| Parameter | Type   | Location | Description            |
| --------- | ------ | -------- | ---------------------- |
| `user_id` | string | path     | Unique user identifier |

#### Request Example

```http
DELETE /v1.0/delete/delete_user/5779356081
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

#### Response

```json
{
  "message": "User with ID 5779356081 has been deleted."
}
```

#### Security Features

- **Super User Only**: Restricted to super user role
- **User Validation**: Checks if user exists before deletion
- **Database Transaction**: Ensures atomic operation

### Delete Super User by ID

#### Endpoint

```http
DELETE /v1.0/delete/delete_super_user/{user_id}
Authorization: Bearer <super_user_token>
```

#### Parameters

| Parameter | Type   | Location | Description                     |
| --------- | ------ | -------- | ------------------------------- |
| `user_id` | string | path     | Super user identifier to delete |

#### Request Example

```http
DELETE /v1.0/delete/delete_super_user/super_001
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

#### Response

```json
{
  "message": "User with ID super_001 has been deleted."
}
```

#### Important Notes

- **Self-Deletion Risk**: Super users can delete other super users
- **System Access**: Ensure at least one super user remains
- **Irreversible Operation**: No recovery mechanism available

## Hotel Deletion Endpoints

### Delete Hotel by ITTID

#### Endpoint

```http
DELETE /v1.0/delete/delete_hotel_by_ittid/{ittid}
Authorization: Bearer <super_user_token>
```

#### Parameters

| Parameter | Type   | Location | Description                 |
| --------- | ------ | -------- | --------------------------- |
| `ittid`   | string | path     | ITT hotel unique identifier |

#### Request Example

```http
DELETE /v1.0/delete/delete_hotel_by_ittid/10000001
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

#### Response

```json
{
  "message": "Hotel with ittid '10000001' and all related data deleted successfully."
}
```

#### Cascading Deletion

The hotel deletion process removes all related data:

1. **Provider Mappings**: All supplier mappings for the hotel
2. **Locations**: Geographic and address information
3. **Contacts**: Phone, email, and other contact details
4. **Chains**: Hotel chain associations
5. **Hotel Record**: Main hotel data

#### Deletion Sequence

```python
# Delete related data first
db.query(ProviderMapping).filter(ProviderMapping.ittid == ittid).delete()
db.query(Location).filter(Location.ittid == ittid).delete()
db.query(Contact).filter(Contact.ittid == ittid).delete()
db.query(models.Chain).filter(models.Chain.ittid == ittid).delete()

# Delete main hotel record
db.delete(hotel)
db.commit()
```

### Delete Hotel Mapping

#### Endpoint

```http
DELETE /v1.0/delete/delete_a_hotel_mapping
Authorization: Bearer <super_user_token>
```

#### Parameters

| Parameter       | Type   | Location | Description                       |
| --------------- | ------ | -------- | --------------------------------- |
| `provider_name` | string | query    | Provider name (e.g., "hotelbeds") |
| `provider_id`   | string | query    | Provider's hotel identifier       |

#### Request Example

```http
DELETE /v1.0/delete/delete_a_hotel_mapping?provider_name=hotelbeds&provider_id=12345
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

#### Response

```json
{
  "message": "Mapping for provider 'hotelbeds', provider_id '12345' deleted successfully."
}
```

#### Use Cases

- **Remove Invalid Mappings**: Delete incorrect provider mappings
- **Provider Cleanup**: Remove mappings for discontinued providers
- **Data Maintenance**: Clean up duplicate or obsolete mappings

## Security and Access Control

### Super User Only Access

All delete operations require super user privileges:

```python
if current_user.role != UserRole.SUPER_USER:
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Only super users can delete hotels."
    )
```

### Access Control Features

- **Role Verification**: Explicit super user role checking
- **Authentication Required**: Valid JWT token mandatory
- **Hidden Endpoints**: Excluded from public API schema
- **Audit Logging**: All operations should be logged

### Security Considerations

- **Irreversible Operations**: No undo functionality
- **Data Loss Risk**: Complete data removal
- **System Impact**: Potential service disruption
- **Access Logging**: Track all deletion activities

## Error Handling

### Common Error Scenarios

#### Access Denied

```json
{
  "detail": "Only super_user can delete users."
}
```

#### User Not Found

```json
{
  "detail": "User not found."
}
```

#### Hotel Not Found

```json
{
  "detail": "Hotel with ittid '10000001' not found."
}
```

#### Mapping Not Found

```json
{
  "detail": "Provider mapping not found."
}
```

### Error Response Format

```json
{
  "detail": "Error message describing the issue"
}
```

## Data Integrity and Safety

### Pre-Deletion Validation

- **Existence Checks**: Verify records exist before deletion
- **Dependency Analysis**: Check for related data
- **Permission Validation**: Confirm user authorization
- **Transaction Management**: Ensure atomic operations

### Cascading Delete Strategy

```python
# Hotel deletion with cascading cleanup
def delete_hotel_with_relations(ittid: str, db: Session):
    # 1. Delete provider mappings
    db.query(ProviderMapping).filter(ProviderMapping.ittid == ittid).delete()

    # 2. Delete location data
    db.query(Location).filter(Location.ittid == ittid).delete()

    # 3. Delete contact information
    db.query(Contact).filter(Contact.ittid == ittid).delete()

    # 4. Delete chain associations
    db.query(Chain).filter(Chain.ittid == ittid).delete()

    # 5. Delete main hotel record
    hotel = db.query(Hotel).filter(Hotel.ittid == ittid).first()
    db.delete(hotel)

    # 6. Commit transaction
    db.commit()
```

### Database Transaction Safety

- **Atomic Operations**: All-or-nothing deletion
- **Rollback Capability**: Automatic rollback on errors
- **Consistency Maintenance**: Preserve database integrity
- **Foreign Key Handling**: Proper constraint management

## Best Practices

### Before Deletion

1. **Backup Data**: Create backups before major deletions
2. **Verify Impact**: Assess deletion impact on system
3. **Check Dependencies**: Identify related data
4. **Confirm Authorization**: Verify super user permissions
5. **Plan Recovery**: Have recovery procedures ready

### During Deletion

1. **Monitor Progress**: Track deletion operations
2. **Handle Errors**: Implement proper error handling
3. **Log Activities**: Record all deletion activities
4. **Validate Results**: Confirm successful deletion
5. **Check Integrity**: Verify database consistency

### After Deletion

1. **Verify Cleanup**: Confirm all related data removed
2. **Update Caches**: Clear relevant cached data
3. **Notify Systems**: Inform dependent systems
4. **Document Changes**: Record deletion activities
5. **Monitor Impact**: Watch for system issues

## Operational Guidelines

### User Deletion Guidelines

- **Last Resort**: Use only when absolutely necessary
- **Data Export**: Export user data before deletion if needed
- **Related Data**: Consider impact on points, transactions, activities
- **System Access**: Ensure system remains accessible

### Hotel Deletion Guidelines

- **Provider Impact**: Consider impact on provider mappings
- **Search Results**: Update search indexes
- **Cache Invalidation**: Clear hotel-related caches
- **API Responses**: Verify API endpoints handle missing data

### Mapping Deletion Guidelines

- **Provider Coordination**: Coordinate with provider systems
- **Data Consistency**: Maintain mapping consistency
- **Search Impact**: Update search and discovery systems
- **Monitoring**: Monitor for broken integrations

## Recovery and Backup

### Data Recovery Options

- **Database Backups**: Restore from database backups
- **Transaction Logs**: Use transaction log recovery
- **Data Export**: Restore from exported data
- **Manual Recreation**: Manually recreate deleted records

### Backup Strategies

- **Pre-Deletion Backup**: Backup specific records before deletion
- **Full Database Backup**: Regular complete database backups
- **Incremental Backups**: Frequent incremental backups
- **Point-in-Time Recovery**: Enable point-in-time recovery

## Monitoring and Auditing

### Deletion Monitoring

- **Operation Tracking**: Monitor all deletion operations
- **Performance Impact**: Track system performance impact
- **Error Rates**: Monitor deletion error rates
- **Success Metrics**: Track successful deletions

### Audit Requirements

- **Activity Logging**: Log all deletion activities
- **User Tracking**: Track which users perform deletions
- **Timestamp Recording**: Record deletion timestamps
- **Impact Assessment**: Document deletion impact

## Integration Examples

### User Deletion

```python
import requests

# Delete a user (super user only)
response = requests.delete(
    f"{base_url}/v1.0/delete/delete_user/5779356081",
    headers={"Authorization": f"Bearer {super_user_token}"}
)

if response.status_code == 200:
    print("User deleted successfully")
else:
    print(f"Deletion failed: {response.json()['detail']}")
```

### Hotel Deletion

```python
# Delete a hotel and all related data
response = requests.delete(
    f"{base_url}/v1.0/delete/delete_hotel_by_ittid/10000001",
    headers={"Authorization": f"Bearer {super_user_token}"}
)

if response.status_code == 200:
    print("Hotel deleted successfully")
    # Clear related caches
    clear_hotel_caches("10000001")
```

### Mapping Deletion

```python
# Delete a specific provider mapping
response = requests.delete(
    f"{base_url}/v1.0/delete/delete_a_hotel_mapping",
    params={
        "provider_name": "hotelbeds",
        "provider_id": "12345"
    },
    headers={"Authorization": f"Bearer {super_user_token}"}
)
```

## Risk Management

### High-Risk Operations

- **Super User Deletion**: Risk of losing system access
- **Bulk Hotel Deletion**: Risk of data loss
- **Provider Mapping Cleanup**: Risk of broken integrations
- **Database Corruption**: Risk of data integrity issues

### Risk Mitigation

- **Multiple Super Users**: Maintain multiple super user accounts
- **Backup Verification**: Verify backup integrity before deletion
- **Staged Deletion**: Delete in stages with verification
- **Rollback Plans**: Have rollback procedures ready

### Emergency Procedures

- **System Recovery**: Procedures for system recovery
- **Data Restoration**: Steps for data restoration
- **Access Recovery**: Methods to regain system access
- **Communication Plan**: Notify stakeholders of issues

## Future Enhancements

### Potential Improvements

- **Soft Delete**: Implement soft delete with recovery options
- **Batch Operations**: Support for bulk deletion operations
- **Audit Trail**: Enhanced audit logging and tracking
- **Recovery Tools**: Built-in data recovery mechanisms
- **Confirmation Dialogs**: Multi-step confirmation process

### Advanced Features

- **Scheduled Deletion**: Time-based deletion scheduling
- **Conditional Deletion**: Rule-based deletion criteria
- **Impact Analysis**: Pre-deletion impact assessment
- **Automated Cleanup**: Automatic cleanup of orphaned data
- **Deletion Workflows**: Multi-step approval workflows
