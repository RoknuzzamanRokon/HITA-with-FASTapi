# "All" Suppliers Feature - Search Hotel Endpoint

## Endpoint: `POST /v1.0/locations/search-hotel-with-location`

---

## 🎯 New Feature: Search All Suppliers

You can now use `"All"` or `"all"` in the supplier list to search across all available suppliers instead of specifying each one individually.

---

## 📋 Usage Examples

### Example 1: Specific Supplier (Original)

```json
{
  "lat": "25.2048493",
  "lon": "55.2707828",
  "radius": "10",
  "supplier": ["agoda"],
  "country_code": "AI"
}
```

**Result:** Hotels from Agoda only

---

### Example 2: All Suppliers (NEW)

```json
{
  "lat": "25.2048493",
  "lon": "55.2707828",
  "radius": "10",
  "supplier": ["All"],
  "country_code": "AI"
}
```

**Result:** Hotels from all available suppliers

---

### Example 3: Case Insensitive

```json
{
  "supplier": ["all"]     // lowercase
  "supplier": ["All"]     // capitalized
  "supplier": ["ALL"]     // uppercase
}
```

**All work the same!** Case-insensitive.

---

### Example 4: Mixed (All + Specific)

```json
{
  "supplier": ["All", "ean"]
}
```

**Result:** Same as `["All"]` - searches all suppliers (specific ones are ignored when "All" is present)

---

## 🔓 Public Access

This endpoint is **public** (no authentication required):

- ✅ Searches **ALL suppliers in the system**
- ✅ Gets results from all available suppliers
- ✅ No permission restrictions

**Example:**

- System has: agoda, booking, expedia, ean, dotw
- Request: `["All"]`
- Result: Hotels from all 5 suppliers

---

## 📊 Response Format

Same as before, but with hotels from multiple suppliers:

```json
{
  "total_hotels": 150,
  "hotels": [
    {
      "a": 18.17,
      "b": -63.1423,
      "name": "Sheriva Luxury Villas and Suites",
      "addr": "Maundays Bay Rd",
      "type": "Villa",
      "photo": "https://...",
      "star": 4.0,
      "vervotech": "15392205",
      "giata": "291678",
      "agoda": ["55395643"]
    },
    {
      "name": "Another Hotel",
      "booking": ["hotel_123"],
      "ean": ["12345"]
    }
  ]
}
```

**Note:** Each hotel includes supplier-specific IDs (e.g., `"agoda": [...]`, `"booking": [...]`)

---

## 🔍 How It Works

### 1. Check for "All" in Supplier List

```python
use_all_suppliers = any(s.lower() == "all" for s in request.supplier)
```

### 2. Get All Suppliers

```python
# Get all suppliers from supplier_summary table
all_system_suppliers = db.query(SupplierSummary.provider_name).all()
suppliers_to_search = [supplier[0] for supplier in all_system_suppliers]
```

### 3. Search All Suppliers

```python
for supplier in suppliers_to_search:
    # Load JSON file for each supplier
    # Filter hotels within radius
    # Add to results
```

---

## 💡 Benefits

### 1. Convenience

- No need to list all suppliers manually
- One request instead of multiple

### 2. Comprehensive Results

- Get hotels from all available sources
- Better coverage and options

### 3. Future-Proof

- New suppliers automatically included
- No code changes needed when adding suppliers

---

## 🧪 Testing

### Manual Testing

**1. Test with specific supplier:**

```bash
POST /v1.0/locations/search-hotel-with-location
{
  "lat": "25.2048493",
  "lon": "55.2707828",
  "radius": "10",
  "supplier": ["agoda"],
  "country_code": "AI"
}
```

**2. Test with "All":**

```bash
POST /v1.0/locations/search-hotel-with-location
{
  "lat": "25.2048493",
  "lon": "55.2707828",
  "radius": "10",
  "supplier": ["All"],
  "country_code": "AI"
}
```

**3. Test case insensitivity:**

```bash
# Try: ["all"], ["All"], ["ALL"]
# All should work the same
```

---

## 📝 Implementation Details

### Changes Made:

1. **Added Database Dependency**

   - Added `db: Session = Depends(get_db)` parameter
   - Enables querying supplier_summary table

2. **Added "All" Detection**

   - Checks if "All" (case-insensitive) is in supplier list
   - Sets flag: `use_all_suppliers`

3. **Dynamic Supplier Loading**

   - Loads all suppliers from `supplier_summary` table when "All" is used
   - Uses requested suppliers otherwise

4. **Updated Documentation**

   - Added examples for "All" usage
   - Documented case-insensitivity note
   - Added mixed request behavior

5. **Logging**
   - Logs when "All" is used
   - Shows how many suppliers are being searched

---

## ⚠️ Important Notes

### 1. Performance

- Searching all suppliers may take longer
- More files to read and process
- Consider caching for production

### 2. File Availability

- Only searches suppliers with available JSON files
- Missing files are silently skipped
- No error if some suppliers have no data

### 3. Mixed Requests

- If "All" is present, specific suppliers are ignored
- `["All", "ean"]` = `["All"]`
- This is intentional for simplicity

### 4. Empty Results

- If no suppliers have data, returns empty result
- No error thrown, just `{"total_hotels": 0, "hotels": []}`

---

## 🎯 Use Cases

### 1. Public Search Widget

Search all suppliers for comprehensive results:

```javascript
const searchAllSuppliers = async () => {
  const response = await fetch("/v1.0/locations/search-hotel-with-location", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      lat: "25.2048493",
      lon: "55.2707828",
      radius: "10",
      supplier: ["All"],
      country_code: "AI",
    }),
  });
  const data = await response.json();
  console.log(`Found ${data.total_hotels} hotels from all suppliers`);
};
```

### 2. Comparison Tool

Compare prices across all suppliers:

```python
# Get hotels from all suppliers
# Group by hotel name/location
# Compare availability
# Show all options
```

---

## ✅ Summary

**Feature:** Search all suppliers with `["All"]`

**Benefits:**

- ✅ Convenient - no need to list all suppliers
- ✅ Public access - no authentication required
- ✅ Case-insensitive - "All", "all", "ALL" all work
- ✅ Future-proof - new suppliers automatically included

**Access:**

- Public endpoint - searches all system suppliers

**Usage:**

```json
{ "supplier": ["All"] } // or ["all"] or ["ALL"]
```

---

## 🔄 Difference from `/search-hotel-with-location-with-rate`

| Feature              | `/search-hotel-with-location` | `/search-hotel-with-location-with-rate` |
| -------------------- | ----------------------------- | --------------------------------------- |
| Authentication       | ❌ Not required               | ✅ Required (JWT token)                 |
| IP Whitelist         | ❌ Not required               | ✅ Required                             |
| Supplier Permissions | ❌ Not checked                | ✅ Checked for general users            |
| Rate Information     | ❌ Not included               | ✅ Included (room rates, prices)        |
| "All" Suppliers      | ✅ All system suppliers       | ✅ All permitted suppliers (role-based) |
| Data Source          | `countryJson/`                | `countryJsonWithRate/`                  |

---

**Updated:** November 15, 2025  
**Status:** ✅ Complete and Ready to Use
