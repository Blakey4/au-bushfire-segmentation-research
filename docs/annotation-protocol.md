# Annotation Protocol — Australian Bushfire Boundary Dataset

**Version:** 2.1 (aligned with the production scripts)
**Last updated:** 2026-10-11
**Owner:** Oliver Revis
**Repo:** `au-bushfire-segmentation-research`

This document is the single source of truth for how the dataset is built. It was
rewritten from scratch after the Georges Yard pilot (2026-08-24/25); every decision
below was either validated in that pilot or follows structurally from it. v2.1 brings
the registry, download and composite sections in line with `download_scenes.py` /
`make_indices.py` as built in Sept–Oct (§14). Revise via the changelog after the
fire-#3 retro (§13).

> **Proposed, not yet adopted:** a stated label definition, a blind audit subset,
> and a `seed` field recording each polygon's starting geometry — see
> [`research-direction.md`](research-direction.md). Fold into this protocol once agreed.

---

## 0. Core design decisions (the short version)

1. **Vector polygons over whole fire scenes; rasterise and tile as build steps.**
   Labels are georeferenced geometry, independent of pixel grid, patch size, band
   choice, and resolution. Nothing downstream can force re-annotation.
2. **Final extent first, progression later.** Every fire gets its post-fire final
   extent annotated before any fire gets during-fire dates. Final extents are the
   TRM deliverable; progressions are Honours enrichment on a subset.
3. **Two structural constraints replace hand care.** During-fire polygons are built
   as `Union(previous_date, corrected_SAM) ∩ final_extent` — monotonic growth and
   no-overshoot are enforced by geoprocessing, not vigilance.
4. **One bbox per fire, fixed across all dates**, in the scene's native UTM CRS.
   Every date lands on the identical pixel grid; unions, dNBR, and tiling align
   with zero resampling.
5. **Geo-SAM (SAM2.1 Base) box prompt is the first-pass tool** (~50–80% correct in
   pilot), corrected with Stream Digitizing + Reshape Features. dNBR seeds are the
   fallback where SAM fails. GeoOSAM was tested and rejected (§11).
6. **The registry is three files** (§2): human judgements in `fires_master.csv`,
   drawn bboxes in `aoi.gpkg`, machine-written scene provenance in `scenes.csv`.
   Scripts read the registry; humans never retype coordinates or scene IDs.

Target scale: **25–50 fires with final extents; progression time-series on the
3–8 fires with the best usable-date coverage.**

---

## 1. Repository layout

```
au-bushfire-segmentation-research/
├── registry/                     # TRACKED — catalogue and state (small, textual)
│   ├── fires_master.csv          # one row per fire: verification, priority, IDs
│   ├── aoi.gpkg                  # one rectangle per fire_code + scouted dates
│   ├── scenes.csv                # auto-appended by download_scenes.py; provenance
│   ├── season_counts.csv         # HBB feature counts per season
│   ├── split_by_season.py        # HBB V4 gdb → one GeoPackage per season
│   ├── supplement_from_live_service.py  # add live-service-only HBB records
│   ├── *.gdb/                    # GITIGNORED — national HBB geodatabases (V3, V4)
│   └── seasons/                  # GITIGNORED — per-season HBB GeoPackages
├── data/                         # GITIGNORED — bulk and irreplaceable data
│   ├── fires/<fire_id>/          #   downloaded stacks + all derived rasters for
│   │                             #   that fire (re-downloadable / regenerable)
│   ├── annotations/<fire_id>.gpkg#   THE WORK — backed up outside git (§12)
│   ├── build/                    #   ML-ready tiles (regenerable)
│   │   ├── images/  masks/  manifest.csv
│   └── raw/ · derived/           #   Georges Yard pilot only (pre-v2.1 layout)
├── qgis/
│   ├── _template.qgz             # tracked — Save-As per fire (NOT YET CREATED)
│   ├── scouting.qgz              # aoi drawing + candidate review
│   └── <fire_id>.qgz             # gitignored — machine-specific
├── styles/                       # TRACKED — .qml styles (§5.2)
├── scripts/                      # TRACKED — the reproducible pipeline
│   ├── _registry.py              # read-only aoi.gpkg ↔ fires_master.csv join
│   ├── download_scenes.py        # STAC → 10-band GeoTIFF stack + scenes.csv row
│   ├── make_indices.py           # NBR/NBR2/dNBR, highlight composites, dNBR seeds
│   ├── make_extra_views.py       # RBR, BAIS2 (extra review rasters)
│   ├── make_styles.py            # writes styles/*.qml (QGIS python)
│   ├── new_fire.py               # scaffold annotation gpkg + project (to write)
│   ├── qa_checks.py              # monotonicity + validity (to write)
│   └── build_patches.py          # rasterise + tile + manifest (to write)
└── docs/
    ├── annotation-protocol.md    # this file
    ├── status.md · log.md · background.md · research-direction.md
    ├── data-source-survey.md · meeting-notes/ · ai-sessions/
    └── images/                   # cropped screenshots for docs (compress first)
```

