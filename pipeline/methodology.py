"""AI Matrix methodology: agency composite, stage assignment, and access calculation.

Replicates the methodology from Simpson (2025), "Decomposing the Capability
Overhang: Access, Agency, and the Geography of AI Adoption."
https://doi.org/10.2139/ssrn.5228571
"""

from __future__ import annotations

import logging
import math
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants from the paper
# ---------------------------------------------------------------------------

# Minimum conversation count for a country to be included
MIN_OBSERVATIONS = 200

# Stage assignment thresholds (Section 3.2 of the paper)
COURSEWORK_STAGE1_THRESHOLD = 0.30
WORK_STAGE2_THRESHOLD = 0.48
COURSEWORK_STAGE2_MAX = 0.25
PERSONAL_STAGE3_THRESHOLD = 0.38

# Residual agency composite cutpoints
AGENCY_STAGE2_CUTPOINT = 0.55
AGENCY_STAGE3_CUTPOINT = 0.42

# Collaboration clusters that constitute "co-creation"
CO_CREATION_CLUSTERS = frozenset({"task iteration", "learning", "validation"})

STAGE_NAMES = {
    1: "Full Dependency",
    2: "Elite Empowerment",
    3: "Passive Dependency",
    4: "Full Empowerment",
}

QUADRANT_LABELS = {
    1: "Low Access, Low Agency",
    2: "High Access, Low Agency",
    3: "Low Access, High Agency",
    4: "High Access, High Agency",
}


# ---------------------------------------------------------------------------
# Data extraction: long-format AEI CSV → country-level wide DataFrame
# ---------------------------------------------------------------------------


def extract_country_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """Extract country-level metrics from a long-format AEI raw CSV.

    Args:
        df: Raw AEI DataFrame with columns: geo_id, geography, facet,
            level, variable, cluster_name, value.

    Returns:
        Wide DataFrame indexed by geo_id (ISO-2) with columns for each
        metric needed by the methodology.
    """
    country = df[(df["geography"] == "country") & (df["level"] == 0)].copy()

    records: list[dict[str, Any]] = []
    for geo_id, group in country.groupby("geo_id"):
        record: dict[str, Any] = {"geo_id": geo_id}

        # Usage count
        usage = group[
            (group["facet"] == "country") & (group["variable"] == "usage_count")
        ]
        if len(usage) > 0:
            record["usage_count"] = usage["value"].iloc[0]
        else:
            continue  # Skip countries with no usage data

        # Collaboration cluster percentages
        collab = group[
            (group["facet"] == "collaboration")
            & (group["variable"] == "collaboration_pct")
        ]
        for _, row in collab.iterrows():
            cluster = row["cluster_name"]
            if pd.notna(cluster):
                record[f"collab_{cluster}"] = row["value"] / 100.0

        # Use case percentages (coursework, work, personal)
        use_case = group[
            (group["facet"] == "use_case") & (group["variable"] == "use_case_pct")
        ]
        for _, row in use_case.iterrows():
            cluster = row["cluster_name"]
            if pd.notna(cluster) and cluster not in ("not_classified", "none"):
                record[f"usecase_{cluster}"] = row["value"] / 100.0

        # Task success rate
        task_success = group[
            (group["facet"] == "task_success")
            & (group["variable"] == "task_success_pct")
        ]
        for _, row in task_success.iterrows():
            cluster = row["cluster_name"]
            if cluster == "yes":
                record["task_success_rate"] = row["value"] / 100.0

        # Human education years (mean)
        education = group[
            (group["facet"] == "human_education_years")
            & (group["variable"] == "human_education_years_mean")
        ]
        if len(education) > 0:
            record["education_years_mean"] = education["value"].iloc[0]

        records.append(record)

    result = pd.DataFrame(records)
    logger.info("Extracted metrics for %d countries", len(result))
    return result


# ---------------------------------------------------------------------------
# Agency composite
# ---------------------------------------------------------------------------


def _min_max_normalize(series: pd.Series) -> pd.Series:
    """Min-max normalize a Series to [0, 1]."""
    smin = series.min()
    smax = series.max()
    if smax == smin:
        return pd.Series(0.5, index=series.index)
    return (series - smin) / (smax - smin)


