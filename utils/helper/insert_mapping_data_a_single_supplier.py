import os
import json
import requests
import signal
import sys
from dotenv import load_dotenv
from sqlalchemy import create_engine, MetaData, Table, select, desc, update
from sqlalchemy.orm import Session
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import threading
from contextlib import contextmanager

# --- CONFIGURATION & AUTH --- #

load_dotenv()

API_BASE = "http://127.0.0.1:8028/v1.0"
ENDPOINT = f"{API_BASE}/hotels/add_provider_all_details_with_ittid/"

# Global engine instance
_engine = None


def get_database_engine():
    global _engine
    if _engine is None:
        db_uri = (
            f"mysql+pymysql://{os.getenv('DB_USER')}:"
            f"{os.getenv('DB_PASSWORD')}@"
            f"{os.getenv('DB_HOST')}/"
            f"{os.getenv('DB_NAME')}"
        )
        _engine = create_engine(
            db_uri,
            pool_pre_ping=True,
            pool_size=3,  # Reduced pool size
            max_overflow=5,  # Reduced overflow
            pool_recycle=1800,  # 30 minutes
            pool_timeout=20,  # Reduced timeout
            echo=False,
        )
    return _engine


@contextmanager
def get_db_session():
    """Context manager for database sessions with proper cleanup"""
    engine = get_database_engine()
    session = Session(engine)
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_pool_status():
    """Get current connection pool status for monitoring"""
    try:
        engine = get_database_engine()
        pool = engine.pool
        status = {
            "pool_size": pool.size(),
            "checked_in": pool.checkedin(),
            "checked_out": pool.checkedout(),
            "overflow": pool.overflow(),
        }

        # Try to get invalid count if available (not all pool types have this)
        try:
            status["invalid"] = pool.invalid()
        except AttributeError:
            status["invalid"] = "N/A"

        return status
    except Exception as e:
        return {"error": f"Could not get pool status: {e}"}


def get_auth_token():
    url = f"{API_BASE}/auth/token/"
    payload = {"username": os.getenv("API_USER"), "password": os.getenv("API_PASS")}
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    resp = requests.post(url, headers=headers, data=payload)
    resp.raise_for_status()
    return resp.json()["access_token"]


def get_headers():
    token = get_auth_token()
    return {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}


# --- MAPPING DEFINITIONS --- #

PROVIDERS = [
    "hotelbeds",
    "ean",
    "agoda",
    "mgholiday",
    "restel",
    "stuba",
    "hyperguestdirect",
    "tbohotel",
    "goglobal",
    "ratehawkhotel",
    "adivahahotel",
    "grnconnect",
    "juniperhotel",
    "mikihotel",
    "paximumhotel",
    "adonishotel",
    "w2mhotel",
    "oryxhotel",
    "dotw",
    "hotelston",
    "letsflyhotel",
    "illusionshotel",
    "innstanttravel",
    "roomerang",
    "kiwihotel",
    "rnrhotel",
]

SUFFIX_MAP = {"": "g", "_a": "b", "_b": "c", "_c": "d", "_d": "e", "_e": "f"}


# --- CORE LOGIC --- #


def build_payload(row, provider, suffix):
    col_name = provider + suffix
    provider_id = getattr(row, col_name, None)
    if provider_id is None:
        return None

    vervo = getattr(row, "VervotechId", None)
    giata = getattr(row, "GiataCode", None)

    return {
        "ittid": row.ittid,
        "provider_name": provider,
        "provider_id": provider_id,
        "system_type": SUFFIX_MAP[suffix],
        "vervotech_id": vervo,
        "giata_code": giata,
    }


# def fetch_all_mappings(engine, offset=0, limit=10000):
#     """
#     Fetch a batch of rows from the global_hotel_mapping_copy table.
#     Ensures proper session cleanup and engine disposal to prevent
#     MySQL connection exhaustion during long-running loops.
#     """
#     meta = MetaData()
#     table = Table("global_hotel_mapping_copy", meta, autoload_with=engine)

#     try:
#         with Session(engine) as sess:
#             stmt = select(table).offset(offset).limit(limit)
#             results = sess.execute(stmt).all()
#             return results
#     finally:
#         # ✅ Ensure connection pool doesn't grow endlessly
#         engine.dispose()


from sqlalchemy import desc