Principle: everything under `data/` is either re-downloadable or regenerable by a
script — except `annotations/`, which is the sole irreplaceable artefact and gets
its own backup ritual (§12). `registry/`, `scripts/`, `styles/`, `docs/` are the
reproducible deliverable: a stranger cloning the repo gets no data but can rebuild
the entire pipeline.

Naming: `fire_id` is stable kebab-case with a season prefix (`1920-gospers-mountain`,
`1920-kangaroo-island-menzies-duncan-ravine-complex`), assigned once in
`fires_master.csv` and used verbatim as the folder name under `data/fires/` and
`data/annotations/`. `fire_code` (`1920-03`) is the short key used in `aoi.gpkg` and as
the scripts' `--fire` argument. Rasters: `data/fires/<fire_id>/<YYYY-MM-DD>_<role>.tif`,
role ∈ `pre | during | final`; the fire_id is also stored in each file's `FIRE_ID` tag.

---

## 2. The registry

### 2.1 `fires_master.csv` — human judgements and status

The verified wildfire catalogue: 162 candidates across 2015–16 to 2025–26 (from 207;
45 dropped with documented reasons). Current columns:

| Group | Columns |
|---|---|
| Identity | `season`, `fire_name`, `state_area`, `fire_id`, `fire_code`, `fire_complex_id` |
| Timing / size | `ignition_start`, `finish_status`, `ignition_time_verified`, `end_time_type`, `rough_size` |
| Verification | `verified`, `verification_tier`, `verification_note`, `authoritative_source`, `authoritative_perimeter_available`, `chatgpt_notes` |
| Data availability | `s2_checked`, `s2_usable_dates`, `linescan_available` |
| Selection | `priority` (high / medium / low), `exclude_reason` |

- `fire_complex_id`: complexes annotate as one unit under one ID, and can never
  straddle a train/test split.
- **Planned, not yet added:** per-fire annotation status (`final_extent_done`,
  `progression_done`, `qa_done`) and `time_spent_min` (running total per fire —
  feasibility and annotation-cost data). Add when annotation at scale starts.

### 2.2 `aoi.gpkg` — bboxes and scouted dates

Layer `aoi`, EPSG:4326, one rectangle per `fire_code`, drawn in `scouting.qgz` over
imagery — never typed as coordinates. Sized to the **final extent + ~5 km buffer**. For
complexes, one rectangle around the merged final footprint.

Fields: `fire_code`, `prefire_date`, `postfire_date`, `during_dates` (list),
`bbox_drawn`, `dates_scouted`, `notes`. The **chosen dates live here** (not in
`fires_master.csv`); `scripts/_registry.py` joins them to `fire_id` via
`fires_master.csv` and validates them (season window, ordering) before any download:

