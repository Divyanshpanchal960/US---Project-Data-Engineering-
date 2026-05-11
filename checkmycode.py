"""
========================================================
Data Acquisition — US Flight Delay Analytics
========================================================

Project:
US Domestic Flight Delay Analytics Platform

Dataset Source:
Bureau of Transportation Statistics (BTS)
https://www.transtats.bts.gov/

Project Notes:
- 2021-2023 ke monthly CSV files download karenge
- Airport reference JSON bhi download hoga
- Manifest file maintain hogi taaki same file dobara download na ho
"""

# =========================================================
# IMPORT LIBRARIES
# =========================================================

import os              # File/folder operations ke liye
import json            # JSON read/write karne ke liye
import time            # Sleep/timer ke liye
import requests        # API/file download karne ke liye
from pathlib import Path
from datetime import datetime, timezone


# =========================================================
# LOCAL DOWNLOAD DIRECTORY
# =========================================================

# Yaha sari downloaded files save hongi
LOCAL_DOWNLOAD_DIR = "./downloads"

# Folder create karega agar pehle se exist nahi karta
Path(LOCAL_DOWNLOAD_DIR).mkdir(exist_ok=True)


# =========================================================
# MANIFEST FILE PATH
# =========================================================

# Manifest ek tracking file hai
# Isme record rahega kaunsi files already download ho chuki hain

MANIFEST_PATH = os.path.join(
    LOCAL_DOWNLOAD_DIR,
    "download_manifest.json"
)


# =========================================================
# BTS CONFIGURATION
# =========================================================

# Base URL jahan se BTS zip files download hongi
BTS_BASE_URL = "https://transtats.bts.gov/PREZIP/"

# Kaunse years ka data download karna hai
YEARS = [2021]

# Kaunse months ka data download karna hai
# range(1,3) => Jan and Feb
MONTHS = range(1, 3)


# =========================================================
# LOAD MANIFEST FUNCTION
# =========================================================

def _load_manifest() -> dict:
    """
    Manifest file ko disk se load karega.

    Manifest ka use:
    - Already downloaded files track karna
    - Duplicate downloads avoid karna
    - Idempotency maintain karna
    """

    # Agar manifest file already exist karti hai
    if os.path.exists(MANIFEST_PATH):

        # File open karo read mode me
        with open(MANIFEST_PATH, "r") as f:

            # JSON data load karke return karo
            return json.load(f)

    # Agar first run hai aur manifest nahi hai
    # to empty manifest return karo
    return {"downloaded_files": {}}


# =========================================================
# SAVE MANIFEST FUNCTION
# =========================================================

def _save_manifest(manifest: dict) -> None:
    """
    Manifest ko disk me save karega.
    """

    # Temporary file path banaya
    tmp_path = MANIFEST_PATH + ".tmp"

    # Temp file me data write karo
    with open(tmp_path, "w") as f:
        json.dump(manifest, f, indent=2)

    # Temp file ko actual manifest se replace karo
    # Atomic operation hoti hai
    os.replace(tmp_path, MANIFEST_PATH)


# =========================================================
# CHECK FILE ALREADY DOWNLOADED OR NOT
# =========================================================

def _is_already_downloaded(manifest: dict, filename: str) -> bool:
    """
    Check karega file already successfully download hui hai ya nahi
    """

    # Manifest me filename search karo
    entry = manifest["downloaded_files"].get(filename)

    # True return karega agar status completed hai
    return entry is not None and entry.get("status") == "completed"


# =========================================================
# RECORD SUCCESSFUL DOWNLOAD
# =========================================================

def _record_download(
        manifest: dict,
        filename: str,
        year: int,
        month: int,
        local_zip_path: str,
        file_size_bytes: int
) -> None:

    """
    Successful download ko manifest me record karega
    """

    manifest["downloaded_files"][filename] = {

        # Download successful
        "status": "completed",

        # Download timestamp
        "downloaded_at":
        datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),

        # File size bytes me
        "file_size_bytes": file_size_bytes,

        # Local path
        "local_zip_path": local_zip_path,

        # Year and month metadata
        "year": year,
        "month": month,
    }

    # Manifest save karo
    _save_manifest(manifest)


# =========================================================
# RECORD FAILED DOWNLOAD
# =========================================================

def _record_failure(
        manifest: dict,
        filename: str,
        year: int,
        month: int,
        error: str
) -> None:

    """
    Failed download ka error manifest me store karega
    """

    manifest["downloaded_files"][filename] = {

        # Failed status
        "status": "failed",

        # Failure timestamp
        "failed_at":
        datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),

        # Error message
        "error": error,

        # Metadata
        "year": year,
        "month": month,
    }

    # Manifest save karo
    _save_manifest(manifest)


# =========================================================
# MAIN DOWNLOAD FUNCTION
# =========================================================

