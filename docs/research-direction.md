# Research Direction

Where the project is heading beyond the immediate next steps in [`status.md`](status.md).

> **Status of this document:** the "Agreed" section reflects the 28 Sep meeting with
> Wenjing. Everything under "Proposed" is Ollie's working proposal, **not yet agreed** —
> raise it with Wenjing before treating it as a decision.

## Agreed (28 Sep 2026)

Priority order: label viability → zero-shot transfer of FLOGA models → (if labels are good
enough) an Australian label set + training and comparing several model families. The
**generalisation analysis and the dataset** are the main contributions. Spread forecasting
stays long-term.

## Proposed framing

> Reliable burnt-area labels for Australia: how agency records differ from what the
> imagery shows, how well existing models transfer, and how cheaply good labels can be made.

Three mutually supporting contributions:

1. **The dataset** — photo-interpreted final extents for 25–50 fires, provenance and
   per-polygon confidence/uncertainty, event-level splits, progression polygons on a subset.
2. **The label audit** — HBB (and FESM where it exists) quantified against own labels,
   stratified by `capt_method`, biome and severity. Answers priority 1 directly; possibly
   publishable on its own.
3. **Transfer + label efficiency** — zero-shot FLOGA-, CaBuAr- and foundation-model
   performance on Australian fires, then performance vs number of annotated Australian
   fires. `time_spent_min` makes annotation cost (minutes per 1,000 ha) reportable.

Spread prediction becomes explicit future work enabled by the progression polygons.

## Proposed method decisions (pending Wenjing)

- **State the label definition:** own labels mean *visible burn at 20 m*. Understorey fire
  under an intact canopy is often not visible; where HBB/FESM-low-severity say burnt and
  imagery doesn't, that disagreement is a computed result, not an error to hide.
  `uncertain` / low confidence carry the ambiguous band.
- **Blind audit subset (~8–12 fires, stratified by `capt_method`):** annotate without the
  official polygon loaded; import HBB only afterwards. Record the starting seed
  (`geosam` / `dnbr_seed` / `official` / model) as its own field so anchoring can be analysed.
- **Independent validation:** a second annotator on 3–5 fires; georeferenced linescans
  (GIPA R20/599) on the fires they cover — the only reference independent of Sentinel-2.
- **Stratified fire selection:** choose the 25–50 by size, biome (forest / woodland /
  grassland / agricultural), state and capture method — not by prominence. FLOGA's median
  event is ~50 ha; mid-size grass and agricultural fires are where transfer will break.
- **Radiometric harmonisation before any zero-shot run:** convert inputs to the convention
  the model was trained on (Step 0: offset removal moved IoU 91.0 → 93.9). The catalogue
  spans the 2022 processing-baseline change.
- **Post-fire image timing:** eucalypt epicormic resprouting and grass recovery degrade a
  late single post-fire image; record image lag per fire and use during-fire dates where
  available on long-running fires. *Orroral test (Oct 2026): a blind dNBR delineation
  agreed with HBB at IoU 0.88, but missed grass-fire scars that had regreened within
  ~7 weeks, while HBB's perimeter took in unburnt valley grassland. Grassland is where
  both label sources fail, in opposite directions.*
- **Evaluation:** per event and stratified, never only pooled; always include dNBR + Otsu
  as a baseline.
- **Model comparison — one representative per family:** BAM-CD; a plain early-fusion
  U-Net (from ML A2); one geospatial foundation model (e.g. Prithvi-EO via TerraTorch);
  one SAM2-based pipeline. PANGAEA found a plain U-Net matched or beat GFMs at full
  labels; GFMs help most with few labels.
- **CaBuAr as a second source domain:** agency-perimeter labels (like HBB) vs FLOGA's
  expert labels — a natural experiment on how label style affects transfer.
- **Model-in-the-loop labelling** after ~8–10 fires: train, propose polygons for new
  fires, correct, log time saved. Test fires must be annotated *without* model proposals;
  record model-seeded geometry in `method`.

## Known label-source caveats

- **HBB (Digital Atlas service)** removes interior holes ("donut" polygons) — unburnt
  islands become burnt. Check whether the bulk geodatabase keeps them before use.
- HBB v2 covers early 1900s–2023, **excludes the NT**, mixes wildfires and prescribed
  burns, and coverage varies by jurisdiction. Bulk V4 and the live service have diverged.
- No HBB labels for the 2025–26 holdout season — it needs a separate label source, which
  confounds "time" with "label source" unless controlled.
- Some recent NSW polygons may themselves derive from Sentinel-2 / FESM (a random forest on
  Sentinel-2) — agreement with them is partly circular.
- FESM accuracy is high for unburnt and crown scorch/consumption, notably lower for
  low-severity classes; grass fires are mapped "extent only".

## Parked (after Honours, or only if time allows)

SAR fusion, Himawari sub-daily progression, multi-modal spread modelling, building around
FireSat (50 m imagery with 5 m fire detection; early-adopter data from late 2026, no
archive), MSR-BACD as a headline model.

## Rough sequence

| Period | Focus |
|---|---|
| To 25 Oct | Zero-shot on ~10 fires; first own annotations vs HBB; TRM A2 + 1B + modules |
| Nov–Dec | Annotate toward 25 final extents; freeze dataset v0; second annotator |
| Summer | Model-in-the-loop labelling; label-efficiency experiments; linescan validation; toward 50 fires + progression on 3–8 |
| Honours S1 | Model-family comparison, write-up, dataset + code release; audit possibly as an earlier standalone paper |