```python
# inside scripts/ (the scripts import it as a sibling module)
from _registry import load_fires
fires = load_fires()   # dict keyed by fire_code; each Fire has .fire_id, .geometry, .dates
```

`during_dates` accepts several dates separated by `;`, `,` or spaces.

### 2.3 `scenes.csv` — machine-written provenance

`download_scenes.py` **appends** one row per written file and never overwrites
existing rows, so human-edited columns survive re-runs.

Auto columns: `fire_id, date, scene_id, tile, cloud_cover_tile, scl_cloud_pct_aoi,
boa_offset_applied, file, downloaded_at, role`. Multi-tile mosaics record
`;`-joined values per tile.
Human columns: `usable` (y/n), `notes`.

`scl_cloud_pct_aoi` is computed from the downloaded SCL band (classes 3, 8, 9, 10
as a fraction of the AOI) and is far more truthful than tile-level cloud cover.
**Caveat:** SCL counts dense smoke as cloud, so this number is reliable for
post-fire scenes and *overcounts* on during-fire dates — during-fire usability is
confirmed by eye, not by threshold (§4.2).

### 2.4 Historical Bushfire Boundaries (HBB) — reference data

National fire-history polygons (Geoscience Australia / Digital Atlas). Used as the
`burnt_previous` source (§5.3), as the provisional label for zero-shot tests, and as
the reference that the label audit compares own annotations against. **Never treated
as ground truth.**

- `registry/*.gdb/` — bulk national geodatabases (V3 2024, V4 2025); gitignored.
- `registry/split_by_season.py` → `registry/seasons/bushfire_boundaries_<season>.gpkg`
  (gitignored, regenerable). Uses `OGR_ORGANIZE_POLYGONS=SKIP` — without it GDAL/QGIS
  hang on the gdb's multipolygon assembly.
- `registry/supplement_from_live_service.py` — appends records present only in the live
  Digital Atlas FeatureServer (the bulk and live products have diverged; e.g. Gospers
  Mountain and Currowan 2 are missing from bulk). Additive only.
- Known caveats (detail in `data-source-survey.md` §3.4): the *service* version strips
  interior holes; coverage varies by jurisdiction; NT excluded; mixes wildfires and
  prescribed burns; `capt_method` varies (aerial, linescan, satellite interpretation,
  ground) — keep it for stratification.
- **Choosing the records that make up a fire's provisional label is a manual QGIS step.**
  One AOI typically holds agency duplicates of the same burn (RFS/NPWS, NSW/ACT, NSW/VIC;
  ACT splits one fire into ~100 records), other fires burning between the pre and post
  dates, earlier burns and prescribed burns. Ignition dates and `capt_method` are too
  unreliable to filter on automatically. Keep one version per burn, judged against the
  imagery.

---

## 3. One-time setup

- **QGIS 3.40 LTR or newer.** (3.28 cannot load current Geo-SAM — Qt5/Qt6 split.)
- **Geo-SAM plugin** + plugin-managed dependencies. Known trap from pilot: after
  "Install Missing", verify the `geosam` row itself shows Installed, then **fully
  restart QGIS** — the import cache will not pick it up mid-session.
- **Model: SAM2.1 Base.** SAM3 requires Meta/HuggingFace approval; not used.
- **Value Tool plugin** — live pixel readout for threshold tuning.
- **Python venv** (plain pip; no conda needed): `pystac-client rasterio geopandas shapely`.
- **Drawing tablet.** Any cheap small tablet; QGIS treats it as a pointing device.
  Map one pen button to middle-click (pan). Transforms stream digitizing.
- **`_template.qgz`** containing: layer group skeleton (§6.1), the composite styles,
  snapping config (10 px, vertex+segment), Avoid Overlap enabled on the
  annotation layer slot, OpenTopoMap basemap. **Not yet created** — build it from the
  first production fire's project and export the styles to `styles/` at the same time.

---

## 4. Per-fire workflow — Stage A: scouting and triage

Batch this stage: 10–15 fires per session in `scouting.qgz` + Copernicus Browser.

