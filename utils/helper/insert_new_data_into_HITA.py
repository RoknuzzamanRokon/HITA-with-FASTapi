import os
import json
import requests
from sqlalchemy import create_engine, MetaData, Table, select, text
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed

# Load environment variables
load_dotenv()


# --- CONFIGURATION --- #
def get_database_engine():
    db_uri = (
        f"mysql+pymysql://{os.getenv('DB_USER')}:"
        f"{os.getenv('DB_PASSWORD')}@"
        f"{os.getenv('DB_HOST')}/"
        f"{os.getenv('DB_NAME')}"
    )
    # Configure connection pool to handle concurrent connections better
    return create_engine(
        db_uri,
        echo=False,
        pool_size=20,  # Increase pool size
        max_overflow=30,  # Allow more overflow connections
        pool_timeout=30,  # Timeout for getting connection from pool
        pool_recycle=3600,  # Recycle connections every hour
        pool_pre_ping=True,  # Validate connections before use
    )


# --- AUTHENTICATION & API HELPERS --- #
def get_auth_token():
    url = "http://127.0.0.1:8028/v1.0/auth/token/"
    payload = {"username": "ursamroko", "password": "ursamroko123"}
    r = requests.post(url, data=payload)
    r.raise_for_status()
    return r.json().get("access_token")


def get_headers():
    token = get_auth_token()
    return {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}


# --- EXISTENCE CHECK --- #
def check_if_ittid_exists(ittid, headers):
    url = f"http://127.0.0.1:8028/v1.0/content/get-hotel-with-ittid/{ittid}"
    r = requests.get(url, headers=headers)
    return (r.status_code == 200) and bool(r.json().get("hotel"))


# --- PAYLOAD BUILDER --- #
def parse_contacts(data_str, contact_type):
    if not data_str:
        return []
    return [
        {"contact_type": contact_type, "value": v.strip()}
        for v in data_str.split(",")
        if v.strip()
    ]


def build_payload(row):
    return {
        "ittid": row.ittid,
        "name": row.Name,
        "latitude": str(row.Latitude) if row.Latitude is not None else "",
        "longitude": str(row.Longitude) if row.Longitude is not None else "",
        "address_line1": str(row.AddressLine1) if row.AddressLine1 else "",
        "address_line2": str(row.AddressLine2) if row.AddressLine2 else "",
        "postal_code": str(row.PostalCode) if row.PostalCode else "",
        "rating": str(row.Rating) if row.Rating is not None else "",
        "property_type": str(row.PropertyType) if row.PropertyType else "",
        "primary_photo": str(row.PrimaryPhoto) if row.PrimaryPhoto else "",
        "map_status": "pending",
        "content_update_status": "NewAdd",
        "locations": [
            {
                "city_name": str(row.CityName) if row.CityName else "",
                "state_name": str(row.StateName) if row.StateName else "",
                "state_code": str(row.StateCode) if row.StateCode else "",
                "country_name": str(row.CountryName) if row.CountryName else "",
                "country_code": str(row.CountryCode) if row.CountryCode else "",
                "master_city_name": (
                    str(row.MasterCityName)
                    if row.MasterCityName
                    else str(row.CityName or "")
                ),
                "city_code": str(row.CityCode) if row.CityCode else "",
                "city_location_id": (
                    str(row.CityLocationId) if row.CityLocationId is not None else ""
                ),
            }
        ],
        "provider_mappings": [
            {
                "provider_name": "itt",
                "provider_id": row.ittid,
                "system_type": "a",
                "vervotech_id": str(row.VervotechId) if row.VervotechId else "",
                "giata_code": str(row.GiataCode) if row.GiataCode else "",
            }
        ],
        "contacts": (
            parse_contacts(row.Phones, "phone")
            + parse_contacts(row.Emails, "email")
            + parse_contacts(row.Fax, "fax")
            + parse_contacts(row.Website, "website")
        ),
        "chains": [
            {
                "chain_name": str(row.ChainName) if row.ChainName else "",
                "chain_code": str(row.ChainCode) if row.ChainCode else "",
                "brand_name": str(row.BrandName) if row.BrandName else "",
            }
        ],
    }


