# Research Log
 
Dated, append-only. A few bullets every time you sit down to work — not polished,
just enough to reconstruct what happened and why later. Newest entries at the top.
Copy the "new entry" block below each session, even a short one.
 
---
 
 <!--
New entry — copy this block, fill in, paste ABOVE (newest first)
## YYYY-MM-DD
-
-
-->

## 2026-10-26 — Proposal figures; HBB error examples (Claude Code)
- Figures in `docs/images/proposal/` (scripts in `scripts/` there): Fig 1 Orroral (now shows all neighbouring in-window HBB perimeters), Fig 2 dataset structure (labels from metadata `suggested`, not yet screened; KI Complex shown as part of the KI event), Fig 3 draft of HBB limitations
- **Correction to 2026-10-11:** the Orroral Valley grass floor did burn. On ~1,390 ha of valley floor inside the HBB perimeter, 90% has dNBR > 0.1 on 4 Feb 2020 (median 0.22) vs 19% on the 15 Mar post image (median −0.22). It regreened, so the HBB perimeter was right and the post-date dNBR is wrong there
- Screening for HBB errors (dNBR only as a pointer, then checked by eye): most dNBR-flagged "misses" are cloud or cropland change, not fire. Clear cases: Keilira, ~160 ha burnt outside the perimeter and ~250 ha unchanged paddocks inside it; QPWS Main Range NP, 45 vertices for 2,774 ha. Median vertex spacing is 45 m over all kept records, against 297 m for QPWS and 165 m for NSW PWS (Gospers). Over-inclusion at Gell River, Riveaux Road and Coolagolite can't be separated from burning after the final image (all three were out after it)

## 2026-10-17 — Zero-shot plan; HBB label candidates for 18 fires (Claude Code)
- Downloads finished 2026-10-11/12: Sarabah, Nunnett, Bayindeen, Riveaux Road, West Coast Complex (final ~40% cloud), Gospers Mountain, Waroona (new AOI). 18 fires now have pre + final 10-band stacks
- Plan for a zero-shot BAM-CD test on all 18 (who does what, decisions D1–D5): [`zeroshot-plan.md`](zeroshot-plan.md)
- `scripts/hbb_candidates.py` → `data/annotations/hbb_selection.gpkg` (235 candidates, 18 fires); `scripts/make_zeroshot_project.py` → `qgis/zeroshot_labels.qgz` (bookmark per fire). Suggestions are metadata-only (latest-dated version per overlap group); no dNBR, to avoid biasing the label choice
- HBB patterns: `capture_date` is almost never filled; 9/18 target fires were still burning after the final image (worst: Sarabah, final 18 Sep, out 18 Jan); only 7/18 fires have a single obvious record. Details in zeroshot-plan.md

## 2026-10-11 — Orroral test: HBB version selection vs a blind dNBR annotation (Claude Code)
- HBB records dissolved into agency versions (ACT splits one fire into ~100 records), versions of the same burn grouped by overlap, best kept by IoU vs a dNBR > 0.1 mask: ACT PSC wins 5 of 6 groups (Orroral ACT 0.86 vs NSW PWS 0.81, which has no holes); Adaminaby RFS 0.77 vs VIC DEECA 0.56
- Claude's blind annotation (dNBR hysteresis 0.25/0.10, SCL mask, majority smoothing; no HBB input) vs the selected HBB set: IoU 0.88 over the AOI; ~15,000 ha HBB-only vs ~1,000 ha Claude-only
- Checked disagreements against 4 Feb and 24 Feb 2020 images: the Orroral Valley grassland floor looks unburnt on 4 Feb (HBB perimeter over-includes it); grass-fire scars around Bredbo are clear on 4 Feb but regreened by the 15 Mar post date (the post-date dNBR misses them). **Post-date lag + Feb 2020 rain is a major label-disagreement factor for grassland**
- Outputs (gitignored): `data/fires/1920-orroral-valley/review_hbb_selection.gpkg`, `review_claude_annotation.gpkg`, `review/` PNGs + the scratch scripts that made them
- Decisions: HBB record selection per fire stays a manual QGIS step (protocol §2.4); scout a late during-fire reference date for own annotation of grassland / long fires (protocol §4.2)
- Waroona-Yarloop final re-dated to 2016-03-03 (in `aoi.gpkg` by Ollie) and downloaded — all 12 fires now have pre + final 10-band stacks

## 2026-10-11 — Full-band imagery moved in; first look at HBB records per AOI (Claude Code)
- Moved the 12 fire folders (10-band stacks) from `temporal-bushfire-segmentation/data/au_fires/` into `data/fires/`; the old 5-band `data/fires/` (incl. Sarabah, Deep Creek and derived indices) set aside in `data/_superseded_5band_2026-10-11/` (gitignored, delete when happy). `scenes.csv` paths repointed; superseded rows noted
- `_registry.py` now skips `aoi.gpkg` rows with no `fire_code` — 146 tiny uncoded polygons (look like Cudlee Creek HBB parts pasted in on 2 Oct) were crashing `load_fires()` and so `download_scenes.py`
- Waroona-Yarloop final 2016-02-02 has no S2 pass in Earth Search or Planetary Computer; Jan/Feb passes ~100% cloud over AOI; **2016-03-03 is the only clean candidate** (both tiles, 0% SCL cloud) — awaiting decision before editing `aoi.gpkg`
- **2324-02 "Glens Creek Road" AOI is over the Barton St, Scone fire** (150.9E 32.05S, ~1,230 ha) — the real Glens Creek Rd, Nymboida fire is at 152.73E 29.87S (13,589 ha in HBB)
- HBB records per AOI (season file only): 4 fires are a single clean record (Pinery, Gell River, Keilira, Cudlee Creek); the rest mix agency duplicates of one fire (RFS vs NPWS, NSW vs ACT PSC, RFS vs VIC DEECA — e.g. Orroral NSW PWS vs ACT ≈ 0.92 IoU, Adaminaby RFS vs DEECA ≈ 0.80), separate fires burning between the pre and post dates, fires before the pre date, and prescribed burns. HBB ignition dates are unreliable (Waroona "Murray Road" dated 18 Jan vs actual 6 Jan); `capt_method` mostly null/Unknown outside SA/WA