### 4.1 Draw the AOI
Find the fire in Copernicus Browser (SWIR composite), identify the full final
scar, draw the rectangle in `aoi.gpkg` with ~5 km buffer, set `fire_code`, tick
`bbox_drawn`.

### 4.2 Triage dates
Step through the fire's season in Copernicus Browser over the AOI. Record in
`aoi.gpkg`: `postfire_date` (first fully clean post-containment scene),
`prefire_date`, and for progression candidates `during_dates`; tick
`dates_scouted`. Tile-level cloud % lies; judge the AOI by eye. Alternative for the
final scene only: bulk-download candidate dates cheaply and let
`scl_cloud_pct_aoi` rank them. Mark `usable` in `scenes.csv` after download.

Also note the **lag between containment and `postfire_date`**: eucalypt resprouting and
grass recovery make late post-fire images under-show the burn (see
`research-direction.md`). Where the fire includes grassland or the clean post date is
weeks after containment, also scout a **late `during_dates` reference** (as close to
containment as smoke allows) to annotate against — at Orroral, grass scars clear on
4 Feb 2020 had regreened by the 15 Mar post date.

### 4.3 Pre-fire date rule (fixed)
> Nearest clean scene ≤ 30 days before ignition; if none, nearest ≤ 60 days and
> flag in `notes`. Record in `aoi.gpkg`.

### 4.4 UTM zone check
If the AOI crosses a UTM zone boundary, check whether one tile alone covers it
(MGRS tiles overlap; Georges Yard resolved this way). If genuinely two-zone,
`download_scenes.py` reprojects the minority tile into the majority zone's CRS via
WarpedVRT and mosaics — never annotate across two CRSs.

---

## 5. Per-fire workflow — Stage B: data preparation (scripted)

```bash
python scripts/download_scenes.py --dry-run                 # validate + plan every fire
python scripts/download_scenes.py --fire 1920-03            # all scouted dates of one fire
python scripts/download_scenes.py --fire 1920-01,1920-02 [--overwrite] [--out-dir D:/elsewhere]
python scripts/make_indices.py --fire 1920-03 [--seeds] [--seed-threshold 0.27]
# new_fire.py (annotation gpkg + project scaffold) — to write; until then copy the schema by hand
```

`--fire` takes `fire_code`s; omitted = every fire whose dates validate. Dates and roles
come from `aoi.gpkg` — nothing is typed on the command line.

### 5.1 Download specification (`download_scenes.py`)
- Source: **Element 84 Earth Search** STAC (`sentinel-2-l2a` by default,
  `--collection` to change), public, no auth.
- Output: `data/fires/<fire_id>/<YYYY-MM-DD>_<role>.tif` — one uint16 GeoTIFF per date,
  nodata 0, 20 m, the fire's UTM zone, snapped to native Sentinel-2 pixel edges so every
  date of a fire shares one grid (zero resampling between dates).
- **10 bands, fixed order:**

  | # | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
  |---|---|---|---|---|---|---|---|---|---|---|
  | Band | B12 | B11 | B8A | B04 | SCL | B02 | B03 | B05 | B06 | B07 |

  Bands 1–5 are the annotation set (positions unchanged from the 5-band version, so
  styles and `make_indices.py` work on both); bands 6–10 complete the **9 spectral
  bands the FLOGA-trained models take** (B02–B07, B8A, B11, B12). 10 m bands
  (B02/B03/B04) are averaged to 20 m. Older 5-band stacks must be re-downloaded before
  they can feed a model.
- AOIs spanning several MGRS tiles are mosaicked (target-zone tiles first; tiles adding
  no new AOI coverage dropped); minority-zone tiles reprojected. Duplicate products of
  one tile (`_0/_1`): newest processing baseline kept.
