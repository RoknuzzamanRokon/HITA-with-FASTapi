from sqlalchemy import create_engine
from dotenv import load_dotenv
import pandas as pd
import os
import json

load_dotenv()

db_host = os.getenv("DB_HOST")
db_user = os.getenv("DB_USER")
db_pass = os.getenv("DB_PASSWORD")
db_name = os.getenv("DB_NAME")

DATABASE_URL_SERVER = f"mysql+pymysql://{db_user}:{db_pass}@{db_host}/{db_name}"
engine = create_engine(DATABASE_URL_SERVER)


output_directory = "D:/Rokon/ofc_git/HITA_full/backend/static/countryJson"
os.makedirs(output_directory, exist_ok=True)


def get_country_code_list(engine, table):
    query = f"SELECT DISTINCT CountryCode FROM {table};"
    with engine.connect() as connection:
        df = pd.read_sql(query, connection)
    return df["CountryCode"].tolist()


def fetch_supplier_country_data(engine, table, country_code, supplier):
    supplier_columns = PROVIDER_MAPPING_FOR_DB[supplier]
    additional_columns = [
        "Name",
        "AddressLine1",
        "PropertyType",
        "PrimaryPhoto",
        "Rating",
        "Longitude",
        "Latitude",
        "VervotechId",
        "GiataCode",
        "ittid",
    ]
    all_columns = supplier_columns + additional_columns
    cols_str = ", ".join(all_columns)

    query = f"""
    SELECT {cols_str}
    FROM {table}
    WHERE CountryCode = '{country_code}';
    """

    with engine.connect() as connection:
        df = pd.read_sql(query, connection)

    # Drop rows without valid geographic data
    df = df.dropna(subset=["Longitude", "Latitude"])

    result = []
    for _, row in df.iterrows():
        supplier_list = [
            str(row[col]).strip()
            for col in supplier_columns
            if pd.notna(row[col]) and str(row[col]).strip() != ""
        ]

        if supplier_list:
            row_dict = {
                supplier: supplier_list,
                "name": row["Name"] if pd.notna(row["Name"]) else None,
                "addr": row["AddressLine1"] if pd.notna(row["AddressLine1"]) else None,
                "ptype": row["PropertyType"] if pd.notna(row["PropertyType"]) else None,
                "photo": row["PrimaryPhoto"] if pd.notna(row["PrimaryPhoto"]) else None,
                "star": row["Rating"] if pd.notna(row["Rating"]) else None,
                "lon": row["Longitude"],
                "lat": row["Latitude"],
                "vervotech": (
                    row["VervotechId"] if pd.notna(row["VervotechId"]) else None
                ),
                "giata": row["GiataCode"] if pd.notna(row["GiataCode"]) else None,
                "ittid": row["ittid"] if pd.notna(row["ittid"]) else None,
            }
            result.append(row_dict)

    return result


def save_country_data_to_json(country_code, data, output_folder):
    """
    Save the given data into a JSON file named as the country code inside the specified folder.
    """
    file_path = os.path.join(output_folder, f"{country_code}.json")
    with open(file_path, "w", encoding="utf-8") as json_file:
        json.dump(data, json_file, ensure_ascii=False, indent=4)


def generate_supplier_json_files_follow_all_supplier(engine, table, output_directory):
    """
    For each supplier in PROVIDER_MAPPING_FOR_DB:
      - Create a folder for that supplier.
      - Iterate over each country and save a JSON file with data only for that supplier.
    """
    country_codes = get_country_code_list(engine, table)
    for supplier in PROVIDER_MAPPING_FOR_DB:
        supplier_folder = os.path.join(output_directory, supplier)
        os.makedirs(supplier_folder, exist_ok=True)

        for country_code in country_codes:
            print(f"Processing {supplier} data for country: {country_code}")
            data = fetch_supplier_country_data(engine, table, country_code, supplier)
            if data:
                save_country_data_to_json(country_code, data, supplier_folder)
                print(f"{supplier} - {country_code} saved successfully.")
            else:
                print(f"No data found for {supplier} in country: {country_code}")


def only_generate_a_supplier_json_files(
    engine, table, output_directory, supplier_name=None
):
    """
    If supplier_name is provided, process only that supplier.
    Otherwise, iterate over all suppliers in PROVIDER_MAPPING_FOR_DB.
    """
    country_codes = get_country_code_list(engine, table)

    # Determine which suppliers to process
    if supplier_name:
        if supplier_name not in PROVIDER_MAPPING_FOR_DB:
            print(f"Supplier '{supplier_name}' not found in mapping.")
            return
        suppliers_to_process = [supplier_name]
    else:
        suppliers_to_process = list(PROVIDER_MAPPING_FOR_DB.keys())

    for supplier in suppliers_to_process:
        supplier_folder = os.path.join(output_directory, supplier)
        os.makedirs(supplier_folder, exist_ok=True)

        for country_code in country_codes:
            print(f"Processing {supplier} data for country: {country_code}")
            data = fetch_supplier_country_data(engine, table, country_code, supplier)
            if data:
                save_country_data_to_json(country_code, data, supplier_folder)
                print(f"{supplier} - {country_code} saved successfully.")
            else:
                print(f"No data found for {supplier} in country: {country_code}")


