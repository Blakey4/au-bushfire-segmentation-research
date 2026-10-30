# Project Status & Next Steps

Living snapshot of **where the project is now and what happens next**, edited in place
(not appended to). Refresh before each supervisor meeting and at milestones.
History lives in [`log.md`](log.md); meeting records in [`meeting-notes/`](meeting-notes/);
project context in [`background.md`](background.md); the longer-term plan in
[`research-direction.md`](research-direction.md).

*(Replaces the former `handoff.md`.)*

**Last updated:** 2026-10-17 · **Next supervisor meeting:** Mon 2026-10-12, 13:00

---

## Where things stand

- **Step 0 (FLOGA reproduction) — complete** (results discussed with Wenjing 2026-09-28).
  Lives in the separate `FLOGA-reproduction` repo. Key findings, in brief:
  - Released BAM-CD V1 checkpoint evaluated on FLOGA **V2 GeoTIFFs** (V1 HDF5 was
    undownloadable), official `data_split.csv` test split, 67 events.
  - Pooled burnt IoU **91.0** on the benchmark patch protocol; removing ESA's +1000
    BOA offset from the V2 pixels raises it to **93.9** — the V1/V2 mismatch is largely
    a fixable radiometric offset.
  - The headline number is dominated by four large fires and patches lying wholly
    inside a burn. Real errors: low-severity / grassland / agricultural burns,
    wildland-urban interface, plus **label errors** (unlabelled scars, coarse
    perimeters) and a snow-covered post image that passes the SCL-9-only cloud filter.
  - Best on forest, worst near urban areas, grassland and agricultural land.
- **Supervisor's revised priorities (2026-09-28)**, replacing the original Step 1/2 wording:
  1. Verify viability of the Historical Bushfire Boundaries (HBB) labels — mixed
     capture methods (ground, photo-interpretation, aerial, linescan).
  2. Zero-shot test the FLOGA model on a range of Australian fires.
  3. If labels are good enough: build a sizeable Australian label set and train/compare
     models (FLOGA/BAM-CD, CaBuAr-style models, SAM, a geospatial foundation model).
  4. (Own addition) Get familiar with other datasets/models in FLOGA's format.
  The **generalisation analysis + the dataset** are seen as the main contributions.
  Spread forecasting is long-term only (Wenjing: probably PhD-level).
- **Australian data pipeline:** registry + download/index scripts working.
  - Catalogue: 162 verified candidate fires in `registry/fires_master.csv`
    (169 rows in `registry/aoi.gpkg`, 23 AOIs drawn).
  - `scripts/download_scenes.py` writes 10-band 20 m stacks (incl. the 9 spectral bands
    FLOGA models take) with per-band BOA-offset detection; `scripts/make_indices.py`
    writes NBR/NBR2/dNBR, highlight composites and optional dNBR seeds.
  - **12 fires of 10-band imagery now in `data/fires/`** (moved from the ML A2 repo
    2026-10-11; old 5-band stacks set aside in `data/_superseded_5band_2026-10-11/`).
    All 12 have pre + final (Waroona final moved to 2016-03-03). The 2324-02 "Glens
    Creek Road" AOI actually covers the Barton St, Scone fire — being redrawn.
    See `log.md` 2026-10-11.
  - Annotated: Georges Yard pilot only (old pilot layout, `data/annotations/georges_yard.gpkg`).
- **HBB reference data:** national V4 (2025) geodatabase split per season
  (`registry/split_by_season.py`) and supplemented from the live Digital Atlas service
  (`registry/supplement_from_live_service.py`) — the two products have diverged and
  each lacks records the other has (e.g. Gospers Mountain, Currowan 2 missing from bulk).
- **RFS linescans:** access granted to GIPA R20/599 (e.g. 438 images for Gospers
  Mountain alone). Files are flattened JPGs with no georeferencing and no recoverable
  spectral bands — georeferenced originals/world files must be requested from RFS.