- Append the `scenes.csv` row (§2.3), including AOI SCL cloud %.
- **BOA offset:** pixels are stored as delivered. Whether a scene carries the
  baseline ≥ 04.00 +1000 DN offset is **detected from the pixels** (Earth Search STAC
  metadata is not reliable) and written per band as the `BOA_ADD_OFFSET` tag
  (0 or −1000). Anything converting to reflectance — `make_indices.py`, model input
  pipelines — must apply it; mixed-offset pre/post pairs otherwise corrupt dNBR and
  shift model inputs silently.

### 5.2 Composite views (locked set)
Two RGB **styles** on the downloaded stack plus computed rasters from
`make_indices.py`. Identical fixed stretches on every date — never per-scene
auto-stretch, which shifts what "looks burnt".

| Name | Definition | Kind | Job |
|---|---|---|---|
| `atm-pen` | R=B12 G=B11 B=B8A (bands 1/2/3), 0–4000 | style | reads through moderate smoke; the pilot's primary view (was `swir` in v2.0) |
| `swir` | R=B12 G=B8A B=B04 (bands 1/3/4), 0–4000 | style | second view at ambiguous edges (was `swir-alt` in v2.0) |
| `nbr` | (B8A−B12)/(B8A+B12) → `<date>_nbr.tif` | raster, float32 | severity / scar-age judgement |
| `nbr2` | (B11−B12)/(B11+B12) → `<date>_nbr2.tif` | raster, float32 | active-front precision |
| `dnbr` | NBR(pre) − NBR(final) → `dnbr.tif` | raster, float32 | change vs pre-fire; seed source |
| `atm-pen-highlight` / `swir-highlight` | final-date composite, 0–0.4 reflectance, brightness scaled by dNBR → `*-highlight.tif` | raster, uint8 RGB | unchanged ground dimmed, burn at full colour; displays without a style |

`styles/` holds `atm-pen.qml`, `swir.qml` (10-band stack), `nbr.qml`,
`nbr2.qml` and `dnbr.qml`, written by `scripts/make_styles.py` (QGIS python) with the
stretches above: RGB 0–4000 DN; NBR grey −0.5…0.7; NBR2 grey −0.1…0.4; dNBR Inferno −0.1…0.8.
Optional extras from the same script: `agriculture.qml` (stack, B11/B8A/B02) and
`false-colour-ir.qml` (stack, B8A/B04/B03), plus `rbr.qml` (Inferno −0.1…0.6) and
`bais2.qml` (Inferno 0.2…1.2) for the `rbr.tif` / `<date>_bais2.tif` rasters written by
`scripts/make_extra_views.py`. B8 is not in the stacks, so B8A stands in for NIR throughout.
The RGB styles assume offset-free DN (`BOA_ADD_OFFSET` = 0, true of every stack so far).
`swir_pilot-4band.qml` is the pilot's style for the old 4-band stack (on the 10-band stack it
shows atm-pen).

### 5.3 Auto-generated proposal layers (generate before annotating)
- **water** — national hydrology layer (GA Surface Hydrology / DEA WOs), clipped.
  Never drawn by hand.
- **burnt_previous** — Historical Bushfire Boundaries (`registry/seasons/`, §2.4),
  events within 5 years before ignition, unioned, clipped. Hand-correct only where
  visibly wrong. HBB ends at its version cut-off — for recent fires the previous-burn
  layer may be incomplete; note it per fire.
- **cloud proposal** — s2cloudless/OmniCloudMask preferred; SCL acceptable for
  post-fire scenes. Loaded as a *visible, editable proposal*, never auto-applied:
  SCL flags dense smoke as cloud, and the `atm-pen` composite reads through moderate
  smoke, so auto-applying would discard annotatable ground.
- **dNBR seed** — `make_indices.py --seeds` → `data/fires/<fire_id>/dnbr_seed.gpkg`
  (`method='dnbr_seed'`): threshold, remove specks < 2 ha, polygonise. Pixels SCL calls
  water, cloud, cloud shadow or cirrus on either date are never seeded. 0.27 is the
  starting point only; the pilot showed it needs per-fire tuning by eye
  (`--seed-threshold`).

