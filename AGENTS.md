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

- Install Python deps: `uv sync`
- Install site deps: `npm install` (from `site/`)
- Run pipeline: `uv run python pipeline/run.py`
- Run notebooks: `uv run marimo edit <notebook.py>`
- Dev server: `npm run dev` (from `site/`)
- Build site: `npm run build` (from `site/`, outputs to `site/dist/`)

## STOP List

- Do NOT hardcode AEI release folder names — detect dynamically from HuggingFace
- Do NOT commit to `main` without permission — this repo auto-deploys via Cloudflare Pages
- Do NOT commit without a linked GitHub issue — every commit references an issue number
- Do NOT install Python packages globally — use `uv`
- Do NOT use Jupyter notebooks — use marimo (`*.py` notebooks) for all interactive work
- Do NOT modify the methodology (thresholds, composite formula) without discussion — these replicate a published paper

## Project Structure

- `pipeline/` — Python data pipeline and methodology module
- `notebooks/` — Marimo notebooks for exploration
- `site/` — Astro static site (HTML, CSS, JS)
- `site/public/data/` — JSON output consumed by the site
- `site/src/pages/` — Astro pages (index, framework, methodology, updates)
- `site/src/layouts/` — Shared layout (nav, footer)
- `site/src/styles/` — Global CSS design system

## Verification

1. Pipeline produces valid JSON: `python -c "import json; json.load(open('site/public/data/countries.json')); json.load(open('site/public/data/waves.json'))"`
2. Site builds: `npm run build` (from `site/`) exits cleanly
3. All countries have required fields: `name`, `iso3`, `stage`, `access`, `agency`
