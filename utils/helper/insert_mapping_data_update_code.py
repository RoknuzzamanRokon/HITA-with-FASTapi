import os
import json
import time
import signal
import threading
import requests
from dotenv import load_dotenv
from sqlalchemy import create_engine, MetaData, Table, select, update, desc
from sqlalchemy.orm import Session
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from requests.exceptions import ReadTimeout, ConnectionError, HTTPError

# =====================================================
# CONFIG
# =====================================================

load_dotenv()

API_BASE = "http://127.0.0.1:8028/v1.0"
ENDPOINT = f"{API_BASE}/hotels/add_provider_all_details_with_ittid/"
TABLE_NAME = "global_hotel_mapping_copy_2"

BATCH_SIZE = 200
MAX_WORKERS = 3
MAX_RETRIES = 3

# =====================================================
# DATABASE
# =====================================================

_engine = None


def get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(
            f"mysql+pymysql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@"
            f"{os.getenv('DB_HOST')}/{os.getenv('DB_NAME')}",
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=5,
            pool_recycle=1800,
        )
    return _engine


@contextmanager
def db_session():
    session = Session(get_engine())
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


metadata = MetaData()
ghm = Table(TABLE_NAME, metadata, autoload_with=get_engine())

# =====================================================
# AUTH (CACHED)
# =====================================================

_HEADERS = None
_HEADERS_LOCK = threading.Lock()


def get_headers():
    global _HEADERS
    with _HEADERS_LOCK:
        if _HEADERS:
            return _HEADERS

        resp = requests.post(
            f"{API_BASE}/auth/token/",
            data={
                "username": os.getenv("API_USER"),
                "password": os.getenv("API_PASS"),
            },
            timeout=(5, 15),
        )
        resp.raise_for_status()

        _HEADERS = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {resp.json()['access_token']}",
        }
        return _HEADERS


# =====================================================
# PROVIDERS
# =====================================================

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
    "rakuten",
]

SUFFIX_MAP = {"": "g", "_a": "b", "_b": "c", "_c": "d", "_d": "e", "_e": "f"}

# =====================================================
# GLOBAL STATE
# =====================================================

success_count = 0
not_found_count = 0
error_count = 0
counter_lock = threading.Lock()
shutdown_requested = False

# =====================================================
# SIGNAL HANDLING
# =====================================================


def signal_handler(sig, frame):
    global shutdown_requested
    print("\n⚠️ Graceful shutdown requested...")
    shutdown_requested = True


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# =====================================================
# CORE HELPERS
# =====================================================


def fetch_rows(offset, limit):
    with db_session() as session:
        stmt = (
            select(ghm)
            .where(ghm.c.mapStatus.notin_(["upd1", "new id"]))
            .order_by(desc(ghm.c.ittid))
            .offset(offset)
            .limit(limit)
        )
        return session.execute(stmt).all()


def update_map_status(ittid, status):
    with db_session() as session:
        session.execute(
            update(ghm).where(ghm.c.ittid == ittid).values(mapStatus=status)
        )


def build_payloads(row):
    payloads = []
    for provider in PROVIDERS:
        for suffix, sys_type in SUFFIX_MAP.items():
            pid = getattr(row, provider + suffix, None)
            if not pid:
                continue

            payloads.append(
                {
                    "ittid": row.ittid,
                    "provider_name": provider,
                    "provider_id": pid,
                    "system_type": sys_type,
                    "vervotech_id": row.VervotechId,
                    "giata_code": row.GiataCode,
                }
            )
    return payloads


def post_payload(session, headers, payload):
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = session.post(
                ENDPOINT,
                headers=headers,
                json=payload,
                timeout=(5, 30),
            )

            if resp.status_code == 401:
                headers = get_headers()
                continue

            if resp.status_code == 404:
                return "not_found"

            resp.raise_for_status()
            return "success"

        except (ReadTimeout, ConnectionError):
            print(
                f"⏳ Timeout (attempt {attempt}/{MAX_RETRIES}) | "
                f"ittid={payload['ittid']} | {payload['provider_name']}"
            )
            time.sleep(attempt * 2)

        except HTTPError as e:
            print(f"❌ HTTP {e.response.status_code}: {e}")
            return "error"

        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            return "error"

    return "error"


def process_row(row):
    headers = get_headers()
    success = False
    not_found = False

    with requests.Session() as http:
        for payload in build_payloads(row):
            result = post_payload(http, headers, payload)
            if result == "success":
                success = True
            elif result == "not_found":
                not_found = True

    if success:
        update_map_status(row.ittid, "upd1")
        return "success"
    if not_found:
        update_map_status(row.ittid, "new id")
        return "not_found"
    return "error"


# =====================================================
# PROGRESS SAVE / LOAD
# =====================================================


def save_progress(offset):
    with open("mapping_progress.json", "w") as f:
        json.dump(
            {
                "offset": offset,
                "success": success_count,
                "not_found": not_found_count,
                "error": error_count,
            },
            f,
        )


def load_progress():
    try:
        with open("mapping_progress.json") as f:
            d = json.load(f)
            return d["offset"], d["success"], d["not_found"], d["error"]
    except:
        return 0, 0, 0, 0


# =====================================================
# MAIN
# =====================================================


def main():
    global success_count, not_found_count, error_count

    offset, success_count, not_found_count, error_count = load_progress()
    print(f"🚀 Starting from offset {offset}")

    while not shutdown_requested:
        rows = fetch_rows(offset, BATCH_SIZE)
        if not rows:
            print("✅ All records processed")
            break

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = [executor.submit(process_row, r) for r in rows]

            for fut in as_completed(futures):
                result = fut.result()
                with counter_lock:
                    if result == "success":
                        success_count += 1
                    elif result == "not_found":
                        not_found_count += 1
                    else:
                        error_count += 1

        offset += BATCH_SIZE
        save_progress(offset)

        print(
            f"📊 Offset={offset} | "
            f"Success={success_count} | "
            f"NotFound={not_found_count} | "
            f"Errors={error_count}"
        )

    save_progress(offset)

    print("\n🏁 FINAL SUMMARY")
    print(f"✅ Success: {success_count}")
    print(f"⚠️ Not Found: {not_found_count}")
    print(f"❌ Errors: {error_count}")


if __name__ == "__main__":
    main()
