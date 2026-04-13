---
description: AI Matrix Live — auto-updating global AI adoption dashboard
globs:
  - "**/*"
alwaysApply: true
---

# AI Matrix Live

Public dashboard tracking global AI adoption using the AI Matrix framework from
[Simpson (2026)](https://doi.org/10.5281/zenodo.18181372). Plots countries on two
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
- `site/src/pages/` — Astro pages (index, explore, framework, methodology)
- `site/src/layouts/` — Shared layout (nav, footer)
- `site/src/styles/` — Global CSS design system

## Writing Prose

This is a public-facing site for policy professionals, researchers, and
journalists. All prose must pass a slop check before committing.

**Kill on sight:**
- Meta-commentary: "This page documents...", "In this section we will..."
- Hallmark AI phrases: delve, navigate, landscape, tapestry, robust, seamless
- Empty hedging: "It is important to note", "It's worth noting"
- Nominalizations: "the utilization of" → "using"
- Corporate filler: "leverage", "paradigm", "transformative"
- Em dashes as parenthetical crutches. Write a full sentence instead.

**Prefer:**
- Complete sentences with strong verbs. Not fragments. Not hedged clauses.
- Short sentences for claims, longer ones for explanation. Vary the rhythm.
- Concrete examples over abstract descriptions ("Kenya sits here" not "countries in this quadrant tend to...")
- Plain verbs: show, use, track, compute. Not illuminate, leverage, facilitate.
- Direct claims when evidence supports them. Hedge only genuine uncertainty.
- Bullets for discrete items. Prose for relationships between ideas.

**Test:** Read it aloud. If it sounds like a press release or a textbook
introduction, rewrite it.

## Verification

1. Pipeline produces valid JSON: `python -c "import json; json.load(open('site/public/data/countries.json')); json.load(open('site/public/data/waves.json'))"`
2. Site builds: `npm run build` (from `site/`) exits cleanly
3. All countries have required fields: `name`, `iso3`, `stage`, `access`, `agency`
