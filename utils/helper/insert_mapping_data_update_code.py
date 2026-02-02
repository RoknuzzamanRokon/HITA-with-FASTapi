import os
import json
import time
import signal
import asyncio
import aiohttp
from sqlalchemy import create_engine, MetaData, Table, select, update, desc
from sqlalchemy.orm import Session
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager, contextmanager
from dotenv import load_dotenv
import logging
import sys
from typing import List, Dict, Any, Optional

# =====================================================
# CONFIG & LOGGING
# =====================================================

load_dotenv()

# Configure logging with proper encoding for Windows
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("mapping_process.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

# Configuration - Use port 8000 (confirmed working)
API_BASE = "http://127.0.0.1:8028"  # Use port 8000 instead of overloaded 8028
ENDPOINT = f"{API_BASE}/v1.0/hotels/add_provider_all_details_with_ittid/"
TABLE_NAME = "global_hotel_mapping_copy_2_new"  # Use same table as working script

# Optimized for throughput but not overwhelming the server
BATCH_SIZE = 100  # Reduced batch size
DB_FETCH_SIZE = 500  # Reduced fetch size
MAX_CONCURRENT_REQUESTS = 5  # Much lower concurrency to avoid overwhelming server
MAX_RETRIES = 3
RETRY_DELAY = 2  # Longer delay for retries

# Database connection pool settings
DB_POOL_SIZE = 5  # Reduced pool size
DB_MAX_OVERFLOW = 5  # Reduced overflow

# Logging setup
# =====================================================
# DATABASE - OPTIMIZED
# =====================================================


class DatabaseManager:
    """Optimized database manager with connection pooling"""

    def __init__(self):
        self.engine = None
        self.metadata = None
        self.table = None
        self._init_lock = asyncio.Lock()

    async def init(self):
        """Initialize database connection asynchronously"""
        async with self._init_lock:
            if self.engine is None:
                self.engine = create_engine(
                    f"mysql+pymysql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@"
                    f"{os.getenv('DB_HOST')}/{os.getenv('DB_NAME')}",
                    pool_pre_ping=True,
                    pool_size=DB_POOL_SIZE,
                    max_overflow=DB_MAX_OVERFLOW,
                    pool_recycle=1800,
                    pool_timeout=30,
                    echo=False,  # Disable SQL echo for performance
                )
                self.metadata = MetaData()
                self.table = Table(TABLE_NAME, self.metadata, autoload_with=self.engine)

    @contextmanager
    def get_session(self):
        """Get database session with context manager"""
        session = Session(self.engine)
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    async def fetch_batch(self, offset: int, limit: int) -> List[Any]:
        """Fetch batch of rows asynchronously - only NULL mapStatus records"""
        loop = asyncio.get_event_loop()

        def _fetch():
            with self.get_session() as session:
                stmt = (
                    select(self.table)
                    .where(self.table.c.mapStatus.is_(None))
                    .order_by(desc(self.table.c.ittid))
                    .offset(offset)
                    .limit(limit)
                )
                results = session.execute(stmt).fetchall()
                logger.info(
                    f"Fetched {len(results)} records with NULL mapStatus (offset={offset}, limit={limit})"
                )
                return results

        return await loop.run_in_executor(None, _fetch)

    async def bulk_update_status(self, updates: Dict[str, str]):
        """Bulk update mapStatus for multiple rows"""
        loop = asyncio.get_event_loop()

        def _bulk_update():
            with self.get_session() as session:
                updated_count = 0
                for ittid, status in updates.items():
                    result = session.execute(
                        update(self.table)
                        .where(self.table.c.ittid == ittid)
                        .values(mapStatus=status)
                    )
                    updated_count += result.rowcount
                session.commit()
                return updated_count

        updated_count = await loop.run_in_executor(None, _bulk_update)
        logger.info(f"Successfully updated {updated_count} records in database")


db_manager = DatabaseManager()

# =====================================================
# HTTP CLIENT - ASYNCHRONOUS
# =====================================================


class AsyncHttpClient:
    """Asynchronous HTTP client with connection pooling and retry logic"""

    def __init__(self, max_concurrent: int = MAX_CONCURRENT_REQUESTS):
        self.max_concurrent = max_concurrent
        self.session = None
        self.headers = None
        self._auth_lock = asyncio.Lock()
        self.semaphore = asyncio.Semaphore(max_concurrent)

    async def init(self):
        """Initialize aiohttp session"""
        timeout = aiohttp.ClientTimeout(total=60, connect=10, sock_read=30)
        connector = aiohttp.TCPConnector(
            limit=10,  # Much lower total connection limit
            limit_per_host=5,  # Lower per-host limit
            ttl_dns_cache=300,
            force_close=True,  # Force close connections to prevent buildup
        )
        # Don't set default Content-Type header to avoid conflicts with FormData
        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
        )
        await self._get_auth_token()

    async def _get_auth_token(self):
        """Get authentication token with retry logic"""
        # Use the same format as the working script
        auth_data = {
            "username": os.getenv("API_USER"),
            "password": os.getenv("API_PASS"),
        }

        for attempt in range(MAX_RETRIES):
            try:
                # Use the same format as working script: application/x-www-form-urlencoded
                headers = {"Content-Type": "application/x-www-form-urlencoded"}

                async with self.session.post(
                    f"{API_BASE}/v1.0/auth/token",  # Use v1.0 prefix for port 8000
                    data=auth_data,  # Use simple dict, not FormData
                    headers=headers,  # Use form-urlencoded header
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        self.headers = {
                            "Authorization": f"Bearer {data['access_token']}"
                        }
                        logger.info("Authentication successful")
                        return
                    else:
                        response_text = await response.text()
                        logger.warning(
                            f"Auth failed attempt {attempt + 1}: {response.status} - {response_text}"
                        )
            except Exception as e:
                logger.warning(f"Auth attempt {attempt + 1} failed: {str(e)}")

            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(RETRY_DELAY * (2**attempt))

        raise Exception("Failed to authenticate after retries")

    async def post_with_retry(self, payload: Dict[str, Any]) -> str:
        """Post payload with retry logic and rate limiting"""
        async with self.semaphore:  # Limit concurrent requests
            for attempt in range(MAX_RETRIES):
                try:
                    # Use JSON content-type for API requests (not auth)
                    request_headers = {
                        **self.headers,  # Include Authorization header
                        "Content-Type": "application/json",
                    }

                    async with self.session.post(
                        ENDPOINT,
                        json=payload,
                        headers=request_headers,
                        timeout=aiohttp.ClientTimeout(total=30),
                    ) as response:

                        # Handle token expiration
                        if response.status == 401:
                            async with self._auth_lock:
                                await self._get_auth_token()
                            continue

                        if response.status == 404:
                            return "not_found"

                        if response.status in [200, 201]:
                            return "success"

                        # For other status codes, log and retry
                        response_text = await response.text()
                        logger.warning(
                            f"Request failed with status {response.status} on attempt {attempt + 1}: {response_text[:200]}"
                        )

                except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                    logger.warning(f"Request error on attempt {attempt + 1}: {str(e)}")

                # Exponential backoff
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_DELAY * (2**attempt))

            return "error"

    async def close(self):
        """Close the HTTP session"""
        if self.session:
            await self.session.close()