PROVIDER_MAPPING_FOR_DB = {
    "hotelbeds": [
        "hotelbeds",
        "hotelbeds_a",
        "hotelbeds_b",
        "hotelbeds_c",
        "hotelbeds_d",
        "hotelbeds_e",
    ],
    "ean": ["ean", "ean_a", "ean_b", "ean_c", "ean_d", "ean_e"],
    "agoda": ["agoda", "agoda_a", "agoda_b", "agoda_c", "agoda_d", "agoda_e"],
    "mgholiday": [
        "mgholiday",
        "mgholiday_a",
        "mgholiday_b",
        "mgholiday_c",
        "mgholiday_d",
        "mgholiday_e",
    ],
    "restel": ["restel", "restel_a", "restel_b", "restel_c", "restel_d", "restel_e"],
    "stuba": ["stuba", "stuba_a", "stuba_b", "stuba_c", "stuba_d", "stuba_e"],
    "hyperguestdirect": [
        "hyperguestdirect",
        "hyperguestdirect_a",
        "hyperguestdirect_b",
        "hyperguestdirect_c",
        "hyperguestdirect_d",
        "hyperguestdirect_e",
    ],
    "tbohotel": [
        "tbohotel",
        "tbohotel_a",
        "tbohotel_b",
        "tbohotel_c",
        "tbohotel_d",
        "tbohotel_e",
    ],
    "goglobal": [
        "goglobal",
        "goglobal_a",
        "goglobal_b",
        "goglobal_c",
        "goglobal_d",
        "goglobal_e",
    ],
    "ratehawkhotel": [
        "ratehawkhotel",
        "ratehawkhotel_a",
        "ratehawkhotel_b",
        "ratehawkhotel_c",
        "ratehawkhotel_d",
        "ratehawkhotel_e",
    ],
    "grnconnect": [
        "grnconnect",
        "grnconnect_a",
        "grnconnect_b",
        "grnconnect_c",
        "grnconnect_d",
        "grnconnect_e",
    ],
    "juniperhotel": [
        "juniperhotel",
        "juniperhotel_a",
        "juniperhotel_b",
        "juniperhotel_c",
        "juniperhotel_d",
        "juniperhotel_e",
    ],
    "paximumhotel": [
        "paximumhotel",
        "paximumhotel_a",
        "paximumhotel_b",
        "paximumhotel_c",
        "paximumhotel_d",
        "paximumhotel_e",
    ],
    "oryxhotel": [
        "oryxhotel",
        "oryxhotel_a",
        "oryxhotel_b",
        "oryxhotel_c",
        "oryxhotel_d",
        "oryxhotel_e",
    ],
    "dotw": ["dotw", "dotw_a", "dotw_b", "dotw_c", "dotw_d", "dotw_e"],
    "hotelston": [
        "hotelston",
        "hotelston_a",
        "hotelston_b",
        "hotelston_c",
        "hotelston_d",
        "hotelston_e",
    ],
    "letsflyhotel": [
        "letsflyhotel",
        "letsflyhotel_a",
        "letsflyhotel_b",
        "letsflyhotel_c",
        "letsflyhotel_d",
        "letsflyhotel_e",
    ],
    "illusionshotel": [
        "illusionshotel",
        "illusionshotel_a",
        "illusionshotel_b",
        "illusionshotel_c",
        "illusionshotel_d",
        "illusionshotel_e",
    ],
    "innstant": [
        "innstanttravel",
        "innstanttravel_a",
        "innstanttravel_b",
        "innstanttravel_c",
        "innstanttravel_d",
        "innstanttravel_e",
    ],
    "roomerang": [
        "roomerang",
        "roomerang_a",
        "roomerang_b",
        "roomerang_c",
        "roomerang_d",
        "roomerang_e",
    ],
    "mikihotel": [
        "mikihotel",
        "mikihotel_a",
        "mikihotel_b",
        "mikihotel_c",
        "mikihotel_d",
        "mikihotel_e",
    ],
    "adonishotel": [
        "adonishotel",
        "adonishotel_a",
        "adonishotel_b",
        "adonishotel_c",
        "adonishotel_d",
        "adonishotel_e",
    ],
    "w2mhotel": [
        "w2mhotel",
        "w2mhotel_a",
        "w2mhotel_b",
        "w2mhotel_c",
        "w2mhotel_d",
        "w2mhotel_e",
    ],
    "kiwihotel": [
        "kiwihotel",
        "kiwihotel_a",
        "kiwihotel_b",
        "kiwihotel_c",
        "kiwihotel_d",
        "kiwihotel_e",
    ],
    "rakuten": [
        "rakuten",
        "rakuten_a",
        "rakuten_b",
        "rakuten_c",
        "rakuten_d",
        "rakuten_e",
    ],
    "rnrhotel": [
        "rnrhotel",
        "rnrhotel_a",
        "rnrhotel_b",
        "rnrhotel_c",
        "rnrhotel_d",
        "rnrhotel_e",
    ],
}


if __name__ == "__main__":
    table = "global_hotel_mapping_copy_2"
    supplier_name = "ean"
    only_generate_a_supplier_json_files(engine, table, output_directory, supplier_name)
    print("Supplier JSON files generated successfully!")
