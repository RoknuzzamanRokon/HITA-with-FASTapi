import os
import json
import requests
from dotenv import load_dotenv
from sqlalchemy import create_engine, MetaData, Table, select
from sqlalchemy.orm import Session
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- CONFIGURATION & AUTH --- #

load_dotenv()

API_BASE = "http://127.0.0.1:8000/v1.0"
ENDPOINT = f"{API_BASE}/hotels/mapping/add_provider_all_details_with_ittid/"

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
    col = provider + suffix
    pid = getattr(row, col, None)
    if pid is None:
        return None

    return {
        "ittid":         row.ittid,
        "provider_name": provider,
        "provider_id":   pid,
        "system_type":   SUFFIX_MAP[suffix],
        "vervotech_id":  getattr(row, "VervotechId", None),
        "giata_code":    getattr(row, "GiataCode",    None)
    }

def fetch_all_mappings(engine):
    meta  = MetaData()  
    table = Table("hotel_test_mapping", meta, autoload_with=engine)
    with Session(engine) as sess:
        return sess.execute(select(table)).all()

def fetch_existing_mappings(engine):
    """
    Returns two sets:
      - existing_triples: (ittid, provider_name, provider_id)
      - existing_pairs:   (provider_name, provider_id)
    """
    meta = MetaData()
    tgt  = Table("provider_mappings", meta, autoload_with=engine)
    stmt = select(
        tgt.c.ittid,
        tgt.c.provider_name,
        tgt.c.provider_id
    )
    with Session(engine) as sess:
        triples = set()
        pairs   = set()
        for row in sess.execute(stmt):
            triples.add((row.ittid, row.provider_name, row.provider_id))
            pairs.add((row.provider_name, row.provider_id))
        return triples, pairs

def post_mapping(session, headers, payload):
    resp = session.post(ENDPOINT, headers=headers, data=json.dumps(payload))
    resp.raise_for_status()
    return payload

def main():
    engine   = get_database_engine()
    headers  = get_headers()
    rows     = fetch_all_mappings(engine)
    existing = fetch_existing_mappings(engine)

    # Also track in‐run payloads
    existing_triples, existing_pairs = fetch_existing_mappings(engine)
    seen = set()

    with requests.Session() as sess, ThreadPoolExecutor(max_workers=50) as executor:
        futures = []

        for row in rows:
            for provider in PROVIDERS:
                for suffix in SUFFIX_MAP:
                    payload = build_payload(row, provider, suffix)
                    if not payload:
                        continue

                    triple = (
                        payload["ittid"],
                        payload["provider_name"],
                        payload["provider_id"]
                    )
                    pair   = (
                        payload["provider_name"],
                        payload["provider_id"]
                    )

                    # skip if already in DB by triple OR by pair
                    if triple in existing_triples or pair in existing_pairs:
                        print("--------------------------------------------------Triple skipping -----------------------------------------------------")
                        continue

                    # also skip duplicates within this run
                    if pair in seen:
                        print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~Pair skipping")
                        continue

                    seen.add(pair)
                    futures.append(
                        executor.submit(post_mapping, sess, headers, payload)
                    )

        for fut in as_completed(futures):
            try:
                p = fut.result()
                print(
                    f"✅ Inserted: itt id={p['ittid']} | "
                    f"provider={p['provider_name']} | "
                    f"id={p['provider_id']} | "
                    f"type={p['system_type']}"
                )
            except Exception as e:
                print("❌ Error:", e)

if __name__ == "__main__":
    main()
