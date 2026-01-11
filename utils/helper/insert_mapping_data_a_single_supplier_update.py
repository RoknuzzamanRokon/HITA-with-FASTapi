import os
import time
import signal
import threading
import requests

from dotenv import load_dotenv
from sqlalchemy import create_engine, MetaData, Table, select, update, desc, or_
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

SUPPLIER = "rakuten"
MAP_STATUS_DONE = "raku1"

BATCH_SIZE = 200
MAX_WORKERS = 3
MAX_RETRIES = 3

# =====================================================
# SUPPLIER COLUMN & SUFFIX MAP
# =====================================================

PROVIDER_MAPPINGS = {
    "rakuten": [
        "rakuten",
        "rakuten_a",
        "rakuten_b",
        "rakuten_c",
        "rakuten_d",
        "rakuten_e",
    ]
}

SUFFIX_MAP = {
    "": "g",
    "_a": "b",
    "_b": "c",
    "_c": "d",
    "_d": "e",
    "_e": "f",
}

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
# AUTH (TOKEN CACHE)
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
# SIGNAL HANDLING
# =====================================================

shutdown_requested = False


def signal_handler(sig, frame):
    global shutdown_requested
    print("\n⚠️ Graceful shutdown requested...")
    shutdown_requested = True


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# =====================================================
# CORE LOGIC
# =====================================================


def fetch_rows(offset, limit):
    """Fetch rows where ANY rakuten column has value"""
    cols = PROVIDER_MAPPINGS[SUPPLIER]
    conditions = [ghm.c[col].is_not(None) for col in cols]

    with db_session() as session:
        stmt = (
            select(ghm)
            .where(or_(*conditions), ghm.c.mapStatus != MAP_STATUS_DONE)
            .order_by(desc(ghm.c.ittid))
            .offset(offset)
            .limit(limit)
        )
        return session.execute(stmt).all()


def update_map_status(ittid):
    with db_session() as session:
        session.execute(
            update(ghm).where(ghm.c.ittid == ittid).values(mapStatus=MAP_STATUS_DONE)
        )


def build_payloads(row):
    payloads = []

    for col in PROVIDER_MAPPINGS[SUPPLIER]:
        provider_id = getattr(row, col, None)
        if not provider_id:
            continue

        suffix = col.replace(SUPPLIER, "")
        system_type = SUFFIX_MAP.get(suffix)

        if not system_type:
            continue

        payloads.append(
            {
                "ittid": row.ittid,
                "provider_name": SUPPLIER,
                "provider_id": provider_id,
                "system_type": system_type,
                "vervotech_id": row.VervotechId,
                "giata_code": row.GiataCode,
            }
        )

    return payloads


def post_payload(http, headers, payload):
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = http.post(
                ENDPOINT,
                headers=headers,
                json=payload,
                timeout=(5, 30),
            )

            if resp.status_code == 401:
                headers = get_headers()
                continue

            resp.raise_for_status()
            return True

        except (ReadTimeout, ConnectionError):
            print(
                f"⏳ Retry {attempt}/{MAX_RETRIES} | "
                f"ittid={payload['ittid']} | {payload['provider_id']}"
            )
            time.sleep(attempt * 2)

        except HTTPError as e:
            print(f"❌ HTTP {e.response.status_code} | ittid={payload['ittid']}")
            return False

        except Exception as e:
            print(f"❌ Error | ittid={payload['ittid']} | {e}")
            return False

    return False


def process_row(row):
    headers = get_headers()
    payloads = build_payloads(row)

    if not payloads:
        return "skip"

    with requests.Session() as http:
        for payload in payloads:
            if not post_payload(http, headers, payload):
                return "error"

    update_map_status(row.ittid)
    return "success"


# =====================================================
# MAIN
# =====================================================


def main():
    offset = 0
    success = 0
    error = 0

    print("🚀 rakuten processing started")

    while not shutdown_requested:
        rows = fetch_rows(offset, BATCH_SIZE)
        if not rows:
            break

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = [executor.submit(process_row, r) for r in rows]

            for fut in as_completed(futures):
                if fut.result() == "success":
                    success += 1
                else:
                    error += 1

        offset += BATCH_SIZE

        print(f"📊 Offset={offset} | " f"Success={success} | " f"Errors={error}")

    print("\n🏁 FINAL SUMMARY")
    print(f"✅ Success: {success}")
    print(f"❌ Errors: {error}")


if __name__ == "__main__":
    main()
