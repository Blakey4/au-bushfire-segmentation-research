# Research Log
 
Dated, append-only. A few bullets every time you sit down to work — not polished,
just enough to reconstruct what happened and why later. Newest entries at the top.
Copy the "new entry" block below each session, even a short one.
 
---
 
## 2026-08-25 — Annotation pipeline pilot: SAM testing, composite selection, workflow lock-in

- Upgraded to QGIS 3.40 LTR; Geo-SAM installed cleanly
- Geo-SAM dependency install (torch/torchvision/ultralytics/geosam, plugin-managed, isolated runtime) — initial run left `geosam` package itself uninstalled silently; required explicit "Install Missing" + **full QGIS restart** (not just dialog close) before `geosam` import resolved. Root cause = Python import cache, not a real install failure
- Downloaded SAM2.1 Base checkpoint
- First real segmentation test: box prompt on postfire scar — good result, followed jagged real boundary closely; two issues: (1) missed a real interior unburnt island, (2) minor vectorization noise/speckle at scar edges in Pixel-Level mode
- **Result: SAM (Geo-SAM) box prompt ≈ 50–80% correct first pass — best of the three methods tested, clearly worth using as first-pass tool**
- Tested whether display stretch (min/max/gamma) affects SAM output — since SAM ingests the rendered 8-bit image, this is a real effect in principle, but tested narrow-vs-wide stretch and default vs current — negligible practical difference on this fire
- Composite exploration — tested several band combos as annotation aids (not just for SAM):
  - Primary SWIR (B12/B11/B8A) — current default, kept
  - Alt SWIR (B12/B8A/B4) — kept as cross-check
  - NBR (B8A,B12) — kept, severity view
  - **NBR2 (B11,B12)** — good specifically at active fire front, weaker in bulk interior — kept as a fire-front precision tool
  - Bi-temporal dNBR fusion script (pre/post in one image) — couldn't get working via Copernicus Browser's multi-datasource UI (datasource alias mismatch, PRE/POST not recognized); **deprioritized** — already covered locally via existing `dnbr_seed.py` script instead, no need for browser-side version
  - Tested BAI, true colour, false-colour IR — not adopted, marginal value over existing set
- **Final composite set locked in**: `swir` (primary), `swir-alt`, `nbr`, `nbr2`, `dnbr` — all derivable from one band download (B04/B8A/B11/B12/SCL), each a `.qml` style on the same raster
- Tested GeoOSAM as a second SAM implementation — installed cleanly, but:
  - SAM3 unavailable without Meta/HuggingFace approval — abandoned, stuck with SAM2.1 family for direct comparison
  - Default "Single" mode does **not** run detection — it rasterizes the drawn bbox directly into a polygon (explains "no segmentation happening" symptom)
  - "Batch Segmentation" mode (actual detection) tried — poor/fragmented result
  - **Decision: abandoned GeoOSAM, reverting to Geo-SAM only.** Plugin disabled (not uninstalled) in case Detect/text-prompt tab worth revisiting later for Tier 3 (automated labelling at scale)
- Finalized annotation workflow:
  1. `new_fire.py` template → per-fire folder + schema'd GeoPackage + styles
  2. `download_scene.py` → one GeoTIFF/date (B04/B8A/B11/B12/SCL, 20m native)
  3. `dnbr_seed.py` → dNBR raster + seed polygons
  4. Geo-SAM box prompt → raw polygon
  5. **Union with previous date's polygon** (enforces monotonicity structurally, not just via QA check)
  6. Correct via Stream Digitizing + Reshape Features (not raster brush — vector pen-tool equivalent); BG points / Add Ring for interior islands; select-by-area for speckle cleanup
  7. Set attributes (`method='geosam'` critical for later SAM2 eval circularity check), save
  8. Repeat per date
- Locked repo structure: `data/{raw,derived,annotations,build}` all gitignored (annotations backed up separately, not via Git); `scripts/`, `styles/`, `docs/` tracked as the actual reproducible deliverable
- **Outstanding**: still need to finish annotating Georges Yard end-to-end with locked workflow and time it — real per-fire cost estimate still unknown, needed before committing to a fire list for bulk annotation
 
---
 
## 2026-08-24 — Annotation pipeline pilot: setup

- Selected Georges Yard as pilot fire (smallest in dataset, 6 old patches) to test new annotation workflow end-to-end before committing to bulk annotation
- Pulled bbox + dates from `TechFest_Patches.csv`: prefire 2019-11-21, postfire 2019-12-21
- Set up Python env (venv, not conda — `pystac-client` + `rasterio` sufficient for download/search; conda reserved for FLOGA training env)
- Queried Element 84 Earth Search STAC; confirmed no-auth/no-quota access works
- AOI spans two S2 tiles (55HGB/56HKG) at a UTM zone boundary — but full AOI sits inside 56HKG alone, so simplified to single-tile download rather than cross-zone mosaicking (revisit reprojection/merge logic for larger fires that genuinely straddle zones, e.g. Gospers)
- Wrote `download_scene.py` — pulls B12/B11/B8A/SCL at native 20m, single tile, clipped to bbox, uint16 GeoTIFF
- Downloaded prefire scene successfully; postfire pending
- Loaded into QGIS, confirmed CRS = EPSG:32756 (correct, no reprojection)
- Set up SWIR composite style (R=B12/G=B11/B8=B8A, fixed 0–4000 stretch), saved as reusable `.qml`
- Created `annotations.gpkg` with full schema (fire/date/scene_id/class/confidence/method/annotator/notes) + attribute form defaults/value-maps
- Drew first test polygon manually — confirmed digitizing + attribute form loop works (not saved)
- Ran dNBR seed script (`dnbr_seed.py`) — threshold 0.27 produced weak/inaccurate result on this fire; flagged threshold needs per-fire tuning, not a fixed default
- Attempted Geo-SAM install — **failed**: QGIS 3.28.2 is Qt5-based, plugin expects Qt6 (`QAction` import error). Root cause: plugin repo build targets newer QGIS
- Decision: upgrade to QGIS 3.40 LTR (blocking, carries to next session)
 
---
 
## 2026-08-23
 
- Set up repo structure: `au-bushfire-segmentation-research` (docs + step1/step2,
  ongoing project) kept separate from `FLOGA-reproduction` (Step 0 code, cloned
  from Orion-AI-Lab — not our code, kept out of the project repo's history)
- Decided against FLOGA dataset v2 (Hugging Face, GeoTIFF) for Step 0 — v1
  (Dropbox, HDF) is required to match the published BAM-CD benchmark, since v2's
  imagery was reprocessed by Copernicus after the paper's release and isn't
  guaranteed pixel-identical to what the reported results are based on
---
 
<!--
New entry — copy this block, fill in, paste ABOVE (newest first)
## YYYY-MM-DD
-
-
-->
