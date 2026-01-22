import os
import json
import requests
from dotenv import load_dotenv
from sqlalchemy import create_engine, MetaData, Table, select, update
from sqlalchemy.orm import Session
from contextlib import contextmanager

# =====================================================
# CONFIG
# =====================================================

load_dotenv()

API_BASE = "http://127.0.0.1:8028/v1.0"
ENDPOINT = f"{API_BASE}/hotels/add_provider_all_details_with_ittid/"
TABLE_NAME = "global_hotel_mapping_copy_2"


# =====================================================
# DATABASE (SINGLE ENGINE & TABLE)
# =====================================================

engine = create_engine(
    f"mysql+pymysql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@"
    f"{os.getenv('DB_HOST')}/{os.getenv('DB_NAME')}",
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=0,
    pool_recycle=1800,
)

metadata = MetaData()
ghm = Table(TABLE_NAME, metadata, autoload_with=engine)

@contextmanager
def db_session():
    session = Session(engine)
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

# =====================================================
# AUTH (CACHED)
# =====================================================

_HEADERS = None

def get_headers():
    global _HEADERS
    if _HEADERS:
        return _HEADERS

    resp = requests.post(
        f"{API_BASE}/auth/token/",
        data={
            "username": os.getenv("API_USER"),
            "password": os.getenv("API_PASS"),
        },
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
    "hotelbeds","ean","agoda","mgholiday","restel","stuba",
    "hyperguestdirect","tbohotel","goglobal","ratehawkhotel",
    "adivahahotel","grnconnect","juniperhotel","mikihotel",
    "paximumhotel","adonishotel","w2mhotel","oryxhotel",
    "dotw","hotelston","letsflyhotel","illusionshotel",
    "innstanttravel","roomerang","kiwihotel","rnrhotel"
]

SUFFIX_MAP = {"": "g", "_a": "b", "_b": "c", "_c": "d", "_d": "e", "_e": "f"}

# =====================================================
# CORE
# =====================================================

def fetch_single_row(session, ittid):
    return session.execute(
        select(ghm).where(ghm.c.ittid == ittid)
    ).first()

def update_map_status(session, ittid, status):
    session.execute(
        update(ghm).where(ghm.c.ittid == ittid).values(mapStatus=status)
    )

def build_payload(row, provider, suffix):
    provider_id = getattr(row, provider + suffix, None)
    if not provider_id:
        return None

    return {
        "ittid": row.ittid,
        "provider_name": provider,
        "provider_id": provider_id,
        "system_type": SUFFIX_MAP[suffix],
        "vervotech_id": row.VervotechId,
        "giata_code": row.GiataCode,
    }

def post_mapping(headers, payload):
    resp = requests.post(
        ENDPOINT,
        headers=headers,
        json=payload,
        timeout=15,
    )

    if resp.status_code == 401:
        headers = get_headers()
        resp = requests.post(ENDPOINT, headers=headers, json=payload)

    if resp.status_code == 404:
        return "not_found"

    resp.raise_for_status()
    return "success"

# =====================================================
# MAIN
# =====================================================

def main():
    print(f"\n🚀 Processing ITTID: {TARGET_ITTID}")

    headers = get_headers()
    success = not_found = errors = 0

    with db_session() as session:
        row = fetch_single_row(session, TARGET_ITTID)
        if not row:
            print("❌ ITTID not found")
            return

        for provider in PROVIDERS:
            for suffix in SUFFIX_MAP:
                payload = build_payload(row, provider, suffix)
                if not payload:
                    continue

                try:
                    result = post_mapping(headers, payload)
                    if result == "success":
                        success += 1
                    else:
                        not_found += 1
                except Exception:
                    errors += 1

        if success:
            update_map_status(session, TARGET_ITTID, "upd1")
        elif not_found:
            update_map_status(session, TARGET_ITTID, "new id")

    print("\n📊 SUMMARY")
    print(f"✅ Success: {success}")
    print(f"⚠️ Not Found: {not_found}")
    print(f"❌ Errors: {errors}")
    print("🏁 Done\n")

# =====================================================
# ENTRY
# =====================================================
TARGET_ITTID = "11688458"

if __name__ == "__main__":
    main()