def compute_agency_composite(df: pd.DataFrame) -> pd.DataFrame:
    """Compute the agency composite score for each country.

    The composite is the mean of up to four min-max normalized components:
    1. Co-creation proportion (task iteration + learning + validation)
    2. Directive proportion (INVERTED -- higher = lower agency)
    3. Task success rate
    4. Prompt education level (human_education_years_mean)

    Components that are missing from the release are excluded from the
    average (the composite uses however many components are available).

    Args:
        df: Country metrics DataFrame from extract_country_metrics().

    Returns:
        DataFrame with added columns: co_creation, agency_composite,
        and the individual normalized components.
    """
    result = df.copy()

    # Co-creation = sum of task iteration, learning, validation proportions
    co_creation_cols = [
        f"collab_{c}" for c in CO_CREATION_CLUSTERS if f"collab_{c}" in result.columns
    ]
    if co_creation_cols:
        result["co_creation"] = result[co_creation_cols].sum(axis=1)
    else:
        result["co_creation"] = np.nan

    # Build list of available components
    components: list[str] = []

    # 1. Co-creation (normalized)
    if "co_creation" in result.columns and result["co_creation"].notna().any():
        result["norm_co_creation"] = _min_max_normalize(
            result["co_creation"].fillna(0)
        )
        components.append("norm_co_creation")

    # 2. Directive (inverted -- higher directive = lower agency)
    if "collab_directive" in result.columns:
        result["norm_directive_inv"] = 1.0 - _min_max_normalize(
            result["collab_directive"].fillna(0)
        )
        components.append("norm_directive_inv")

    # 3. Task success rate
    if "task_success_rate" in result.columns and result["task_success_rate"].notna().any():
        result["norm_task_success"] = _min_max_normalize(
            result["task_success_rate"].fillna(0)
        )
        components.append("norm_task_success")

    # 4. Education level
    if (
        "education_years_mean" in result.columns
        and result["education_years_mean"].notna().any()
    ):
        result["norm_education"] = _min_max_normalize(
            result["education_years_mean"].fillna(0)
        )
        components.append("norm_education")

    if not components:
        result["agency_composite"] = np.nan
        logger.warning("No agency components available")
        return result

    result["agency_composite"] = result[components].mean(axis=1)
    logger.info(
        "Computed agency composite from %d components: %s",
        len(components),
        components,
    )
    return result


# ---------------------------------------------------------------------------
# Access score (per-capita, log-transformed)
# ---------------------------------------------------------------------------


def compute_access_score(
    df: pd.DataFrame,
    population: pd.DataFrame,
) -> pd.DataFrame:
    """Compute the access score (log per-capita usage).

    Args:
        df: Country metrics DataFrame with usage_count.
        population: DataFrame with columns: iso2, population.

    Returns:
        DataFrame with added columns: population, usage_per_capita,
        access_score.
    """
    result = df.merge(
        population[["iso2", "population"]],
        left_on="geo_id",
        right_on="iso2",
        how="left",
    )
    if "iso2" in result.columns:
        result = result.drop(columns=["iso2"])

    result["usage_per_capita"] = result["usage_count"] / result["population"]

    # Log-transform (add small epsilon to avoid log(0))
    result["access_score"] = result["usage_per_capita"].apply(
        lambda x: math.log10(x + 1e-12) if pd.notna(x) and x > 0 else np.nan
    )

    logger.info(
        "Computed access scores: %d with valid scores",
        result["access_score"].notna().sum(),
    )
    return result


# ---------------------------------------------------------------------------
# Stage assignment
# ---------------------------------------------------------------------------


def assign_stages(df: pd.DataFrame) -> pd.DataFrame:
    """Assign AI Matrix stages using the paper's sequential threshold rules.

    Rules applied in order:
    1. coursework share > 30% → Stage 1 (Full Dependency)
    2. work share > 48% AND coursework < 25% → Stage 2 (Elite Empowerment)
    3. personal share > 38% → Stage 3 (Passive Dependency)
    4. Residual: agency >= 0.55 → Stage 2; agency >= 0.42 → Stage 3; else Stage 1

    If use_case data is not available, falls back to agency-only assignment
    using the residual cutpoints.

    Args:
        df: DataFrame with agency_composite and optionally usecase_* columns.

    Returns:
        DataFrame with added columns: stage (int), stage_name (str),
        stage_rule (str describing which rule triggered).
    """
    result = df.copy()
    result["stage"] = np.nan
    result["stage_rule"] = ""

    has_usecase = (
        "usecase_coursework" in result.columns
        and result["usecase_coursework"].notna().any()
    )

    for idx in result.index:
        if pd.isna(result.loc[idx, "agency_composite"]):
            continue

        if has_usecase:
            coursework = result.loc[idx].get("usecase_coursework", 0) or 0
            work = result.loc[idx].get("usecase_work", 0) or 0
            personal = result.loc[idx].get("usecase_personal", 0) or 0

            # Rule 1: Coursework-dominated
            if coursework > COURSEWORK_STAGE1_THRESHOLD:
                result.loc[idx, "stage"] = 1
                result.loc[idx, "stage_rule"] = (
                    f"coursework={coursework:.0%} > {COURSEWORK_STAGE1_THRESHOLD:.0%}"
                )
                continue

            # Rule 2: Work-dominated
            if work > WORK_STAGE2_THRESHOLD and coursework < COURSEWORK_STAGE2_MAX:
                result.loc[idx, "stage"] = 2
                result.loc[idx, "stage_rule"] = (
                    f"work={work:.0%} > {WORK_STAGE2_THRESHOLD:.0%} "
                    f"& coursework={coursework:.0%} < {COURSEWORK_STAGE2_MAX:.0%}"
                )
                continue

            # Rule 3: Personal-dominated
            if personal > PERSONAL_STAGE3_THRESHOLD:
                result.loc[idx, "stage"] = 3
                result.loc[idx, "stage_rule"] = (
                    f"personal={personal:.0%} > {PERSONAL_STAGE3_THRESHOLD:.0%}"
                )
                continue

        # Rule 4: Residual -- classify by agency composite score
        agency = result.loc[idx, "agency_composite"]
        if agency >= AGENCY_STAGE2_CUTPOINT:
            result.loc[idx, "stage"] = 2
            result.loc[idx, "stage_rule"] = (
                f"residual: agency={agency:.3f} >= {AGENCY_STAGE2_CUTPOINT}"
            )
        elif agency >= AGENCY_STAGE3_CUTPOINT:
            result.loc[idx, "stage"] = 3
            result.loc[idx, "stage_rule"] = (
                f"residual: agency={agency:.3f} >= {AGENCY_STAGE3_CUTPOINT}"
            )
        else:
            result.loc[idx, "stage"] = 1
            result.loc[idx, "stage_rule"] = (
                f"residual: agency={agency:.3f} < {AGENCY_STAGE3_CUTPOINT}"
            )

    result["stage"] = result["stage"].astype("Int64")
    result["stage_name"] = result["stage"].map(STAGE_NAMES)

    logger.info(
        "Stage distribution: %s",
        result["stage_name"].value_counts().to_dict(),
    )
    return result


