# CLAUDE.md

Context for Claude (or any assistant) working in this repository.

## Start here

1. **`docs/status.md`** — current state, the immediate next steps, deadlines, blockers.
   Read this first every session; it is kept current.
2. **`docs/annotation-protocol.md`** — authoritative spec for the registry, download,
   composites, annotation and build pipeline. If code and this doc disagree, flag it;
   the doc wins until updated.
3. Others as needed: `docs/background.md` (project context, FLOGA reference, TRM
   assessment), `docs/research-direction.md` (longer-term plan; the "Proposed" parts are
   not yet agreed with the supervisor), `docs/meeting-notes/` (one file per supervisor
   meeting), `docs/log.md` (append-only dated log, newest first),
   `docs/data-source-survey.md`.

## Project

Australian bushfire burnt-area boundary detection from Sentinel-2 — UTS Technology
Research Methods (TRM), supervised by A/Prof Wenjing Jia; continues into Honours 2027.

- **Step 0** — reproduce FLOGA/BAM-CD on the Greek data: **complete** (2026-09-28).
  Lives in the separate private repo `FLOGA-reproduction`, not here.
- **Current priorities (agreed 2026-09-28):** (1) verify viability of Historical Bushfire
  Boundaries (HBB) labels; (2) zero-shot test FLOGA models on Australian fires; (3) if
  labels are good enough, build an Australian label set and train/compare models.
  **This repo.**
- **The dataset, the label analysis and the generalisation analysis are the primary
  contributions**, not model benchmarks.

## Repository layout

```
registry/     fires_master.csv, aoi.gpkg, scenes.csv (catalogue + state; tracked)
              split_by_season.py, supplement_from_live_service.py (HBB tooling)
              *.gdb/, seasons/ — HBB reference data, gitignored, regenerable
data/         GITIGNORED — fires/<fire_id>/ holds downloaded stacks + derived rasters
              (regenerable); build/ regenerable; annotations/ is the only
              irreplaceable folder; raw/ + derived/ are the Georges Yard pilot only
qgis/         scouting.qgz; per-fire .qgz gitignored; _template.qgz not yet created
styles/       .qml styles for stacks and index rasters, from make_styles.py (protocol §5.2)
scripts/      _registry.py, download_scenes.py, make_indices.py (the pipeline);
              make_extra_views.py (RBR, BAIS2), make_styles.py, hbb_candidates.py +
              make_zeroshot_project.py (zero-shot label review)
docs/         status, protocol, background, direction, log, meeting notes, ai-sessions,
              zeroshot-plan; images/proposal/ figures + their scripts
```

**Never write into `data/annotations/`, `registry/aoi.gpkg`, or
`registry/fires_master.csv` programmatically without being asked.** These hold
irreplaceable human work (drawn AOIs, scouted dates, hand annotations, scouting
judgements). Scripts read them; they don't overwrite them. `download_scenes.py` may only
*append* to `registry/scenes.csv`.

## Key conventions

- **`fire_id`** (e.g. `1920-gospers-mountain`) is the permanent key for folders and
  files (`data/fires/<fire_id>/`, `data/annotations/<fire_id>.gpkg`). **`fire_code`**
  (e.g. `1920-03`) keys `aoi.gpkg` and is what the scripts' `--fire` argument takes.
  Both live in `registry/fires_master.csv`; never change either once files exist.
- **CRS is always the fire's native UTM zone** (EPSG:327xx) for any raster or annotation
  data, never EPSG:4326 (only `aoi.gpkg` rectangles are 4326). Every date of a fire sits
  on one snapped 20 m grid — don't introduce resampling.
- **Downloaded stacks:** `data/fires/<fire_id>/<YYYY-MM-DD>_<role>.tif`, 10 bands in fixed
  order `B12, B11, B8A, B04, SCL, B02, B03, B05, B06, B07` (20 m, uint16, nodata 0).
  Bands 1–5 = annotation set; with 6–10 the stack holds the 9 spectral bands FLOGA models
  take (reorder to B02–B07, B8A, B11, B12 for BAM-CD). Stacks downloaded before
  2026-10-01 may be 5-band and need re-downloading before model use.
- **BOA offset:** each band carries a `BOA_ADD_OFFSET` tag (0 or −1000), detected from
  pixels. Always apply it before computing indices or feeding a model; never mix offset
  and non-offset scenes. Step 0 showed the offset alone moves BAM-CD IoU 91.0 → 93.9.
- **Composites:** `atm-pen` = B12/B11/B8A, `swir` = B12/B8A/B04 (styles, fixed 0–4000);
  NBR, NBR2, dNBR and highlight composites are rasters written by `make_indices.py`.
- **Annotations are vector polygons over whole fire scenes**, not raster masks over
  patches. Rasterising and tiling happen only at the build step (`build_patches.py`, to
  write).
- **`method` field on annotations matters:** polygons seeded by a model (`geosam`,
  `dnbr_seed`, or a future trained model) must be excluded from any evaluation of that
  model, or the benchmark is circular.
- **Splits by fire event and geography, never random.** The 2025–26 Victorian season is
  an untouched holdout.
- **Evaluation:** report per event and stratified (land cover, HBB `capt_method`, size),
  never only pooled; include a dNBR + Otsu baseline. HBB polygons are provisional labels,
  not ground truth.

## Working conventions

- Add a dated entry to `docs/log.md` (newest first) after substantive sessions, and
  refresh `docs/status.md` when the state or next steps change.
- TRM requires an appendix of all AI interactions — Claude Code sessions included. See
  `docs/ai-sessions/README.md`.
- Ollie makes the core research and design decisions; lay out options and trade-offs
  rather than deciding for him.

## Environment

Windows, Git Bash. Plain Python venv (`venv/`, not conda) — `pystac-client`, `rasterio`,
`geopandas`, `shapely`, `pandas`, `numpy`. QGIS 3.40 LTR+ with Geo-SAM (SAM2.1 Base).
GPU: RTX 3050 4 GB locally; a 16 GB GPU PC is available for training but time on it is
limited. See `docs/annotation-protocol.md` §3 for setup and install pitfalls.
