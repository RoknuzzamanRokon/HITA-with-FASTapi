from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import os
import pandas as pd
import numpy as np

load_dotenv()

# Database configuration
db_host = os.getenv('DB_HOST')
db_user = os.getenv('DB_USER')
db_password = os.getenv('DB_PASSWORD')
db_name = os.getenv('DB_NAME')
table = "global_hotel_mapping_copy_2"

# Create database engine
connection_url = f"mysql+pymysql://{db_user}:{db_password}@{db_host}/{db_name}"
engine = create_engine(connection_url)

# Provider mappings (unchanged)
provider_mappings = {
    "hotelbeds": ["hotelbeds", "hotelbeds_a", "hotelbeds_b", "hotelbeds_c", "hotelbeds_d", "hotelbeds_e"],
    "ean": ["ean", "ean_a", "ean_b", "ean_c", "ean_d", "ean_e"],
    "agoda": ["agoda", "agoda_a", "agoda_b", "agoda_c", "agoda_d", "agoda_e"],
    "mgholiday": ["mgholiday", "mgholiday_a", "mgholiday_b", "mgholiday_c", "mgholiday_d", "mgholiday_e"],
    "restel": ["restel", "restel_a", "restel_b", "restel_c", "restel_d", "restel_e"],
    "stuba": ["stuba", "stuba_a", "stuba_b", "stuba_c", "stuba_d", "stuba_e"],
    "hyperguestdirect": ["hyperguestdirect", "hyperguestdirect_a", "hyperguestdirect_b", "hyperguestdirect_c", "hyperguestdirect_d", "hyperguestdirect_e"],
    "tbohotel": ["tbohotel", "tbohotel_a", "tbohotel_b", "tbohotel_c", "tbohotel_d", "tbohotel_e"],
    "goglobal": ["goglobal", "goglobal_a", "goglobal_b", "goglobal_c", "goglobal_d", "goglobal_e"],
    "ratehawkhotel": ["ratehawkhotel", "ratehawkhotel_a", "ratehawkhotel_b", "ratehawkhotel_c", "ratehawkhotel_d", "ratehawkhotel_e"],
    "adivahahotel": ["adivahahotel", "adivahahotel_a", "adivahahotel_b", "adivahahotel_c", "adivahahotel_d", "adivahahotel_e"],
    "grnconnect": ["grnconnect", "grnconnect_a", "grnconnect_b", "grnconnect_c", "grnconnect_d", "grnconnect_e"],
    "juniper": ["juniperhotel", "juniperhotel_a", "juniperhotel_b", "juniperhotel_c", "juniperhotel_d", "juniperhotel_e"],
    "mikihotel": ["mikihotel", "mikihotel_a", "mikihotel_b", "mikihotel_c", "mikihotel_d", "mikihotel_e"],
    "paximumhotel": ["paximumhotel", "paximumhotel_a", "paximumhotel_b", "paximumhotel_c", "paximumhotel_d", "paximumhotel_e"],
    "adonishotel": ["adonishotel", "adonishotel_a", "adonishotel_b", "adonishotel_c", "adonishotel_d", "adonishotel_e"],
    "w2mhotel": ["w2mhotel", "w2mhotel_a", "w2mhotel_b", "w2mhotel_c", "w2mhotel_d", "w2mhotel_e"],
    "oryxhotel": ["oryxhotel", "oryxhotel_a", "oryxhotel_b", "oryxhotel_c", "oryxhotel_d", "oryxhotel_e"],
    "dotw": ["dotw", "dotw_a", "dotw_b", "dotw_c", "dotw_d", "dotw_e"],
    "hotelston": ["hotelston", "hotelston_a", "hotelston_b", "hotelston_c", "hotelston_d", "hotelston_e"],
    "letsflyhotel": ["letsflyhotel", "letsflyhotel_a", "letsflyhotel_b", "letsflyhotel_c", "letsflyhotel_d", "letsflyhotel_e"],
    "illusionshotel": ["illusionshotel", "illusionshotel_a", "illusionshotel_b", "illusionshotel_c", "illusionshotel_d", "illusionshotel_e"],
    "innstanttravel": ["innstanttravel", "innstanttravel_a", "innstanttravel_b", "innstanttravel_c", "innstanttravel_d", "innstanttravel_e"],
    "roomerang": ["roomerang", "roomerang_a", "roomerang_b", "roomerang_c", "roomerang_d", "roomerang_e"]
}


def generate_hotel_id_files(supplier, provider_mappings, engine, table_name):
    # Get columns for the specified supplier
    columns = provider_mappings.get(supplier)
    if not columns:
        print(f"Supplier {supplier} not found in provider mappings.")
        return

    selected_columns = ", ".join(columns)
    where_clause = " OR ".join([f"{col} IS NOT NULL AND {col} != ''" for col in columns])
    query = f"SELECT {selected_columns} FROM {table_name} WHERE {where_clause};"
    
    try:
        df = pd.read_sql(text(query), engine)
        
        hotel_ids = set()
        for col in columns:
            # Clean and collect non-empty IDs
            non_empty = df[col].astype(str).str.strip().replace(r'^\s*$', np.nan, regex=True).dropna()
            hotel_ids.update(non_empty.unique())
        
        if hotel_ids:
            # Numeric vs. non-numeric sorting
            numeric_ids = sorted([int(id) for id in hotel_ids if id.isdigit()])
            non_numeric_ids = sorted([id for id in hotel_ids if not id.isdigit()])
            
            # Combine and convert to strings
            sorted_ids = [str(id) for id in numeric_ids] + non_numeric_ids
            
            # Write to file
            filename = f"{supplier}_hotel_id_list.txt"
            with open(filename, 'w') as f:
                f.write("\n".join(sorted_ids) + "\n")
            print(f"Generated {filename} with {len(sorted_ids)} unique IDs.")
        else:
            print(f"No hotel IDs found for {supplier}.")
    
    except Exception as e:
        print(f"Error processing {supplier}: {e}")

def get_hotel_ids_for_supplier(supplier, provider_mappings, engine, table_name):
    """
    Get hotel IDs for a specific supplier from database
    
    Args:
        supplier: Supplier name
        provider_mappings: Dictionary mapping suppliers to database columns
        engine: Database engine
        table_name: Database table name
        
    Returns:
        List of hotel IDs as integers
    """
    # Get columns for the specified supplier
    columns = provider_mappings.get(supplier)
    if not columns:
        print(f"Supplier {supplier} not found in provider mappings.")
        return []

    selected_columns = ", ".join(columns)
    where_clause = " OR ".join([f"{col} IS NOT NULL AND {col} != ''" for col in columns])
    query = f"SELECT {selected_columns} FROM {table_name} WHERE {where_clause};"
    
    try:
        df = pd.read_sql(text(query), engine)
        
        hotel_ids = set()
        for col in columns:
            # Clean and collect non-empty IDs
            non_empty = df[col].astype(str).str.strip().replace(r'^\s*$', np.nan, regex=True).dropna()
            hotel_ids.update(non_empty.unique())
        
        # Convert to integers where possible
        numeric_ids = []
        for id_str in hotel_ids:
            try:
                if id_str.isdigit():
                    numeric_ids.append(int(id_str))
            except (ValueError, AttributeError):
                continue
        
        return sorted(numeric_ids)
        
    except Exception as e:
        print(f"Error processing {supplier}: {e}")
        return []

# Keep the original function for backward compatibility
generate_hotel_id_files('agoda', provider_mappings, engine, table)