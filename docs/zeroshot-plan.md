# Zero-shot plan: FLOGA models on Australian fires

**Goal for Monday's meeting:** BAM-CD run zero-shot on about 18 Australian fires, scored
against HBB provisional labels with a dNBR + Otsu baseline, results per fire.

Written 2026-10-16, updated 2026-10-17. Steps marked **O** are Ollie's and steps marked **C** are Claude's.
Do them in order: each step needs the one before it.

---

## Fires

These are all the fires that already have pre and final 10-band imagery in `data/fires/`.
No more downloads are needed unless D2 or the stretch goal below adds fires.

| code | fire_id | note |
|---|---|---|
| 1516-01 | 1516-waroona-yarloop | new AOI |
| 1516-02 | 1516-pinery | |
| 1819-03 | 1819-nunnett-timbarra-river-complex | |
| 1819-04 | 1819-tingha-plateau | |
| 1819-05 | 1819-gell-river | |
| 1819-07 | 1819-riveaux-road | |
| 1920-01 | 1920-kangaroo-island-menzies-duncan-ravine-complex | |
| 1920-02 | 1920-green-wattle-creek | |
| 1920-07 | 1920-gospers-mountain | |
| 1920-09 | 1920-cudlee-creek | |
| 1920-10 | 1920-keilira | |
| 1920-11 | 1920-mount-barney-double-peak-complex | HBB polygon includes unburnt areas |
| 1920-12 | 1920-sarabah-binna-burra-scenic-rim | |
| 1920-26 | 1920-orroral-valley | already tested |
| 2324-02 | 2324-glens-creek-road | **AOI is actually Barton St, Scone** (see D2) |
| 2324-03 | 2324-bayindeen-rocky-road | |
| 2324-05 | 2324-coolagolite-road | |
| 2425-01 | 2425-west-coast-complex | final image ~40% cloud/shadow |

The four 2025–26 AOIs are the holdout season and are not used.

---

## Steps

### C1: prepare the label candidates — DONE 2026-10-17

- `scripts/hbb_candidates.py` wrote **`data/annotations/hbb_selection.gpkg`** (EPSG:3577).
  It refuses to overwrite; `--append-new` adds new fires only. It has two layers:
  - **`candidates`** (235): every HBB record touching each AOI, clipped to the AOI.
    Records of one agency with the same name and ignition date are dissolved into one.
    - `group` links candidates overlapping ≥50% of the smaller one: versions of one burn,
      or a part of a bigger record.
    - Info fields: `timing` (before pre / spans pre / in window / after final),
      `latest_date` (the latest of ignition / capture / extinguish) and
      `burning_after_final`.
    - `suggested` is **metadata only, with no imagery or dNBR used**:
      - out-of-window records are `drop`.
      - In each group, the latest-dated version is kept and the others are dropped unless
        they lie mostly outside it.
      - The biggest kept candidate and any name-matched ones are `target`; other kept
        candidates are `other`.
  - **`fires`** (18): for you to fill `include`, `post_ok`, `label_quality`, `note`.
- `scripts/make_zeroshot_project.py` (run with QGIS python) wrote
  **`qgis/zeroshot_labels.qgz`**. It contains:
  - candidates styled by role (filled = set by you, dashed = suggestion only)
  - dropdowns for `role` and the `fires` fields
  - final (shown) and pre (hidden) atm-pen stacks per fire
  - **a bookmark per fire**
  - no dNBR layers

### O1: choose the labels in QGIS (weekend, ~5–10 min per fire, ~2–3 h total)

Open `qgis/zeroshot_labels.qgz` and toggle editing on both layers. Then, for each fire:

1. Jump to it from the Spatial Bookmarks panel (Ctrl+B).
2. Set **`role`** on each candidate:
   - **`target`**: the fire's burnt area. Use one candidate per `group`. If agencies
     overlap, pick the one that best matches the image. Several targets are fine if the
     fire is a complex.
   - **`other`**: a different fire whose ignition falls between the pre and final dates,
     so it is visibly burnt but belongs to another event. What happens to these depends
     on D1.
   - **`drop`**: a duplicate version, a burn from before the pre date, or anything
     irrelevant.
   - If the `suggested` value is right, accept it.
3. **Don't edit geometry.** We are testing HBB as it is. If a polygon is clearly wrong,
   say so in `note` and set `label_quality = poor` on the fire.
4. Fill in the fire's row in `fires`: `include`, `post_ok` (cloud, smoke, regreening)
   and `label_quality`.
5. Save edits. Tell Claude when done, or when part-done, since Claude can start on the
   finished fires.

### C2: build the dataset (after O1, ~1 h)

Write `data/build/zeroshot_v0/<fire_id>/` with these files:

- **`pre.tif`, `post.tif`**: the 9 spectral bands in BAM-CD order (B02, B03, B04, B05,
  B06, B07, B8A, B11, B12). `BOA_ADD_OFFSET` is applied, which matches the pre-2022
  convention the V1 checkpoint was trained on. These stay on the fire's 20 m UTM grid,
  with no resampling.
- **`label.tif`**: values are:
  - 0: unburnt
  - 1: burnt (`target`)
  - 2: ignore, which covers `other` per D1, SCL cloud/shadow (3, 8, 9, 10) on either
    date, nodata, and anything outside the AOI
- **`manifest.csv`**: one row per fire with the dates, image lag, area, `capt_method`,
  `label_quality` and pixel counts.

### C3: run the models (~1 h, GPU)

