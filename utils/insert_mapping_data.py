import os
import json
import requests
from dotenv import load_dotenv
from sqlalchemy import create_engine, MetaData, Table, select, desc, update
from sqlalchemy.orm import Session
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import threading

# --- CONFIGURATION & AUTH --- #

load_dotenv()

API_BASE = "http://127.0.0.1:8001/v1.0"
ENDPOINT = f"{API_BASE}/hotels/add_provider_all_details_with_ittid/"

def get_database_engine():
    db_uri = (
        f"mysql+pymysql://{os.getenv('DB_USER')}:"
        f"{os.getenv('DB_PASSWORD')}@"
        f"{os.getenv('DB_HOST')}/"
        f"{os.getenv('DB_NAME')}"
    )
    return create_engine(db_uri, pool_pre_ping=True)

def get_auth_token():
    url = f"{API_BASE}/auth/token/"
    payload = {
        'username': os.getenv('API_USER'),
        'password': os.getenv('API_PASS')
    }
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    resp = requests.post(url, headers=headers, data=payload)
    resp.raise_for_status()
    return resp.json()['access_token']

def get_headers():
    token = get_auth_token()
    return {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {token}'
    }


# --- MAPPING DEFINITIONS --- #

PROVIDERS = [
    "hotelbeds", "ean", "agoda", "mgholiday", "restel", "stuba",
    "hyperguestdirect", "tbohotel", "goglobal", "ratehawkhotel",
    "adivahahotel", "grnconnect", "juniperhotel", "mikihotel",
    "paximumhotel", "adonishotel", "w2mhotel", "oryxhotel",
    "dotw", "hotelston", "letsflyhotel", "illusionshotel",
    "innstanttravel", "roomerang"
]

SUFFIX_MAP = {
    "":   "g",
    "_a": "b",
    "_b": "c",
    "_c": "d",
    "_d": "e",
    "_e": "f"
}


# --- CORE LOGIC --- #

def build_payload(row, provider, suffix):
    col_name = provider + suffix
    provider_id = getattr(row, col_name, None)
    if provider_id is None:
        return None

    vervo = getattr(row, "VervotechId", None)
    giata = getattr(row, "GiataCode",    None)

    return {
        "ittid":           row.ittid,
        "provider_name":   provider,
        "provider_id":     provider_id,
        "system_type":     SUFFIX_MAP[suffix],
        "vervotech_id":    vervo,
        "giata_code":      giata
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


def fetch_all_mappings(engine, offset=0, limit=10000):
    meta = MetaData()
    table = Table("global_hotel_mapping_copy_2", meta, autoload_with=engine)

    try:
        with Session(engine) as sess:
            stmt = (
                select(table).where(table.c.mapStatus != "upd1").order_by(desc(table.c.ittid)).offset(offset).limit(limit)

            )
            results = sess.execute(stmt).all()
            return results
    finally:
        engine.dispose()


def post_mapping(session, headers, payload):
    """POST and return the payload on success, refresh token if expired."""
    try:
        resp = session.post(ENDPOINT, headers=headers, data=json.dumps(payload))
        resp.raise_for_status()
        return payload

    except requests.exceptions.HTTPError as e:
        # If token expired or invalid, refresh and retry once
        if e.response is not None and e.response.status_code == 401:
            print("⚠️ Token expired. Refreshing access token...")
            new_headers = get_headers()  # refresh token
            resp = session.post(ENDPOINT, headers=new_headers, data=json.dumps(payload))
            resp.raise_for_status()
            return payload
        else:
            # Re-raise all other HTTP errors
            raise e


seen_lock = threading.Lock()
seen = set()


def update_map_status(engine, ittid):
    """Update mapStatus to 'upd1' for the given ittid"""
    meta = MetaData()
    table = Table("global_hotel_mapping_copy_2", meta, autoload_with=engine)

    try:
        with Session(engine) as sess:
            stmt = update(table).where(table.c.ittid == ittid).values(mapStatus="upd1")
            sess.execute(stmt)
            sess.commit()
    except Exception as e:
        print(f"❌ Error updating mapStatus for ittid {ittid}: {e}")
    finally:
        engine.dispose()


def post_mapping(session, headers, payload, engine):
    """POST and update mapStatus on success"""
    try:
        resp = session.post(ENDPOINT, headers=headers, data=json.dumps(payload))
        resp.raise_for_status()
        update_map_status(engine, payload["ittid"])
        return payload

    except requests.exceptions.HTTPError as e:
        if e.response is not None and e.response.status_code == 401:
            print("⚠️ Token expired. Refreshing access token...")
            new_headers = get_headers()
            resp = session.post(ENDPOINT, headers=new_headers, data=json.dumps(payload))
            resp.raise_for_status()
            update_map_status(engine, payload["ittid"])
            return payload
        else:
            raise e


def main():
    engine = get_database_engine()
    headers = get_headers()
    batch_size = 1000
    offset = 0

    with requests.Session() as sess, ThreadPoolExecutor(max_workers=10) as executor:
        while True:
            rows = fetch_all_mappings(engine, offset=offset, limit=batch_size)
            if not rows:
                break

            futures = []

            for row in rows:
                for provider in PROVIDERS:
                    for suffix in SUFFIX_MAP:
                        payload = build_payload(row, provider, suffix)
                        if not payload:
                            continue

                        key = (payload["provider_name"], payload["provider_id"])

                        with seen_lock:
                            if key in seen:
                                continue
                            seen.add(key)

                        futures.append(
                            executor.submit(
                                post_mapping, sess, headers, payload, engine
                            )
                        )

            for fut in as_completed(futures):
                try:
                    payload = fut.result()
                    print(
                        f"✅ Inserted and Updated: itt id={payload['ittid']} | "
                        f"provider={payload['provider_name']} | "
                        f"id={payload['provider_id']} | "
                        f"type={payload['system_type']}"
                    )
                except Exception as e:
                    print("❌ Error:", e)

            offset += batch_size
            time.sleep(0.2)

if __name__ == "__main__":
    main()