- **ML A2 (31005), submitted ~1 Oct** (`temporal-bushfire-segmentation` repo):
  uni- vs bi-temporal U-Net on FLOGA. The Australian zero-shot test was dropped for time
  (agency polygons too inconsistent, preprocessing too large) — it's now next step 1 here.

## Next steps

Immediate, in order. **Target before the 12 Oct meeting: 1 done, start on 2.**

1. **Zero-shot FLOGA on 18 Australian fires.** The step-by-step plan is in
   [`zeroshot-plan.md`](zeroshot-plan.md).
   - ~~Move the full-band imagery in from the other repo~~ (done 2026-10-11). Remaining:
     redraw the 2324-02 AOI.
   - Choose the HBB records that form each fire's provisional label **manually in QGIS**
     (protocol §2.4). The candidates (metadata-only suggestions) are ready in
     `qgis/zeroshot_labels.qgz`. Decide how other in-window fires are labelled (FLOGA
     uses class 2 = burnt in another event, ignored).
   - For own annotation of grassland / long fires, add a late during-fire reference date
     (protocol §4.2).
   - Run BAM-CD (and the A2 U-Nets if useful) zero-shot, with HBB polygons as the
     provisional label.
   - Harmonise reflectance to the convention the model was trained on (the offset
     finding above) before inference.
   - Report per event and stratified (land cover, HBB `capt_method`, fire size),
     not pooled; include a dNBR + Otsu baseline.
2. **Analyse results, then annotate a few of the same fires myself** and compare
   my labels, HBB/RFS perimeters and model output. Annotate those fires *before*
   loading the official polygon, so the comparison isn't anchored on it.
3. **TRM A2 — draft Introduction + Methodology** (due 25 Oct; discuss scope with
   Wenjing on 12 Oct).
4. **TRM learning modules (5 cp)** — barely started; must be done before 1B (25 Oct).
   Run alongside 1–3.
5. **Retrain / fine-tune FLOGA models on Australian data** — first on national
   extent (HBB) labels, then on own labels as the dataset grows. Build the dataset
   (final extents first, per [`annotation-protocol.md`](annotation-protocol.md)).
6. **Honours 2027** — continue the dataset + generalisation work; see
   [`research-direction.md`](research-direction.md).

## Deadlines

| What | Due |
|---|---|
| Supervisor meeting | Mon 12 Oct, 13:00 |
| TRM 1B Reflective Portfolio (~3000 words, needs evidence artefacts + supervisor sign-off) | 25 Oct |
| TRM A2 Draft Introduction + Methodology | 25 Oct |
| TRM 5 cp online modules | before 1B, by 25 Oct |
| French final exam | 2–20 Nov exam period |

## Open questions / blockers

- Which HBB `capt_method` values do the first 10 fires cover? Determines whether the
  zero-shot results can be stratified by label source yet.
- Georeferenced linescans: need to request originals / world files from RFS before
  they're usable for validation.
- Missing tooling referenced by the protocol: `styles/` holds only `swir.qml` (old
  5-band band order) — the other styles and `qgis/_template.qgz` need exporting from
  QGIS. `new_fire.py`, `qa_checks.py`, `build_patches.py` not yet written.
- Honours supervisor for 2027 not yet formally confirmed (Wenjing supervises TRM).
- Licensing of anything derived from the GIPA linescans — assume not redistributable
  until RFS confirms.

## Key decisions (current)

- **FLOGA V2 GeoTIFFs, not V1, for Step 0** — reversed from the 23 Aug plan after V1
  proved undownloadable; mismatch documented and largely explained by the BOA offset.
- **Annotations are vector polygons over whole fires, final extent first**; progression
  is enrichment on a subset. See `annotation-protocol.md`.
- **Splits by fire event and geography, never random.** The 2025–26 Victorian season is
  held out untouched (note: HBB v2/V4 has no labels past its cut-off, so the holdout needs
  its own label source).
- **Download all FLOGA bands at download time** (10-band stack) so every fire can feed
  the models without re-downloading.
- `method` on every annotation polygon; SAM- or model-seeded geometry is excluded from any
  evaluation set involving that model.
