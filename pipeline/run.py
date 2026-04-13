"""AI Matrix Live data pipeline.

Detects new AEI releases on HuggingFace, downloads data, applies the
methodology from Simpson (2025), and outputs JSON for the website.

Usage:
    uv run python pipeline/run.py              # Incremental (new releases only)
    uv run python pipeline/run.py --seed       # Process all releases (initial seed)
    uv run python pipeline/run.py --force      # Reprocess all, overwrite outputs
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from pathlib import Path

import pandas as pd
from huggingface_hub import list_repo_tree

from pipeline.methodology import (
    fetch_world_bank_country_metadata,
    fetch_world_bank_population,
    process_release,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent
SITE_DATA_DIR = ROOT / "site" / "public" / "data"
CACHE_DIR = ROOT / "pipeline" / "cache"
LAST_RELEASE_FILE = ROOT / "pipeline" / "last_release.txt"

# ---------------------------------------------------------------------------
# Release detection
# ---------------------------------------------------------------------------

# Only releases with country-level interaction data (not labor market releases)
COUNTRY_RELEASE_PATTERN = re.compile(r"^release_(\d{4}_\d{2}_\d{2})$")


def discover_releases() -> list[str]:
    """List all AEI release folders on HuggingFace that contain country data.

    Returns:
        Sorted list of release folder names (e.g., ['release_2025_09_15', ...]).
    """
    items = list(
        list_repo_tree("Anthropic/EconomicIndex", repo_type="dataset", recursive=False)
    )
    releases = []
    for item in items:
        if COUNTRY_RELEASE_PATTERN.match(item.path):
            releases.append(item.path)

    # Verify each has a raw CSV (country-level data, not just labor market)
    valid = []
    all_items = list(
        list_repo_tree("Anthropic/EconomicIndex", repo_type="dataset", recursive=True)
    )
    paths = {item.path for item in all_items}
    for release in sorted(releases):
        has_raw = any(
            p.startswith(f"{release}/")
            and "aei_raw_claude_ai_" in p
            and p.endswith(".csv")
            for p in paths
        )
        if has_raw:
            valid.append(release)
            logger.info("Found release: %s", release)
        else:
            logger.debug("Skipping %s (no country-level raw CSV)", release)

    return valid


def find_raw_csv_path(release: str, all_paths: set[str]) -> str | None:
    """Find the raw claude_ai CSV path within a release folder.

    The path structure varies across releases, so we search recursively.
    """
    for path in sorted(all_paths):
        if (
            path.startswith(f"{release}/")
            and "aei_raw_claude_ai_" in path
            and path.endswith(".csv")
        ):
            return path
    return None


def get_processed_releases() -> set[str]:
    """Read the set of already-processed release IDs."""
    if not LAST_RELEASE_FILE.exists():
        return set()
    return set(LAST_RELEASE_FILE.read_text().strip().splitlines())


def save_processed_releases(releases: set[str]) -> None:
    """Write the set of processed release IDs."""
    LAST_RELEASE_FILE.parent.mkdir(parents=True, exist_ok=True)
    LAST_RELEASE_FILE.write_text("\n".join(sorted(releases)) + "\n")


# ---------------------------------------------------------------------------
# Population data with caching
# ---------------------------------------------------------------------------


def get_population() -> pd.DataFrame:
    """Fetch population data, using cache as fallback."""
    cache_path = CACHE_DIR / "population.json"

    try:
        population = fetch_world_bank_population(year=2023)
        # Cache for resilience
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        population.to_json(cache_path, orient="records", indent=2)
        logger.info("Population data cached to %s", cache_path)
        return population
    except Exception:
        logger.warning("World Bank API failed, falling back to cache")
        if cache_path.exists():
            return pd.read_json(cache_path, orient="records")
        raise RuntimeError(
            "World Bank API unreachable and no cached population data exists"
        )


# ---------------------------------------------------------------------------
# JSON output
# ---------------------------------------------------------------------------

# Fields to include in the JSON output for each country
COUNTRY_FIELDS = [
    "iso3",
    "country_name",
    "geo_id",
    "region",
    "income_level",
    "stage",
    "stage_name",
    "stage_rule",
    "access_score",
    "agency_composite",
    "usage_count",
    "population",
    "usage_per_capita",
    "co_creation",
    "collab_directive",
    "task_success_rate",
    "education_years_mean",
    "usecase_coursework",
    "usecase_work",
    "usecase_personal",
    "norm_co_creation",
    "norm_directive_inv",
    "norm_task_success",
    "norm_education",
]


def results_to_json(df: pd.DataFrame, release_id: str) -> list[dict]:
    """Convert a processed release DataFrame to JSON-serializable records."""
    # Filter to countries with valid scores
    valid = df.dropna(subset=["access_score", "agency_composite", "stage"]).copy()

    # Select available fields
    available = [f for f in COUNTRY_FIELDS if f in valid.columns]
    output = valid[available].copy()

    # Convert Int64 to int for JSON
    if "stage" in output.columns:
        output["stage"] = output["stage"].astype(int)

    # Round floats for readability
    float_cols = output.select_dtypes(include=["float64"]).columns
    output[float_cols] = output[float_cols].round(6)

    records = output.to_dict(orient="records")

    # Clean NaN values (JSON doesn't support NaN)
    for record in records:
        for key, value in list(record.items()):
            if pd.isna(value):
                record[key] = None

    return records


def extract_date_range(release_id: str, raw_csv_path: str) -> dict:
    """Extract the date range from the CSV filename."""
    match = re.search(r"(\d{4}-\d{2}-\d{2})_to_(\d{4}-\d{2}-\d{2})", raw_csv_path)
    if match:
        return {"date_start": match.group(1), "date_end": match.group(2)}
    return {"date_start": None, "date_end": None}


def write_outputs(
    all_wave_data: dict[str, list[dict]],
    wave_metadata: dict[str, dict],
) -> None:
    """Write countries.json and waves.json to the site data directory."""
    SITE_DATA_DIR.mkdir(parents=True, exist_ok=True)

    # countries.json: latest wave only
    latest_release = sorted(all_wave_data.keys())[-1]
    countries = all_wave_data[latest_release]
    countries_path = SITE_DATA_DIR / "countries.json"
    with open(countries_path, "w") as f:
        json.dump(
            {
                "release": latest_release,
                "metadata": wave_metadata[latest_release],
                "countries": countries,
            },
            f,
            indent=2,
        )
    logger.info("Wrote %s (%d countries)", countries_path, len(countries))

    # waves.json: all waves cumulative
    waves = []
    for release_id in sorted(all_wave_data.keys()):
        waves.append(
            {
                "release": release_id,
                "metadata": wave_metadata[release_id],
                "countries": all_wave_data[release_id],
            }
        )

    waves_path = SITE_DATA_DIR / "waves.json"
    with open(waves_path, "w") as f:
        json.dump(waves, f, indent=2)
    logger.info("Wrote %s (%d waves)", waves_path, len(waves))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description="AI Matrix Live data pipeline")
    parser.add_argument(
        "--seed",
        action="store_true",
        help="Process all releases (initial seed, skip already-processed check)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Reprocess all releases, overwrite outputs",
    )
    args = parser.parse_args()

    # Discover releases
    logger.info("Discovering AEI releases on HuggingFace...")
    releases = discover_releases()
    if not releases:
        logger.error("No country-level AEI releases found")
        return 1

    logger.info("Found %d country-level releases: %s", len(releases), releases)

    # Determine which releases to process
    processed = get_processed_releases()
    if args.seed or args.force:
        to_process = releases
    else:
        to_process = [r for r in releases if r not in processed]

    if not to_process:
        logger.info("No new releases to process")
        return 0

    logger.info("Will process %d release(s): %s", len(to_process), to_process)

    # Get all file paths for CSV discovery
    all_items = list(
        list_repo_tree("Anthropic/EconomicIndex", repo_type="dataset", recursive=True)
    )
    all_paths = {item.path for item in all_items}

    # Fetch population data and country metadata (region, income level)
    population = get_population()
    metadata_cache_path = CACHE_DIR / "country_metadata.json"
    try:
        country_meta = fetch_world_bank_country_metadata()
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        country_meta.to_json(metadata_cache_path, orient="records", indent=2)
    except Exception:
        logger.warning("World Bank metadata API failed, falling back to cache")
        if metadata_cache_path.exists():
            country_meta = pd.read_json(metadata_cache_path, orient="records")
        else:
            country_meta = pd.DataFrame(columns=["iso2", "region", "income_level"])

    # Process each release
    all_wave_data: dict[str, list[dict]] = {}
    wave_metadata: dict[str, dict] = {}

    # Load existing waves.json if doing incremental update
    waves_path = SITE_DATA_DIR / "waves.json"
    if not (args.seed or args.force) and waves_path.exists():
        with open(waves_path) as f:
            existing_waves = json.load(f)
        for wave in existing_waves:
            all_wave_data[wave["release"]] = wave["countries"]
            wave_metadata[wave["release"]] = wave["metadata"]
        logger.info("Loaded %d existing waves from waves.json", len(all_wave_data))

    for release in to_process:
        logger.info("Processing %s...", release)

        # Find the raw CSV
        csv_path = find_raw_csv_path(release, all_paths)
        if csv_path is None:
            logger.warning("No raw CSV found for %s, skipping", release)
            continue

        # Download
        from huggingface_hub import hf_hub_download

        local_path = hf_hub_download(
            "Anthropic/EconomicIndex", csv_path, repo_type="dataset"
        )
        raw_df = pd.read_csv(local_path)
        logger.info("Downloaded %s (%d rows)", csv_path, len(raw_df))

        # Extract release ID (date portion)
        release_id = release.replace("release_", "")

        # Process
        results = process_release(raw_df, population, release_id)

        # Join region and income level metadata (by geo_id = ISO-2)
        if len(country_meta) > 0 and "iso2" in country_meta.columns:
            results = results.merge(
                country_meta[["iso2", "region", "income_level"]],
                left_on="geo_id",
                right_on="iso2",
                how="left",
            )
            if "iso2_y" in results.columns:
                results = results.drop(columns=["iso2_y"])
            elif "iso2" in results.columns and "geo_id" in results.columns:
                results = results.drop(columns=["iso2"])

        # Determine which agency components were available
        agency_components = [c for c in results.columns if c.startswith("norm_")]
        dates = extract_date_range(release_id, csv_path)

        metadata = {
            **dates,
            "country_count": len(
                results.dropna(subset=["access_score", "agency_composite"])
            ),
            "agency_components": agency_components,
            "agency_component_count": len(agency_components),
        }

        # Convert to JSON records
        records = results_to_json(results, release_id)
        all_wave_data[release_id] = records
        wave_metadata[release_id] = metadata

        logger.info(
            "Processed %s: %d countries, %d agency components",
            release,
            metadata["country_count"],
            len(agency_components),
        )

    # Write outputs
    write_outputs(all_wave_data, wave_metadata)

    # Update processed releases
    processed.update(to_process)
    save_processed_releases(processed)

    logger.info("Pipeline complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
