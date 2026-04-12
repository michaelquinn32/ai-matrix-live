---
description: AI Matrix Live — auto-updating global AI adoption dashboard
globs:
  - "**/*"
alwaysApply: true
---

# AI Matrix Live

Public dashboard tracking global AI adoption using the AI Matrix framework from
[Simpson (2025)](https://doi.org/10.2139/ssrn.5228571). Plots countries on two
dimensions — access (how broadly AI reaches the population) and agency (how
productively they engage) — placing each in one of four quadrants: Full
Empowerment, Elite Empowerment, Passive Dependency, Full Dependency.

Data source: Anthropic Economic Index (AEI) on HuggingFace
(`Anthropic/EconomicIndex`), released roughly quarterly. Pipeline detects new
releases, applies the paper's methodology, outputs static JSON consumed by a
Cloudflare Pages site. Deploys automatically on push to `main`.

## Commands

- Install deps: `uv sync`
- Run pipeline: `uv run python pipeline/run.py`
- Run notebooks: `uv run marimo edit <notebook.py>`
- Serve site locally: `uv run python -m http.server 8000 --directory docs`

## STOP List

- Do NOT use frameworks or build tools for the website — plain HTML, CSS, JS only
- Do NOT hardcode AEI release folder names — detect dynamically from HuggingFace
- Do NOT commit to `main` without permission — this repo auto-deploys via Cloudflare Pages
- Do NOT install Python packages globally — use `uv`
- Do NOT use Jupyter notebooks — use marimo (`*.py` notebooks) for all interactive work
- Do NOT modify the methodology (thresholds, composite formula) without discussion — these replicate a published paper

## Verification

1. Pipeline produces valid JSON: `python -c "import json; json.load(open('docs/data/countries.json')); json.load(open('docs/data/waves.json'))"`
2. Site loads without errors: serve locally, check browser console
3. All countries have required fields: `name`, `iso3`, `stage`, `access`, `agency`
