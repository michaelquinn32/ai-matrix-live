import marimo

__generated_with = "0.23.1"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    mo.md(
        """
        # AI Matrix Methodology Explorer

        Prototyping the AI Matrix methodology against real AEI data from HuggingFace.
        This notebook validates the agency composite, stage assignment, and access
        calculations before extracting them into `pipeline/run.py`.

        **Reference:** Simpson (2025), "Decomposing the Capability Overhang"
        https://doi.org/10.2139/ssrn.5228571
        """
    )
    return (mo,)


@app.cell
def _(mo):
    mo.md("## 1. Download AEI data from HuggingFace")
    return


@app.cell
def _():
    import pandas as pd
    from huggingface_hub import hf_hub_download

    # Download the Jan 2026 release (richest data -- all 4 agency variables)
    jan_path = hf_hub_download(
        "Anthropic/EconomicIndex",
        "release_2026_01_15/data/intermediate/aei_raw_claude_ai_2025-11-13_to_2025-11-20.csv",
        repo_type="dataset",
    )
    raw_jan = pd.read_csv(jan_path)

    # Also download Sep 2025 (only collaboration data -- for fallback testing)
    sep_path = hf_hub_download(
        "Anthropic/EconomicIndex",
        "release_2025_09_15/data/intermediate/aei_raw_claude_ai_2025-08-04_to_2025-08-11.csv",
        repo_type="dataset",
    )
    raw_sep = pd.read_csv(sep_path)

    # And Mar 2026
    mar_path = hf_hub_download(
        "Anthropic/EconomicIndex",
        "release_2026_03_24/data/aei_raw_claude_ai_2026-02-05_to_2026-02-12.csv",
        repo_type="dataset",
    )
    raw_mar = pd.read_csv(mar_path)

    print(f"Jan 2026: {len(raw_jan):,} rows, facets: {sorted(raw_jan['facet'].unique())}")
    print(f"Sep 2025: {len(raw_sep):,} rows, facets: {sorted(raw_sep['facet'].unique())}")
    print(f"Mar 2026: {len(raw_mar):,} rows, facets: {sorted(raw_mar['facet'].unique())}")
    return mar_path, pd, raw_jan, raw_mar, raw_sep, sep_path, jan_path, hf_hub_download


@app.cell
def _(mo):
    mo.md("## 2. Fetch World Bank population data")
    return


@app.cell
def _():
    from pipeline.methodology import fetch_world_bank_population

    population = fetch_world_bank_population(year=2023)
    print(f"Population data: {len(population)} countries")
    population.head()
    return fetch_world_bank_population, population


@app.cell
def _(mo):
    mo.md(
        """
        ## 3. Run full methodology on Jan 2026 release

        This is the primary validation target -- Jan 2026 has all four agency
        composite variables (collaboration, task success, use case, education).
        """
    )
    return


@app.cell
def _(population, raw_jan):
    from pipeline.methodology import process_release

    jan_results = process_release(raw_jan, population, release_id="2026_01_15")
    print(f"Processed {len(jan_results)} countries")
    print(f"\nStage distribution:")
    print(jan_results["stage_name"].value_counts())
    print(f"\nAgency components used:")
    agency_cols = [c for c in jan_results.columns if c.startswith("norm_")]
    print(agency_cols)
    return agency_cols, jan_results, process_release


@app.cell
def _(mo):
    mo.md("## 4. The AI Matrix scatter plot")
    return


@app.cell
def _(jan_results):
    import plotly.express as px

    # Stage colors (Okabe-Ito derived, colorblind-safe)
    stage_colors = {
        "Full Dependency": "#D55E00",
        "Elite Empowerment": "#E69F00",
        "Passive Dependency": "#0072B2",
        "Full Empowerment": "#56B4E9",
    }

    plot_df = jan_results.dropna(subset=["access_score", "agency_composite", "stage_name"])

    fig = px.scatter(
        plot_df,
        x="access_score",
        y="agency_composite",
        color="stage_name",
        color_discrete_map=stage_colors,
        hover_name="country_name",
        hover_data={
            "iso3": True,
            "usage_count": ":,.0f",
            "access_score": ":.3f",
            "agency_composite": ":.3f",
            "stage_rule": True,
            "stage_name": False,
        },
        title="AI Matrix: Global AI Adoption (Jan 2026 Release)",
        labels={
            "access_score": "Access (log per-capita usage)",
            "agency_composite": "Agency (composite score)",
            "stage_name": "Stage",
        },
        category_orders={
            "stage_name": [
                "Full Empowerment",
                "Elite Empowerment",
                "Passive Dependency",
                "Full Dependency",
            ]
        },
    )

    # Add quadrant dividing lines
    median_access = plot_df["access_score"].median()
    median_agency = plot_df["agency_composite"].median()

    fig.add_hline(y=median_agency, line_dash="dash", line_color="gray", opacity=0.5)
    fig.add_vline(x=median_access, line_dash="dash", line_color="gray", opacity=0.5)

    fig.update_layout(
        plot_bgcolor="#0f1014",
        paper_bgcolor="#0f1014",
        font_color="rgba(235,230,220,0.85)",
        width=900,
        height=650,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
        ),
    )

    fig.update_xaxes(gridcolor="rgba(235,230,220,0.1)", zeroline=False)
    fig.update_yaxes(gridcolor="rgba(235,230,220,0.1)", zeroline=False)

    fig
    return fig, median_access, median_agency, plot_df, px, stage_colors


@app.cell
def _(mo):
    mo.md("## 5. Inspect country details and stage assignments")
    return


