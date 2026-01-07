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
TARGET_ITTID = 11688457

# =====================================================
# DATABASE
# =====================================================

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
            pool_size=3,
            max_overflow=5,
            pool_recycle=1800,
            echo=False,
        )
    return _engine


@contextmanager
def get_db_session():
    session = Session(get_database_engine())
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# =====================================================
# AUTH
# =====================================================


def get_headers():
    resp = requests.post(
        f"{API_BASE}/auth/token/",
        data={"username": os.getenv("API_USER"), "password": os.getenv("API_PASS")},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    resp.raise_for_status()
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {resp.json()['access_token']}",
    }


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
    "rnrhotel"
]

SUFFIX_MAP = {"": "g", "_a": "b", "_b": "c", "_c": "d", "_d": "e", "_e": "f"}

# =====================================================
# CORE
# =====================================================


def fetch_single_row(ittid):
    engine = get_database_engine()
    meta = MetaData()
    table = Table(TABLE_NAME, meta, autoload_with=engine)

    with get_db_session() as session:
        return session.execute(select(table).where(table.c.ittid == ittid)).first()


def update_map_status(ittid, status):
    engine = get_database_engine()
    meta = MetaData()
    table = Table(TABLE_NAME, meta, autoload_with=engine)

    with get_db_session() as session:
        session.execute(
            update(table).where(table.c.ittid == ittid).values(mapStatus=status)
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
        "vervotech_id": getattr(row, "VervotechId", None),
        "giata_code": getattr(row, "GiataCode", None),
    }


def post_mapping(headers, payload):
    try:
        resp = requests.post(
            ENDPOINT, headers=headers, data=json.dumps(payload), timeout=20
        )
        resp.raise_for_status()
        return "success"

    except requests.exceptions.HTTPError as e:
        if e.response and e.response.status_code == 401:
            headers = get_headers()
            resp = requests.post(
                ENDPOINT, headers=headers, data=json.dumps(payload), timeout=20
            )
            resp.raise_for_status()
            return "success"

        if e.response and e.response.status_code == 404:
            return "not_found"

        raise


# =====================================================
# MAIN
# =====================================================


def main():
    print(f"\n🚀 Processing ITTID: {TARGET_ITTID}")

    row = fetch_single_row(TARGET_ITTID)
    if not row:
        print("❌ ITTID not found")
        return

    headers = get_headers()
    success = 0
    not_found = 0
    errors = 0

    for provider in PROVIDERS:
        for suffix in SUFFIX_MAP:
            payload = build_payload(row, provider, suffix)
            if not payload:
                continue

            try:
                result = post_mapping(headers, payload)

                if result == "success":
                    success += 1
                    print(
                        f"✅ {provider} | {payload['provider_id']} | {payload['system_type']}"
                    )

                elif result == "not_found":
                    not_found += 1
                    print(f"⚠️ Not found for provider {provider}")

            except Exception as e:
                errors += 1
                print("❌ Error:", e)

    if success > 0:
        update_map_status(TARGET_ITTID, "upd1")
    elif not_found > 0:
        update_map_status(TARGET_ITTID, "new id")

    print("\n📊 SUMMARY")
    print(f"✅ Success: {success}")
    print(f"⚠️ Not Found: {not_found}")
    print(f"❌ Errors: {errors}")
    print("🏁 Done\n")


# =====================================================
# ENTRY
# =====================================================

if __name__ == "__main__":
    main()