# --- WORKER --- #
def process_hotel(row, headers, url, engine):
    try:
        if check_if_ittid_exists(row.ittid, headers):
            print(f"[SKIP] {row.ittid} already exists")
            return "skipped"

        payload = build_payload(row)

        # Add timeout to prevent hanging
        resp = requests.post(url, headers=headers, json=payload, timeout=30)

        if 200 <= resp.status_code < 300:
            print(f"[OK]   {row.ittid} -> {resp.status_code}")
            # Update mapStatus to 'processed' after successful insertion
            update_map_status(row.Id, "processed", engine)
            return "success"
        else:
            print(f"[ERR]  {row.ittid} -> {resp.status_code}")
            print(
                f"[ERR]  Response: {resp.text[:200]}..."
            )  # Limit error message length
            return "error"

    except requests.exceptions.Timeout:
        print(f"[TIMEOUT] {row.ittid} -> Request timed out after 30 seconds")
        return "timeout"
    except requests.exceptions.RequestException as e:
        print(f"[REQUEST_ERROR] {row.ittid} -> {e}")
        return "error"
    except Exception as e:
        print(f"[EXCEPTION] {row.ittid} -> {e}")
        return "error"


def update_map_status(row_id, new_status, engine):
    """Update mapStatus for a specific row after processing"""
    try:
        with engine.begin() as conn:  # Use begin() for automatic transaction management
            conn.execute(
                text(
                    "UPDATE global_hotel_mapping_copy_2 SET mapStatus = :status WHERE Id = :id"
                ),
                {"status": new_status, "id": row_id},
            )
            # No need for explicit commit() with begin()
    except Exception as e:
        print(f"[WARNING] Failed to update mapStatus for row {row_id}: {e}")


# --- MAIN --- #
def upload_hotels():
    engine = get_database_engine()
    headers = get_headers()
    api_url = "http://127.0.0.1:8028/v1.0/hotels/input_hotel_all_details"

    metadata = MetaData()
    hotel_table = Table("global_hotel_mapping_copy_2", metadata, autoload_with=engine)

    batch_size = 10
    offset = 0

    with engine.connect() as conn:
        # Show current status distribution
        print("=== Current mapStatus distribution ===")
        status_result = conn.execute(
            text(
                "SELECT mapStatus, COUNT(*) as count FROM global_hotel_mapping_copy_2 GROUP BY mapStatus"
            )
        )
        for row in status_result:
            print(f"mapStatus '{row.mapStatus}': {row.count} rows")

        # Count only rows with mapStatus = 'new id'
        total_rows = conn.execute(
            text(
                "SELECT COUNT(*) FROM global_hotel_mapping_copy_2 WHERE mapStatus = 'new id'"
            )
        ).scalar()

        print(f"Found {total_rows} rows with mapStatus = 'new id' to process")

        if total_rows == 0:
            print("No rows found with mapStatus = 'new id'. Exiting.")
            return

        processed_count = 0
        error_count = 0

        while offset < total_rows:
            print(f"\n--- Processing batch {(offset // batch_size) + 1} ---")
            print(
                f"Processing rows with mapStatus = 'new id' (Batch {offset + 1} to {offset + batch_size})"
            )

            # Re-query to get current 'new id' rows (in case some were processed by another instance)
            result = conn.execute(
                select(hotel_table)
                .where(hotel_table.c.mapStatus == "new id")
                .offset(offset)
                .limit(batch_size)
            )
            rows = result.fetchall()

            if not rows:
                print("No more rows to process")
                break

            print(f"Found {len(rows)} rows in this batch")

            # Add a small delay between batches to prevent overwhelming the API
            if offset > 0:
                import time

                time.sleep(2)  # 2 second delay between batches

            batch_processed = 0
            batch_errors = 0
            batch_skipped = 0
            batch_timeouts = 0

            with ThreadPoolExecutor(
                max_workers=5
            ) as executor:  # Reduced workers to prevent connection issues
                futures = [
                    executor.submit(process_hotel, row, headers, api_url, engine)
                    for row in rows
                ]
                for future in as_completed(futures):
                    try:
                        result = future.result(
                            timeout=60
                        )  # 60 second timeout per future
                        if result == "success":
                            batch_processed += 1
                        elif result == "skipped":
                            batch_skipped += 1
                        elif result == "timeout":
                            batch_timeouts += 1
                        else:  # error
                            batch_errors += 1
                    except Exception as e:
                        batch_errors += 1
                        print(f"[FUTURE ERROR] {e}")

            processed_count += batch_processed
            error_count += batch_errors

            print(
                f"Batch completed: {batch_processed} processed, {batch_skipped} skipped, {batch_errors} errors, {batch_timeouts} timeouts"
            )
            print(
                f"Total progress: {processed_count}/{total_rows} processed, {error_count} total errors"
            )

            offset += batch_size

        print(f"\n=== FINAL SUMMARY ===")
        print(f"Total rows processed: {processed_count}")
        print(f"Total errors: {error_count}")
        print(
            f"Success rate: {(processed_count / (processed_count + error_count) * 100):.1f}%"
            if (processed_count + error_count) > 0
            else "N/A"
        )


if __name__ == "__main__":
    upload_hotels()