def download_bts_month(
        year: int,
        month: int,
        dest_dir: str,
        manifest: dict
) -> str | None:

    """
    BTS monthly ZIP file download karega
    """

    # Dynamic filename create kiya
    filename = (
        f"On_Time_Reporting_Carrier_On_Time_Performance"
        f"_1987_present_{year}_{month}.zip"
    )

    # Complete URL banaya
    url = f"{BTS_BASE_URL}{filename}"

    # Local file path
    local_zip = os.path.join(dest_dir, filename)

    # =====================================================
    # GUARD 1
    # =====================================================

    # Agar manifest me already completed hai
    if _is_already_downloaded(manifest, filename):

        print(f"  [SKIP] Already downloaded (manifest): {filename}")

        return local_zip

    # =====================================================
    # GUARD 2
    # =====================================================

    # Agar file disk me already hai
    if os.path.exists(local_zip) and os.path.getsize(local_zip) > 0:

        # File size nikala
        size = os.path.getsize(local_zip)

        print(f"  [SKIP] ZIP found on disk but not in manifest")
        print(f"         {filename}  ({size:,} bytes)")

        # Manifest me record karo
        _record_download(
            manifest,
            filename,
            year,
            month,
            local_zip,
            size
        )

        return local_zip

    # =====================================================
    # DOWNLOAD START
    # =====================================================

    print(f"  [DOWNLOAD] {year}-{month:02d}  →  {url}")

    try:

        # HTTP request bheji
        resp = requests.get(
            url,
            stream=True,
            timeout=120
        )

        # HTTP errors check karega
        resp.raise_for_status()

        # Bytes counter
        bytes_written = 0

        # File binary write mode me open
        with open(local_zip, "wb") as f:

            # Chunk wise download
            for chunk in resp.iter_content(
                    chunk_size=1024 * 1024):

                # Chunk write karo
                f.write(chunk)

                # Bytes count update
                bytes_written += len(chunk)

        print(f"  [OK] Saved {bytes_written:,} bytes → {local_zip}")

        # Successful download record karo
        _record_download(
            manifest,
            filename,
            year,
            month,
            local_zip,
            bytes_written
        )

        return local_zip

    except Exception as exc:

        # Error print karo
        print(f"  [ERROR] {year}-{month:02d}: {exc}")

        # Failure manifest me save karo
        _record_failure(
            manifest,
            filename,
            year,
            month,
            str(exc)
        )

        # Partial corrupt file delete karo
        if os.path.exists(local_zip):
            os.remove(local_zip)

        return None


# =========================================================
# MANIFEST SUMMARY
# =========================================================

def print_manifest_summary(manifest: dict) -> None:

    """
    Manifest ka summary print karega
    """

    entries = manifest["downloaded_files"]

    # Agar manifest empty hai
    if not entries:

        print("  (manifest is empty)")
        return

    # Completed entries
    completed = [
        e for e in entries.values()
        if e["status"] == "completed"
    ]

    # Failed entries
    failed = [
        e for e in entries.values()
        if e["status"] == "failed"
    ]

    # Total bytes calculate
    total_bytes = sum(
        e.get("file_size_bytes", 0)
        for e in completed
    )

    print(f"\n{'─'*60}")

    print(f"Manifest: {MANIFEST_PATH}")

    print(f"Completed : {len(completed)}")

    print(f"Failed : {len(failed)}")

    print(f"Total size: {total_bytes / (1024**3):.2f} GB")

    # Failed files print karo
    if failed:

        print("Failed files:")

        for name, e in entries.items():

            if e["status"] == "failed":

                print(
                    f"{name} — "
                    f"{e.get('error', 'unknown error')}"
                )

    print(f"{'─'*60}\n")


# =========================================================
# AIRPORT REFERENCE DOWNLOAD
# =========================================================

def download_airport_reference(dest_dir):

    """
    Airport metadata download karega
    """

    # OpenFlights dataset URL
    url = (
        "https://raw.githubusercontent.com/"
        "jpatokal/openflights/master/data/airports.dat"
    )

    # Local file path
    local_path = os.path.join(dest_dir, "airports.dat")

    print(f"[DOWNLOAD] Airport reference data")

    # Data request
    resp = requests.get(url, timeout=30)

    # HTTP errors check
    resp.raise_for_status()

    # Raw .dat file save
    with open(local_path, "wb") as f:
        f.write(resp.content)

    # CSV parsing library
    import csv

    # Column names
    cols = [
        "id", "name", "city", "country",
        "iata", "icao", "latitude",
        "longitude", "altitude",
        "utc_offset", "dst",
        "timezone", "type", "source"
    ]

    # Final airport list
    airports = []

    # Line by line parsing
    for line in resp.text.splitlines():

        row = next(csv.reader([line]))

        # Valid rows only
        if len(row) == len(cols):

            d = dict(zip(cols, row))

            # Valid IATA code check
            if (
                d["iata"]
                and len(d["iata"]) == 3
                and d["iata"] != "\\N"
            ):

                airports.append(d)

    # JSON output path
    json_path = os.path.join(dest_dir, "airports.json")

    # JSON save
    with open(json_path, "w") as f:
        json.dump(airports, f, indent=2)

    print(f"  [OK] {len(airports)} airports → {json_path}")

    return json_path


# =========================================================
# MAIN EXECUTION START
# =========================================================

if __name__ == "__main__":

    print("=" * 70)
    print("US Flight Delay Analytics — Data Acquisition")
    print("=" * 70)

    # Airport reference data download
    airport_path = download_airport_reference(
        LOCAL_DOWNLOAD_DIR
    )

    # Manifest load
    manifest = _load_manifest()

    print(
        f"\nManifest loaded — "
        f"{len(manifest['downloaded_files'])} entries found."
    )

    # Year loop
    for year in YEARS:

        # Month loop
        for month in MONTHS:

            # Monthly ZIP download
            zip_path = download_bts_month(
                year,
                month,
                LOCAL_DOWNLOAD_DIR,
                manifest
            )

            # Agar success hua
            if zip_path:

                print(f"Ready: {zip_path}")

                # Future S3 upload code
                # s3_prefix = f"flights/year={year}/month={month:02d}"
                # upload_to_s3(zip_path, s3_prefix)

            # BTS server overload avoid karne ke liye wait
            time.sleep(2)

    # Final manifest summary
    print_manifest_summary(manifest)

    print("Done.")