def fetch_all_mappings(offset=0, limit=200):
    engine = get_database_engine()
    meta = MetaData()
    table = Table("global_hotel_mapping_copy_2", meta, autoload_with=engine)

    with get_db_session() as session:
        stmt = (
            select(table)
            .where(table.c.mapStatus == "rnrU1")
            .order_by(desc(table.c.ittid))
            .offset(offset)
            .limit(limit)
        )
        results = session.execute(stmt).all()
        return results


seen_lock = threading.Lock()
seen = set()

# Counters for tracking results
success_count = 0
not_found_count = 0
error_count = 0
counter_lock = threading.Lock()

# Global flag for graceful shutdown
shutdown_requested = False


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    global shutdown_requested
    print(f"\n⚠️ Received signal {signum}. Initiating graceful shutdown...")
    print("📊 Current progress will be saved. Please wait...")
    shutdown_requested = True


# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)  # Ctrl+C
signal.signal(signal.SIGTERM, signal_handler)  # Termination signal


def update_map_status(ittid, status="rnrU1"):
    """Update mapStatus for the given ittid"""
    engine = get_database_engine()
    meta = MetaData()
    table = Table("global_hotel_mapping_copy_2", meta, autoload_with=engine)

    try:
        with get_db_session() as session:
            stmt = update(table).where(table.c.ittid == ittid).values(mapStatus=status)
            session.execute(stmt)
    except Exception as e:
        print(f"❌ Error updating mapStatus for ittid {ittid} to {status}: {e}")


def post_mapping(session, headers, payload):
    """POST and update mapStatus on success"""
    global not_found_count
    try:
        resp = session.post(ENDPOINT, headers=headers, data=json.dumps(payload))
        resp.raise_for_status()
        update_map_status(payload["ittid"], "rnrU1")
        return payload

    except requests.exceptions.HTTPError as e:
        if e.response is not None and e.response.status_code == 401:
            print("⚠️ Token expired. Refreshing access token...")
            new_headers = get_headers()
            resp = session.post(ENDPOINT, headers=new_headers, data=json.dumps(payload))
            resp.raise_for_status()
            update_map_status(payload["ittid"], "rnrU1")
            return payload
        elif e.response is not None and e.response.status_code == 404:
            # Handle 404 - Hotel not found
            print(
                f"⚠️ Hotel with ittid '{payload['ittid']}' not found (404). Marking as 'new id'"
            )
            update_map_status(payload["ittid"], "new id")
            with counter_lock:
                not_found_count += 1
            return None  # Return None to indicate this was handled but not successful
        else:
            raise e


def save_progress(offset, success_count, not_found_count, error_count):
    """Save current progress to a file"""
    try:
        progress_data = {
            "offset": offset,
            "success_count": success_count,
            "not_found_count": not_found_count,
            "error_count": error_count,
            "timestamp": time.time(),
        }
        with open("mapping_progress.json", "w") as f:
            json.dump(progress_data, f)
        print(f"💾 Progress saved at offset {offset}")
    except Exception as e:
        print(f"⚠️ Could not save progress: {e}")


def load_progress():
    """Load progress from file if it exists"""
    try:
        with open("mapping_progress.json", "r") as f:
            progress_data = json.load(f)
        return (
            progress_data.get("offset", 0),
            progress_data.get("success_count", 0),
            progress_data.get("not_found_count", 0),
            progress_data.get("error_count", 0),
        )
    except FileNotFoundError:
        return 0, 0, 0, 0
    except Exception as e:
        print(f"⚠️ Could not load progress: {e}")
        return 0, 0, 0, 0