@app.cell
def _(jan_results, pd):
    # Show top and bottom countries by agency
    display_cols = [
        "country_name", "iso3", "stage_name", "stage_rule",
        "agency_composite", "access_score",
        "co_creation", "collab_directive", "task_success_rate",
        "usecase_coursework", "usecase_work", "usecase_personal",
        "usage_count",
    ]
    available_cols = [c for c in display_cols if c in jan_results.columns]

    scored = jan_results.dropna(subset=["agency_composite"]).sort_values(
        "agency_composite", ascending=False
    )

    with pd.option_context("display.max_rows", None, "display.float_format", "{:.3f}".format):
        print("=== Top 15 by Agency ===")
        print(scored[available_cols].head(15).to_string(index=False))
        print(f"\n=== Bottom 15 by Agency ===")
        print(scored[available_cols].tail(15).to_string(index=False))
    return available_cols, display_cols, scored


@app.cell
def _(mo):
    mo.md(
        """
        ## 6. Test Sep 2025 release (missing variables)

        The Sep 2025 release only has collaboration patterns -- no task success,
        use case shares, or education level. Let's see what happens when we run
        the methodology with reduced data.
        """
    )
    return


@app.cell
def _(population, raw_sep):
    from pipeline.methodology import process_release as _process

    sep_results = _process(raw_sep, population, release_id="2025_09_15")
    print(f"Sep 2025: {len(sep_results)} countries processed")
    print(f"\nStage distribution:")
    print(sep_results["stage_name"].value_counts())
    print(f"\nAgency components available:")
    sep_agency_cols = [c for c in sep_results.columns if c.startswith("norm_")]
    print(sep_agency_cols)
    print(f"\nNote: Only {len(sep_agency_cols)} components vs 4 in Jan 2026")
    print("Stage assignment uses agency-only residual rules (no use_case data)")
    return sep_agency_cols, sep_results, _process


@app.cell
def _(mo):
    mo.md("## 7. Test Mar 2026 release")
    return


@app.cell
def _(population, raw_mar):
    from pipeline.methodology import process_release as _process2

    mar_results = _process2(raw_mar, population, release_id="2026_03_24")
    print(f"Mar 2026: {len(mar_results)} countries processed")
    print(f"\nStage distribution:")
    print(mar_results["stage_name"].value_counts())
    print(f"\nAgency components available:")
    mar_agency_cols = [c for c in mar_results.columns if c.startswith("norm_")]
    print(mar_agency_cols)
    return mar_agency_cols, mar_results, _process2


@app.cell
def _(mo):
    mo.md("## 8. Compare releases: all three on one scatter")
    return


@app.cell
def _(jan_results, mar_results, pd, px, sep_results, stage_colors):
    # Combine all three releases
    all_releases = pd.concat(
        [
            sep_results.assign(release="Sep 2025"),
            jan_results.assign(release="Jan 2026"),
            mar_results.assign(release="Mar 2026"),
        ],
        ignore_index=True,
    )

    multi_plot = all_releases.dropna(
        subset=["access_score", "agency_composite", "stage_name"]
    )

    fig_multi = px.scatter(
        multi_plot,
        x="access_score",
        y="agency_composite",
        color="stage_name",
        color_discrete_map=stage_colors,
        facet_col="release",
        hover_name="country_name",
        hover_data={"iso3": True, "usage_count": ":,.0f"},
        title="AI Matrix Across Releases",
        labels={
            "access_score": "Access",
            "agency_composite": "Agency",
            "stage_name": "Stage",
        },
        category_orders={
            "release": ["Sep 2025", "Jan 2026", "Mar 2026"],
            "stage_name": [
                "Full Empowerment",
                "Elite Empowerment",
                "Passive Dependency",
                "Full Dependency",
            ],
        },
    )

    fig_multi.update_layout(
        plot_bgcolor="#0f1014",
        paper_bgcolor="#0f1014",
        font_color="rgba(235,230,220,0.85)",
        width=1200,
        height=500,
    )
    fig_multi.update_xaxes(gridcolor="rgba(235,230,220,0.1)", zeroline=False)
    fig_multi.update_yaxes(gridcolor="rgba(235,230,220,0.1)", zeroline=False)

    fig_multi
    return all_releases, fig_multi, multi_plot


@app.cell
def _(mo):
    mo.md(
        """
        ## 9. Summary and observations

        ### Variable availability by release

        | Variable | Sep 2025 | Jan 2026 | Mar 2026 |
        |---|---|---|---|
        | Collaboration (co-creation, directive) | Yes | Yes | Yes |
        | Task success rate | **No** | Yes | Yes |
        | Use case shares (coursework/work/personal) | **No** | Yes | Yes |
        | Education level | **No** | Yes | **No** |

        ### Implications for the pipeline

        1. **Sep 2025 uses a 2-component composite** (co-creation + directive only).
           Stage assignment falls through to agency-only residual rules since use_case
           data is absent. This means Sep 2025 stages are less precise.

        2. **Jan 2026 uses the full 4-component composite** -- closest to the paper's
           methodology.

        3. **Mar 2026 uses a 3-component composite** (no education). Stage assignment
           uses the use_case rules, so stages are still meaningful.

        4. **The pipeline should document which components were available for each
           wave** in `waves.json` so the frontend can display this context.

        5. **Minimum observations threshold (200)** seems appropriate -- removes
           noise from tiny countries while keeping ~70+ countries per release.
        """
    )
    return


if __name__ == "__main__":
    app.run()
