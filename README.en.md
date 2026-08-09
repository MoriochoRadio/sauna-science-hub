# 🧖 Sauna Science Hub

🇰🇷 [한국어](README.md) · 🇬🇧 English

**A serverless static archive that automatically collects sauna and heat-therapy research from PubMed every day, translates it into Korean, and grades it by level of evidence.**
GitHub Actions handles the entire collect → translate → build → deploy pipeline, with zero operating cost and zero API keys.

🔗 **Live**: https://moriochoradio.github.io/sauna-science-hub/

**Tech stack**: Python 3 standard library only (`urllib` · `xml.etree` · `json` — zero external dependencies) · PubMed E-utilities · keyless machine translation (cached) · GitHub Actions · GitHub Pages

## What It Shows

- **90-odd sauna and heat-therapy studies** — cardiovascular, mortality, cognition, metabolism, recovery, mental health, pain and inflammation, and more (newest first from PubMed)
- **Evidence-level labels** — RCTs, clinical trials, meta-analyses, and cohort studies labeled tier 1–5 by publication type. ★ marks tier 1 (the strongest evidence)
- **Korean translation + original toggle** — machine-translated Korean and the English abstract side by side, switchable with a button
- **Periodical-style listing** — an editorial layout organized by year and issue; abstracts collapsed by default (click to expand)

## Features

| Feature | Description |
|------|------|
| Search | Live search across titles, abstracts, journals, and authors (query highlighting) |
| Topic filters | Cardiovascular · mortality · cognition · metabolism · respiratory · recovery · mental health · pain · inflammation |
| Evidence filters | RCT / clinical trials / meta-analyses & reviews / observational studies |
| Sorting | Newest · by evidence level · clinical trials first |
| View settings | Original (EN) ↔ Korean, light/dark mode (stored locally) |

## How It Works

```
        ┌──────────── GitHub Actions (daily at 10:17 KST + on push) ────────────┐
        │                                                                        │
  collect.py ──────────► data/research.json ──► build.py ──► index.html ──► Pages deploy
 (PubMed E-utilities      (paper metadata)      (static site   (finished HTML)
  collection + Korean   + translations.json cache  generator)
  translation)
```

1. **`collect.py`** — searches and collects the latest sauna-related research via PubMed E-utilities, assigns evidence tiers from the publication type (PublicationType) and topic categories from title/abstract keywords. Titles and abstracts are machine-translated into Korean, with the `translations.json` cache used first.
2. **`build.py`** — reads `research.json` and generates a finished static `index.html` with search, filters, sorting, and dark mode built in (no browser-side data parsing).
3. **`daily.yml`** — runs the two steps above daily, commits data only when it has changed, and deploys to GitHub Pages. It also redeploys on push.

## Why It's Built This Way — Technical Choices Q&A

**Q. Why a serverless static site?**
A. Server rendering is waste for an archive whose data changes once a day. `build.py` produces finished HTML at build time, so the browser renders it directly with no parsing, and with free hosting (GitHub Pages) the operating cost is zero.

**Q. Why GitHub Actions?**
A. Cron scheduling, manual runs, push triggers, and deployment (Pages) are all handled by a single workflow file, and collected data lands as commits, giving history tracking too. To keep bot commits and local pushes from clashing, a `git pull --rebase --autostash` runs before committing.

**Q. Why PubMed E-utilities as the data source?**
A. PubMed is the right source for the "evidence-based" concept of covering only peer-reviewed research, and E-utilities is an official API that's free to use without a key. Its publication-type metadata (RCT, meta-analysis, cohort, etc.) is also what made automatic evidence-tier (1–5) labeling possible.

**Q. Why keyless machine translation + a cache?**
A. Paid translation APIs were ruled out under the zero-cost principle. Instead, translations are cached in `translations.json`, so even with daily runs, already-translated papers are never retranslated — avoiding rate limits and cutting run time at once. If a translation fails, the value is left empty and the original text is shown as-is (the site doesn't break).

**Q. Why only the Python standard library?**
A. HTTP requests, XML/JSON parsing, and HTML generation are perfectly doable with `urllib`, `xml.etree`, and `json`. With zero dependencies there's no install step in CI, and locally it runs with nothing but Python — fewer breakable parts in a pipeline that runs every day.

**Q. Why include evidence-level labeling?**
A. With health information, credibility varies enormously with study design, so distinguishing tiers from RCTs and meta-analyses (tier 1) down to observational and cross-sectional studies (tier 4 and below) is what makes it a true "evidence-based archive". Tier assignment maps PubMed's own publication types directly, ruling out arbitrary judgment.

## Running Locally

> All you need is Python 3. No external libraries to install.

```bash
python3 scripts/collect.py   # PubMed collection + Korean translation (requires internet)
python3 scripts/build.py     # Generate index.html
# Open the generated index.html in a browser
```

- You can also skip collection and run only `build.py` against the existing `data/research.json`.
- To refresh immediately: GitHub **Actions tab → Sauna Science Hub — Daily Update → Run workflow**

## File Structure

```
sauna-science-hub/
├─ .github/workflows/daily.yml   # Daily automated collection · build · deploy
├─ scripts/
│  ├─ collect.py                 # PubMed collection + evidence/topic classification + Korean translation (cached)
│  └─ build.py                   # Static site generator
├─ data/
│  ├─ research.json              # Collected paper metadata
│  └─ translations.json          # Translation cache
├─ index.html                    # Build output (auto-generated)
└─ README.md
```

## Lessons Learned

- **Taming external dependencies with a cache** — accumulating translations in a file cache, and migrating the translations already in `research.json` into that cache, lets the pipeline run reliably every day while staying under the free API's rate limit. Cache writes go through a temp file + `os.replace` so they're atomic, preventing file corruption on mid-write failures.
- **Ship a partial result rather than nothing on failure** — when some translations or collections fail, the pipeline falls back to showing the original text instead of dying on an exception, so the automation deploys something every day rather than being "perfect or halted".
- **Push contention in a repo where a bot commits** — in a repo mixing scheduled bot commits with development pushes, `git pull --rebase --autostash` right before committing is essential.

## Disclaimer

For educational and informational purposes; not a substitute for medical advice. Depending on your health,
consult a physician before using a sauna. Translation quality is for reference only — check the original paper (PubMed link) for exact details.