## 2026-10-11 — Docs reorganised
- Brought repo docs up to date after six weeks of undocumented work (with Claude): `handoff.md` renamed to `status.md` and rewritten (current state + next steps); added `background.md`, `research-direction.md`, `data-source-survey.md`, `ai-sessions/`, and notes for all four supervisor meetings in `meeting-notes/`
- `annotation-protocol.md` → v2.1 to match the current scripts; `CLAUDE.md` refreshed
- Deleted superseded Georges Yard pilot scripts (`download_scene.py`, `dnbr_seed.py`, `search_scenes.py`), the pre-10-band backup of `download_scenes.py`, and a stray shapefile in `registry/`
- Entries dated 2026-08-28 to 2026-10-02 below were **backfilled on 2026-10-11** from file dates, `registry/scenes.csv`, meeting notes and chat history — dates approximate

## 2026-10-02
- `registry/split_by_season.py`: split the national Bushfire Extents Historical V4 (2025) geodatabase into one GeoPackage per fire season (`registry/seasons/`, gitignored). Root cause of the QGIS "crashes" was GDAL's near-quadratic multipolygon assembly on 324k features — fixed with `OGR_ORGANIZE_POLYGONS=SKIP`
- Last scene downloads for now: 14 fires have rows in `registry/scenes.csv`; 23 AOIs drawn in `registry/aoi.gpkg` (169 rows)

## 2026-10-01
- `download_scenes.py` extended from 5 to **10 bands** (adds B02, B03, B05, B06, B07 after the original five) so stacks carry all 9 spectral bands the FLOGA-trained models take; bands 1–5 unchanged so styles and `make_indices.py` still work
- BOA offset now detected from the pixels themselves (Earth Search STAC metadata unreliable) and tagged per band as `BOA_ADD_OFFSET`
- ML A2 (31005, `temporal-bushfire-segmentation`) submitted: uni- vs bi-temporal U-Net on FLOGA. Australian zero-shot test dropped for time — agency polygons too inconsistent and QGIS preprocessing too large → carried over here as the immediate next step

## 2026-09-28 — supervisor meeting
- **Step 0 complete** — presented the BAM-CD V1 analysis (in `FLOGA-reproduction`); see `meeting-notes/2026-09-28.md`
- New priority order from Wenjing: verify HBB label viability → zero-shot FLOGA on Australian fires → if labels OK, build Australian label set and compare models
- RFS granted access to GIPA R20/599 (Black Summer linescans). Later found: flattened JPGs, no georeferencing, no recoverable spectral bands (e.g. 438 images for Gospers Mountain) — need georeferenced originals from RFS
- Met Marta Yebra (ANU Bushfire Research Centre of Excellence) at a recent seminar

## 2026-09-27
- `scripts/_registry.py` (read-only join of `aoi.gpkg` ↔ `fires_master.csv`, date validation) and `scripts/make_indices.py` (NBR, NBR2, dNBR, swir/atm-pen highlight composites, optional dNBR seeds that skip water/cloud) written
- First production downloads via `download_scenes.py` (5-band version), starting with Glens Creek Road

## 2026-09-23
- `registry/supplement_from_live_service.py`: the live Digital Atlas FeatureServer and the bulk V4 download have diverged (311,984 vs 345,345 features), each missing records the other has (e.g. Gospers Mountain, Currowan 2 absent from bulk) — script appends live-only records, never replaces

## 2026-09 — Step 0 in `FLOGA-reproduction`
- FLOGA V1 HDF5 proved undownloadable (expiring Dropbox links, hardware) → switched to V2 GeoTIFFs (Hugging Face); V1 BAM-CD weights + `data_split.csv` used
- BAM-CD V1 on the official test split (67 events): pooled burnt IoU 91.0 on the patch protocol; removing the V2 +1000 BOA offset → 93.9
- Analysis notebook: per-event ranking, land-cover breakdown, boundary-vs-clear errors, label errors (unlabelled scars, coarse perimeters), snow passing the SCL-9 cloud filter

## 2026-09-07 — supervisor meeting
- Partial Step 0 results discussed; Wenjing: check how IoU is computed and inspect overlays; research gap may lie in data preparation / label quality. See `meeting-notes/2026-09-07.md`

## 2026-08-28
- `CLAUDE.md` and `annotation-protocol.md` v2.0 written; `registry/fires_master.csv` built out — 162 verified candidate fires (from 207; 45 dropped with reasons) across 2015–16 to 2025–26, with `fire_id` / `fire_code` / complex IDs, verification tiers and priorities

## 2026-08-26
- Discovered RFS Disclosure Logs R20/599 and R21/276 - May be able to access RFS linescan imagery and burnt area maps for the fires - Need to contact gipa@rfs.nsw.gov.au to enquire
- With help of Chaptgpt compiled a list of around ~162 Fires from 2016 - present to use as candidates for finding usable fires for the dataset
- Identified a range of other models worth adding to my benchmark
- Identified some models worth looking at for a potential benchmark: BAM-CD, BiAU-Net, MSR-BACD, SMoE, DSMNN-Net, CA-BAFormer

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