http_client = AsyncHttpClient()

# =====================================================
# PROVIDERS CONFIG
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
# GLOBAL STATE - THREAD SAFE
# =====================================================


class Counter:
    """Thread-safe counter for statistics"""

    def __init__(self):
        self.success = 0
        self.not_found = 0
        self.error = 0
        self.lock = asyncio.Lock()

    async def increment_success(self):
        async with self.lock:
            self.success += 1

    async def increment_not_found(self):
        async with self.lock:
            self.not_found += 1

    async def increment_error(self):
        async with self.lock:
            self.error += 1

    def get_stats(self):
        return self.success, self.not_found, self.error


counter = Counter()
shutdown_requested = False

# =====================================================
# SIGNAL HANDLING
# =====================================================


def signal_handler(sig, frame):
    global shutdown_requested
    logger.info("\n⚠️ Graceful shutdown requested...")
    shutdown_requested = True


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# =====================================================
# CORE PROCESSING FUNCTIONS
# =====================================================


def build_payloads(row) -> List[Dict[str, Any]]:
    """Build payloads for all providers in a row"""
    payloads = []
    row_dict = row._asdict() if hasattr(row, "_asdict") else dict(row)

    for provider in PROVIDERS:
        for suffix, sys_type in SUFFIX_MAP.items():
            pid = row_dict.get(provider + suffix)
            if pid and str(pid).strip():  # Check if not None and not empty
                payloads.append(
                    {
                        "ittid": row_dict["ittid"],
                        "provider_name": provider,
                        "provider_id": pid,
                        "system_type": sys_type,
                        "vervotech_id": row_dict.get("VervotechId"),
                        "giata_code": row_dict.get("GiataCode"),
                    }
                )
    return payloads


async def process_row_batch(rows: List[Any]) -> Dict[str, List[str]]:
    """
    Process a batch of rows concurrently
    Returns: Dict with lists of ittid for each status
    """
    # Prepare all payloads for the batch
    all_payloads = []
    row_payload_map = {}

    for row in rows:
        payloads = build_payloads(row)
        if payloads:
            all_payloads.extend(payloads)
            row_payload_map[row.ittid] = {
                "payload_count": len(payloads),
                "success_count": 0,
                "not_found_count": 0,
                "error_count": 0,
            }

    if not all_payloads:
        return {"success": [], "not_found": [], "error": []}

    # Process all payloads concurrently
    tasks = [http_client.post_with_retry(payload) for payload in all_payloads]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Process results
    status_updates = {"success": [], "not_found": [], "error": []}
    current_idx = 0

    for ittid, row_info in row_payload_map.items():
        payload_count = row_info["payload_count"]
        row_results = results[current_idx : current_idx + payload_count]
        current_idx += payload_count

        # Count results for this row
        success = any(
            r == "success" for r in row_results if not isinstance(r, Exception)
        )
        not_found = any(
            r == "not_found" for r in row_results if not isinstance(r, Exception)
        )

        if success:
            status_updates["success"].append(ittid)
            await counter.increment_success()
        elif not_found:
            status_updates["not_found"].append(ittid)
            await counter.increment_not_found()
        else:
            status_updates["error"].append(ittid)
            await counter.increment_error()

    return status_updates