- Adapt `D:/floga_dataset/FLOGA/analysis/fullscene_infer.py` to read these GeoTIFFs and
  run it in the FLOGA venv. It uses the same 256 px tiling and `clamp_scale_10000` input
  as Step 0. For comparison, 67 FLOGA events took 28 min at 0.8 GB VRAM.
- Run the BAM-CD **V1** checkpoint, which is the main run, and also the **V2** checkpoint.
  The A2 U-Nets are optional (D4).
- Write `pred_bamcd_v1.tif` (and the others) in each fire's folder, georeferenced so you
  can overlay them in QGIS.
- Baseline: dNBR + Otsu per fire. Also show fixed dNBR thresholds of 0.1 and 0.27 for
  reference.

### C4: score and summarise (~1–2 h)

- Compute per-fire IoU, F1, precision and recall on the burnt class, with class 2
  ignored. This is scored over the whole AOI, not FLOGA's 1:1 patch sampling (D3).
- Break results down by `capt_method`, fire size, `label_quality` and state. Land cover
  waits for a land-cover layer.
- Make one figure per fire: post image | HBB label | prediction | errors (FP/FN).
- Write a short results page for the meeting, linked from `log.md`.

### O2: review (Mon morning)

- Look through the per-fire figures and pick 2–3 examples for the meeting.
- The main point for Wenjing: **disagreement is between the model and HBB, not the model
  and the truth.** The Orroral test showed HBB takes in unburnt valley grassland and
  misses grass scars that had regreened.

---

## Decisions for Ollie (before or during O1)

| # | Question | Options | Suggested |
|---|---|---|---|
| D1 | How to label other in-window fires | ignore (class 2, FLOGA convention) / burnt / unburnt | **Ignore.** They are real change, so counting them as unburnt would penalise correct detections. |
| D2 | 2324-02 (Barton St imagery) | include as Barton St (add a `fires_master` row and AOI code) / drop for now / redraw to Nymboida (Claude re-downloads, ~10 min) | Drop for now, or include if the HBB record is clean. Fix the AOI later. |
| D3 | Scoring protocol | whole AOI / FLOGA 1:1 patch sampling / both | **Whole AOI** as the main result, plus patch protocol for comparability with Step 0. |
| D4 | Models | BAM-CD V1 only / + V2 / + A2 U-Nets | V1 + V2. Add the U-Nets only if the A2 checkpoints load easily. |
| D5 | Fires with poor HBB (e.g. Mount Barney) | include and flag / exclude | **Include and flag.** Label quality is part of the finding. |

## HBB patterns seen in the 18 AOIs (for filtering the geodatabase automatically later)

- **`capture_date` is almost empty**: in 2015–25 it is 0% filled for QLD/SA/TAS/VIC/WA, 21%
  for NSW and 54% for ACT. "Latest version" can only use the latest of ignition, capture
  and extinguish dates.
  - `extinguish_date` is ~100% filled for NSW/QLD and 65% for TAS, but 0% for
    SA/VIC/WA/ACT.
  - `capt_method` is filled only in SA, WA and NT.
- **Duplicates come from cross-agency and cross-border mapping:**
  - NSW RFS vs NPWS: near-identical (Barton St), or an NPWS piece inside the park
    (Coolagolite).
  - NSW vs ACT vs VIC DEECA around Orroral/Adaminaby, and QPWS vs RFS at Mount Barney.
  - The latest-dated version agreed with the earlier dNBR choice in both Orroral cases.
- **Agencies split fires differently:**
  - ACT stores unnamed pieces with mapping-like dates.
  - TAS splits a complex into many named sub-fires sharing one ignition date (Riveaux,
    West Coast).
  - NPWS keeps pre-merger component fires (Kowmung River in Green Wattle Creek; Thompson
    and Vault Creek in Gospers).
- **Ignition dates can be mapping dates** (ACT Orroral 28 Feb; WA Murray Road 18 Jan vs
  the actual 6 Jan), so a strict ignition ≥ pre filter needs slack.
- **Prescribed burns before the pre date often sit inside the later wildfire** (Waroona,
  West Coast). A date filter removes them cleanly.
- **9 of 18 targets were still burning after the final image date:** Tingha, Gell River,
  Riveaux, Green Wattle Creek, Mount Barney, Barton St, Coolagolite, West Coast, and
  especially **Sarabah/Lamington** (final image 18 Sep 2019, extinguished 18 Jan 2020).
  The HBB extent can include area burnt after the image, which is a label-timing error,
  not a model error.
- **Only 7 of 18 fires are trivial** (a single kept candidate). The rest need a target vs
  other call, and D1 matters most at Gospers, where ~440,000 ha of other in-window fires
  sit inside the AOI.
- **A likely automatic rule:**
  1. Keep records where ignition ≤ final, and either extinguish ≥ pre or
     ignition ≥ pre − 14 d.
  2. Group by ≥50% overlap and keep the latest-dated version per group.
  3. Make `target` the record(s) under the fire's name plus the biggest.

  This is exactly `suggested`. Once O1 is done, compare `role` with `suggested` to measure
  how often the rule is right.

## Stretch: more fires

To get to 30+ fires, Claude could take more catalogue fires and generate their AOI from
the HBB polygon bbox and their dates from an automatic cloud-free S2 search. These would
be written to a separate file, never `aoi.gpkg`. That costs about 1–2 GB of download per
fire plus about 5 min of O1 each. It is only worth doing once the 18 work end to end.