---

## 6. Per-fire workflow — Stage C: annotation

### 6.1 Project setup
Save-As from `_template.qgz` → `qgis/<fire_id>.qgz`. Layer groups:

```
Annotations (the gpkg layer — always on top)
Auto masks (water / prev burns / cloud proposal)
Analysis (dnbr.tif, *-highlight.tif, dnbr_seed.gpkg, <date>_nbr/_nbr2)
Imagery by date (reverse chronological; ≤ 2 visible at once)
Reference (FIRMS hotspots, official boundary, basemap)
```

### 6.2 Annotation schema
Single polygon layer `annotations` in `data/annotations/<fire_id>.gpkg`,
CRS = the fire's UTM zone. Fields (with form defaults / value-map dropdowns):

`fire, date, scene_id, class, confidence(high|medium|low),
method(manual|geosam|dnbr_seed|official|auto), annotator, notes`

Classes: `burnt · burnt_previous · cloud · cloud_shadow · water · smoke_dense · uncertain`

- **`method` is load-bearing:** any scene containing `geosam` geometry is excluded
  from the Step 2 SAM2 evaluation set, or the benchmark is circular.
- **`uncertain` is surface-based:** *you cannot see the ground in the SWIR
  composites* — opaque cloud, obscuring shadow, dense smoke, the active flaming
  front, undecidable fresh-vs-old margins. Not "a cloud mask flagged it".
  These pixels get zero loss weight at build time; forcing them to 0/1 is what
  taught the Sem-1 model that "dark = maybe burnt".
- `confidence` lives on burnt polygons so the include/ignore/drop decision can be
  made at build time with class balance visible.
- `smoke_dense`: one coarse polygon per during-fire date (~a dozen vertices).
  Enables per-scene obscuration stats and clear-vs-smoky evaluation stratification.

### 6.3 Final extent (every fire; do all fires before any progression)
1. Geo-SAM box prompt on the `final` scene — generous margin around the scar
   (a tight box degrades SAM to a blob; pilot-confirmed). Output to a scratch
   layer (Geo-SAM manages its own schema), then copy geometry into `annotations`
   and fill fields, `method='geosam'`.
2. Where SAM underperforms, start from the dNBR seed (`dnbr_seed.gpkg`) instead —
   pick per fire, record which in `notes`.
3. Correct with **Stream Digitizing + Reshape Features** (§6.5).
4. Interior unburnt islands: try a BG point in Geo-SAM first; else **Add Ring**.
5. Speckle: Multipart→Singleparts, select `$area < 20000`, delete as a batch.
6. Cross-check ambiguous edges against `nbr` and `swir`; official final
   boundary as reference where available (import as `method='official'` and
   hand-correct rather than trusting).
7. QA (§7), tick `final_extent_done`, log `time_spent_min`.

### 6.4 Progression (subset of fires; chronological, earliest first)
For each usable during-fire date T:
1. Download date T (`--role during`); SAM box prompt → corrected polygon.
2. **Build the date's polygon structurally:**
   `polygon(T) = Union(polygon(T−1), corrected(T)) ∩ final_extent`
   (Vector → Geoprocessing: Union, then Clip against the final extent.)
   Union guarantees monotonic growth; the clip removes overshoot including most
   smoke-driven hallucination. Date 1 skips the union.
3. Hand-correct only the new frontier. Everything inherited is already exact.
4. Under smoke: inherit the interior for free (smoke cannot un-burn ground);
   push the boundary only where visible; band of genuine ambiguity → `uncertain`;
   `nbr` often reads better than `atm-pen` under smoke; FIRMS/VIIRS hotspots
   (~3 h after the S2 pass) locate the front under the plume.
5. Active flaming front → `uncertain`, not burnt/unburnt.
6. Store **cumulative** extent per date; increments derive via difference.