# =====================================================
# PROGRESS MANAGEMENT
# =====================================================


class ProgressManager:
    """Manage progress saving and loading"""

    def __init__(self, filename="mapping_progress.json"):
        self.filename = filename

    def save(self, offset: int):
        """Save progress to file"""
        stats = {
            "offset": offset,
            "success": counter.success,
            "not_found": counter.not_found,
            "error": counter.error,
            "timestamp": time.time(),
        }

        try:
            with open(self.filename, "w") as f:
                json.dump(stats, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save progress: {e}")

    def load(self) -> tuple:
        """Load progress from file"""
        try:
            if os.path.exists(self.filename):
                with open(self.filename, "r") as f:
                    data = json.load(f)
                return (
                    data.get("offset", 0),
                    data.get("success", 0),
                    data.get("not_found", 0),
                    data.get("error", 0),
                )
        except Exception as e:
            logger.warning(f"Failed to load progress: {e}")

        return 0, 0, 0, 0


progress_manager = ProgressManager()

# =====================================================
# MAIN ASYNC PROCESSOR
# =====================================================


async def process_batch(offset: int) -> bool:
    """Process a single batch of rows"""
    # Fetch rows
    rows = await db_manager.fetch_batch(offset, DB_FETCH_SIZE)
    if not rows:
        return False

    logger.info(f"Processing batch: offset={offset}, rows={len(rows)}")

    # Process rows in smaller sub-batches for better memory management
    batch_updates = {"success": [], "not_found": [], "error": []}

    for i in range(0, len(rows), BATCH_SIZE):
        sub_batch = rows[i : i + BATCH_SIZE]
        updates = await process_row_batch(sub_batch)

        # Accumulate updates
        for key in batch_updates:
            batch_updates[key].extend(updates[key])

        # Add delay between sub-batches to avoid overwhelming server
        if i + BATCH_SIZE < len(rows):
            await asyncio.sleep(1)

    # Bulk update database with all changes
    if batch_updates["success"] or batch_updates["not_found"]:
        update_dict = {}
        for ittid in batch_updates["success"]:
            update_dict[ittid] = "upd2"
        for ittid in batch_updates["not_found"]:
            update_dict[ittid] = "new id"

        # Log the updates being made
        if update_dict:
            logger.info(
                f"Updating {len(update_dict)} records: Success={len(batch_updates['success'])}, NotFound={len(batch_updates['not_found'])}"
            )

        await db_manager.bulk_update_status(update_dict)

    return True


async def main_async():
    """Main async processing loop"""
    global shutdown_requested

    # Initialize components
    logger.info("Initializing components...")
    await db_manager.init()
    await http_client.init()

    try:
        # Load progress
        offset, success, not_found, error = progress_manager.load()
        counter.success = success
        counter.not_found = not_found
        counter.error = error

        logger.info(f"Starting from offset {offset}")

        # Main processing loop
        batch_count = 0

        while not shutdown_requested:
            start_time = time.time()

            # Process batch
            has_more = await process_batch(offset)

            if not has_more:
                logger.info("All records processed")
                break

            # Update offset and save progress
            offset += DB_FETCH_SIZE
            batch_count += 1

            # Save progress every few batches
            if batch_count % 5 == 0:
                progress_manager.save(offset)

                # Log progress
                success, not_found, error = counter.get_stats()
                elapsed = time.time() - start_time
                rows_per_sec = DB_FETCH_SIZE / elapsed if elapsed > 0 else 0

                logger.info(
                    f"Batch {batch_count} | "
                    f"Offset={offset} | "
                    f"Success={success} | "
                    f"NotFound={not_found} | "
                    f"Errors={error} | "
                    f"Speed={rows_per_sec:.1f} rows/sec"
                )

            # Add delay between main batches to give server time to recover
            await asyncio.sleep(2)

        # Final save
        progress_manager.save(offset)

        # Final stats
        success, not_found, error = counter.get_stats()
        logger.info("\nFINAL SUMMARY")
        logger.info(f"Success: {success}")
        logger.info(f"Not Found: {not_found}")
        logger.info(f"Errors: {error}")

    finally:
        # Ensure proper cleanup
        await http_client.close()


# =====================================================
# ENTRY POINT
# =====================================================


def main():
    """Main entry point"""
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        logger.info("\nProcess interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