def main():
    global success_count, not_found_count, error_count, shutdown_requested

    print("🚀 Starting mapping data insertion process...")

    # Try to load previous progress
    offset, loaded_success, loaded_not_found, loaded_error = load_progress()
    success_count = loaded_success
    not_found_count = loaded_not_found
    error_count = loaded_error

    if offset > 0:
        print(f"📂 Resuming from previous session at offset {offset}")
        print(
            f"📊 Previous progress: Success={success_count}, Not Found={not_found_count}, Errors={error_count}"
        )
    else:
        print(f"📊 Starting fresh: Success=0, Not Found=0, Errors=0")

    batch_size = 500  # Reduced batch size
    max_retries = 3
    retry_count = 0

    while retry_count < max_retries:
        try:
            headers = get_headers()

            with requests.Session() as sess, ThreadPoolExecutor(
                max_workers=3
            ) as executor:  # Reduced workers
                while True:
                    # Check for shutdown request
                    if shutdown_requested:
                        print("🛑 Shutdown requested. Stopping gracefully...")
                        break

                    try:
                        rows = fetch_all_mappings(offset=offset, limit=batch_size)
                        if not rows:
                            print("✅ No more rows to process. Completed successfully!")
                            break

                        futures = []

                        for row in rows:
                            for provider in PROVIDERS:
                                for suffix in SUFFIX_MAP:
                                    payload = build_payload(row, provider, suffix)
                                    if not payload:
                                        continue

                                    key = (
                                        payload["provider_name"],
                                        payload["provider_id"],
                                    )

                                    with seen_lock:
                                        if key in seen:
                                            continue
                                        seen.add(key)

                                    futures.append(
                                        executor.submit(
                                            post_mapping, sess, headers, payload
                                        )
                                    )

                        # Process futures in smaller batches to avoid overwhelming the system
                        batch_futures = []
                        for i, fut in enumerate(futures):
                            batch_futures.append(fut)
                            if (
                                len(batch_futures) >= 50 or i == len(futures) - 1
                            ):  # Process in batches of 50
                                for completed_fut in as_completed(batch_futures):
                                    try:
                                        payload = completed_fut.result()
                                        if payload is not None:  # Successful insertion
                                            with counter_lock:
                                                success_count += 1
                                            print(
                                                f"✅ Inserted and Updated: itt id={payload['ittid']} | "
                                                f"provider={payload['provider_name']} | "
                                                f"id={payload['provider_id']} | "
                                                f"type={payload['system_type']}"
                                            )
                                        # If payload is None, it means 404 was handled and logged already
                                    except Exception as e:
                                        with counter_lock:
                                            error_count += 1
                                        print("❌ Error:", e)
                                batch_futures = []
                                time.sleep(0.1)  # Small delay between batches

                        offset += batch_size

                        # Monitor connection pool and show progress every 10 batches
                        if offset % (batch_size * 10) == 0:
                            try:
                                pool_status = get_pool_status()
                                print(f"🔍 Pool Status: {pool_status}")
                            except Exception as e:
                                print(f"⚠️ Could not get pool status: {e}")

                            print(
                                f"📊 Progress: Success={success_count}, Not Found={not_found_count}, Errors={error_count}"
                            )

                            # Save progress periodically
                            save_progress(
                                offset, success_count, not_found_count, error_count
                            )

                        time.sleep(1.0)  # Longer delay between main batches

                    except KeyboardInterrupt:
                        print("\n⚠️ Process interrupted by user (Ctrl+C)")
                        shutdown_requested = True
                        break
                    except Exception as batch_error:
                        print(f"❌ Batch processing error: {batch_error}")
                        print("⏳ Waiting 5 seconds before continuing...")
                        time.sleep(5)
                        continue

            # If we reach here, processing completed successfully
            break

        except Exception as main_error:
            retry_count += 1
            print(
                f"❌ Main process error (attempt {retry_count}/{max_retries}): {main_error}"
            )

            if retry_count < max_retries:
                wait_time = retry_count * 10  # Exponential backoff
                print(f"⏳ Waiting {wait_time} seconds before retry...")
                time.sleep(wait_time)
            else:
                print("❌ Max retries reached. Stopping process.")
                break

    # Final cleanup and summary
    try:
        if _engine:
            _engine.dispose()
            print("🔄 Database connections cleaned up")
    except Exception as cleanup_error:
        print(f"⚠️ Cleanup error: {cleanup_error}")

    # Save final progress
    save_progress(offset, success_count, not_found_count, error_count)

    # Final summary
    print(f"\n📈 Final Summary:")
    print(f"   ✅ Successful insertions: {success_count}")
    print(f"   ⚠️ Hotels not found (marked as 'new id'): {not_found_count}")
    print(f"   ❌ Other errors: {error_count}")
    print(f"   📊 Total processed: {success_count + not_found_count + error_count}")
    print(f"   🏁 Process completed at offset: {offset}")

    if shutdown_requested:
        print(f"   ⚠️ Process was interrupted but progress has been saved")
        print(f"   🔄 Run the script again to resume from offset {offset}")
    else:
        # Clean up progress file if completed successfully
        try:
            os.remove("mapping_progress.json")
            print(f"   🧹 Progress file cleaned up")
        except:
            pass


if __name__ == "__main__":
    main()