### 6.5 Correction technique (the "pen tool")
- **Stream Digitizing** on (Shape Digitizing toolbar), tolerance 5–10 px:
  click-drag freehand tracing, no per-vertex clicking.
- **Reshape Features**: stroke crosses the boundary, traces the correction,
  crosses back — works for both adding and removing area.
- Snapping on; Avoid Overlap on for the annotation layer.
- **Simplify (~10 m tolerance) after annotation, on a copy** — stream digitizing
  produces dense vertices.
- No raster brush. Serval exists but raster masks would forfeit the
  resolution-independence the whole design rests on.

---

## 7. QA (run per fire before ticking `qa_done`)

1. **Monotonicity** (progression fires): `area(T+1) ≥ area(T)` and containment
   for every consecutive pair. Violations are label errors or genuine cloud gaps;
   investigate each. This check exists *because* of §6.4's construction.
2. **Geometry validity**: `ST_IsValid` on all features; fix before rasterising —
   rasterize silently corrupts invalid geometry.
3. **Class overlap**: should be clean with Avoid Overlap; residuals resolve by
   the build-time priority order (§8).
4. **Self-agreement**: blind re-annotation of ~5% of scenes ≥ 2 weeks later;
   report IoU with yourself. This is the empirical ceiling on model performance
   and the direct answer to the Sem-1 label-consistency limitation.

---

## 8. Build — `build_patches.py` (vector → ML-ready)

Fully automated; `data/build/` is disposable; never hand-edit outputs.

1. Per fire-date: read the GeoTIFF's transform/shape and rasterise that date's
   polygons onto **that exact grid** (`rasterio.features.rasterize`; never retype
   bounds). Burn in priority order so overlaps resolve deterministically:
   `background < burnt_previous < burnt < water < cloud_shadow < cloud < uncertain`.
2. Derive `label` (burnt = 1) and `ignore` (uncertain/cloud/cloud_shadow → 0
   weight). Water = confident unburnt unless the fire-#3 retro says otherwise.
3. Tile **512 × 512** (≈10.24 km at 20 m; FLOGA-`sen2_20` compatible). Train:
   25–50% overlap; val/test: none. Drop tiles > 90% ignore. Keep a measured
   ratio of all-unburnt negatives (tune at retro).
4. Write `images/`, `masks/`, `manifest.csv`
   (`fire_id, date, tile_origin, split, ignore_frac, burnt_frac`).
5. **Split by fire event and geography — never randomly.** Adjacent tiles are
   near-duplicates; random tile splits leak (the same failure FLOGA's
   `create_dataset.py` random-split behaviour introduces). Hold out whole fires;
   within a huge fire, buffer ≥ 1 patch width between regions.
6. Bi-temporal is first-class: every patch pairs post-fire with its recorded
   pre-fire image. Defer the FLOGA-HDF5 adapter until Step 1 fine-tuning
   consumes it; plain GeoTIFF tiles + manifest until then.

---

## 9. Order of operations across the dataset

1. Scout + triage in batches (§4) until the 25–50 shortlist has AOIs and dates.
2. **Final extents, breadth-first**, highest-priority fires first.
3. **Retro after fire #3** (§13) — revise this document from experience.
4. Continue final extents through the shortlist.
5. Progression, depth-first, on the 3–8 fires with best during-fire coverage.
6. Build, QA aggregate stats, freeze `v0` of the dataset.

Rationale: if time runs out at any point, the dataset is still coherent and
useful — final extents are the TRM deliverable; progressions enrich Honours.

---

## 10. Known pitfalls (all hit during the pilot — do not rediscover)

- Geo-SAM deps: `geosam` package can silently fail to install on the first
  pass; verify row 8, then full QGIS restart.
- QGIS < 3.40 cannot load current Geo-SAM (Qt5/Qt6 `QAction` import error).
- A tight SAM box prompt returns a blob; leave 20–30% margin.
- Tile-level `eo:cloud_cover` is meaningless for a small AOI; use SCL-over-AOI
  or eyes.