# ---------------------------------------------------------------------------
# ISO code mapping
# ---------------------------------------------------------------------------


def map_iso2_to_iso3(df: pd.DataFrame) -> pd.DataFrame:
    """Add ISO-3 codes and country names from ISO-2 geo_id.

    Args:
        df: DataFrame with geo_id column containing ISO-2 codes.

    Returns:
        DataFrame with added columns: iso3, country_name.
    """
    import pycountry

    iso3_map = {}
    name_map = {}
    for c in pycountry.countries:
        iso3_map[c.alpha_2] = c.alpha_3
        name_map[c.alpha_2] = c.name

    result = df.copy()
    result["iso3"] = result["geo_id"].map(iso3_map)
    result["country_name"] = result["geo_id"].map(name_map)

    unmapped = result[result["iso3"].isna()]["geo_id"].unique()
    if len(unmapped) > 0:
        logger.warning("Unmapped ISO-2 codes: %s", list(unmapped))

    return result


# ---------------------------------------------------------------------------
# Population data from World Bank API
# ---------------------------------------------------------------------------


def fetch_world_bank_population(year: int = 2023) -> pd.DataFrame:
    """Fetch country population data from the World Bank API.

    Args:
        year: The year for population data.

    Returns:
        DataFrame with columns: iso2, iso3, country_name, population.
    """
    import requests

    url = (
        f"https://api.worldbank.org/v2/country/all/indicator/SP.POP.TOTL"
        f"?format=json&per_page=400&date={year}"
    )

    all_records = []
    page = 1
    while True:
        resp = requests.get(f"{url}&page={page}", timeout=30)
        resp.raise_for_status()
        data = resp.json()

        if len(data) < 2 or not data[1]:
            break

        for record in data[1]:
            if record["value"] is not None:
                all_records.append(
                    {
                        "iso2": record["country"]["id"],
                        "country_name": record["country"]["value"],
                        "population": record["value"],
                    }
                )

        total_pages = data[0].get("pages", 1)
        if page >= total_pages:
            break
        page += 1

    result = pd.DataFrame(all_records)
    logger.info(
        "Fetched population data for %d countries (year=%d)", len(result), year
    )
    return result


# ---------------------------------------------------------------------------
# Full pipeline: raw CSV → scored countries
# ---------------------------------------------------------------------------


def process_release(
    raw_df: pd.DataFrame,
    population: pd.DataFrame,
    release_id: str,
) -> pd.DataFrame:
    """Run the full methodology pipeline on a single AEI release.

    Args:
        raw_df: Raw AEI CSV loaded as a DataFrame.
        population: Population DataFrame from fetch_world_bank_population().
        release_id: Identifier for the release (e.g., "2026_01_15").

    Returns:
        DataFrame with one row per country containing all scores and stage
        assignments.
    """
    # Extract wide-format metrics
    metrics = extract_country_metrics(raw_df)

    # Filter by minimum observations
    metrics = metrics[metrics["usage_count"] >= MIN_OBSERVATIONS].copy()
    logger.info(
        "After MIN_OBSERVATIONS filter (%d): %d countries",
        MIN_OBSERVATIONS,
        len(metrics),
    )

    # Add ISO-3 codes and names
    metrics = map_iso2_to_iso3(metrics)

    # Compute agency composite
    metrics = compute_agency_composite(metrics)

    # Compute access score
    metrics = compute_access_score(metrics, population)

    # Assign stages
    metrics = assign_stages(metrics)

    # Add release metadata
    metrics["release_id"] = release_id

    return metrics