- SCL calls dense smoke "cloud"; the `atm-pen` composite reads through moderate
  smoke. Never auto-convert cloud masks to `uncertain`.
- dNBR 0.27 is not a universal threshold; tune per fire against the raster.
- UTM-zone-straddling bboxes: check single-tile coverage before building
  merge/reprojection logic; MGRS overlap often saves you.
- Fixed stretches per style, always; per-scene auto-stretch shifts the visual
  definition of "burnt" between dates.
- Mixed BOA-offset pre/post pairs silently corrupt dNBR — and model inputs. Always
  apply the per-band `BOA_ADD_OFFSET` tag; don't trust STAC metadata for it.
- Earth Search can return duplicate products of one tile per date (`_0/_1`) — the same
  acquisition processed twice. `download_scenes.py` keeps the newest processing
  baseline (least tile cloud as tie-break).
- Opening the national HBB geodatabase directly in QGIS hangs (multipolygon
  assembly) — use the per-season GeoPackages (§2.4).
- SCL's cloud filter (class 9 only, as FLOGA uses) lets snow through (class 11) —
  check post-fire scenes in alpine fires by eye.

## 11. Decisions log (why, briefly)

- **Geo-SAM over GeoOSAM:** GeoOSAM's default Single mode rasterises the bbox
  without inference; Batch mode fragmented badly in test. Plugin left disabled;
  its Detect/text-prompt tab is a candidate for the future automated-labelling
  tier, not for interactive annotation.
- **SAM2.1 Base over SAM3:** SAM3 gated behind Meta approval; SAM3's headline
  gain is text prompting, not box-prompt quality on overhead imagery.
- **Display-stretch tuning for SAM:** tested; negligible effect on this imagery.
  Default `atm-pen` stretch (then called `swir`) is fine as SAM input.
- **Final-extent-first:** TRM deliverable, easiest annotation, and provides the
  clip constraint that makes progression cheap and robust.
- **One bbox per fire:** grid alignment across dates beats saved disk space.
- **10-band download (Oct 2026):** every stack carries the 9 FLOGA spectral bands so any
  fire can feed zero-shot tests and training without re-downloading; bands 1–5 kept in
  place so styles and indices didn't change.
- **Offset detected from pixels, not metadata (Oct 2026):** Earth Search's
  `boa_offset_applied` property proved unreliable.

## 12. Backups

`data/annotations/` is the only irreplaceable artefact. Weekly (and after any
long session): zip to the external drive **and** a cloud folder. Automate or
calendar it; do not rely on memory. Everything else regenerates.

## 13. Retro after fire #3

Annotate three fires end-to-end with this system as written, then revise:
per-fire time model, SAM vs dNBR default per fire size, negative-tile ratio,
water-in-ignore-mask decision, simplify tolerance, anything that fought back.
Resist perfecting the machine before it has touched real work.

## 14. Changelog

| Version | Date | Change |
|---|---|---|
| 2.1 | 2026-10-11 | Aligned with production scripts: `download_scenes.py` (10-band stack, `data/fires/<fire_id>/<date>_<role>.tif`, pixel-based BOA offset tag, multi-tile mosaics), `make_indices.py` (replaces `dnbr_seed.py`; adds highlight composites). Dates now live in `aoi.gpkg` (keyed by `fire_code`); actual `fires_master.csv` columns documented. Composite renames: v2.0 `swir` → `atm-pen`, v2.0 `swir-alt` → `swir`. Added HBB reference data (§2.4), new pitfalls, post-fire lag note. Flagged missing `_template.qgz`, styles and to-write scripts. |
| 2.0 | 2026-08-26 | Full rewrite post-pilot: registry design, final-extent-first, Union∩Clip construction, locked tooling (Geo-SAM/SAM2.1B), five-style set, pitfalls + decisions logs |
| 0.1 | 2026-08-24 | Initial pre-pilot draft (superseded) |
