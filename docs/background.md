# Project Background

Stable context for anyone (or any assistant) picking up this repo. For current status
and next steps see [`status.md`](status.md).

## Who and what

**Oliver (Ollie) Revis** — UTS Bachelor of Computing Science (Honours), majoring in AI and
Data Analytics. Currently in **32931 Technology Research Methods (TRM)**, Spring 2026 —
the feasibility/preparation subject feeding **31248 Honours Project** in 2027 (semester 1,
plus the preceding summer).

- **Supervisor (TRM):** A/Prof Wenjing Jia (FEIT). Fortnightly-ish, Mondays 13:00–14:00.
  Honours supervision for 2027 not yet formally confirmed.
- **Subject coordinator:** Dr Mingshan Jia.

**Topic:** deep learning for Australian bushfire burnt-area boundary detection from
Sentinel-2, with a long-term trajectory toward fire progression / spread.

## How the plan evolved

| When | Plan |
|---|---|
| 29 Jul | Registered scope: AI-driven wildfire spread estimation; multi-modal fusion as the long-run idea. See [meeting notes](meeting-notes/2026-07-29.md). |
| 10 Aug | Three steps: **0** reproduce FLOGA; **1** fine-tune on 2019 Australian data; **2** replace with SOTA (e.g. SAM2). See [notes](meeting-notes/2026-08-10.md). |
| 7 Sep | Metrics must be interpreted visually; the research gap may be in **data preparation and label quality**, not only model performance. See [notes](meeting-notes/2026-09-07.md). |
| 28 Sep | Step 0 complete. New order: **label viability → zero-shot transfer → Australian dataset + model comparison**. Spread forecasting reined in as PhD-level. See [notes](meeting-notes/2026-09-28.md). |

Earlier framing (TRP proposal): fire *spread* prediction was judged high-risk because of
agency data gating; an Australian ML-ready burnt-area benchmark plus a label-efficiency
study was judged the most feasible and novel route. FLOGA is both the methodological
template and the gap an Australian equivalent would fill.

## Repos

| Repo | Contents |
|---|---|
| `au-bushfire-segmentation-research` (this) | Docs, registry, annotation pipeline, Australian dataset, Step 1/2 modelling |
| `FLOGA-reproduction` (private) | Step 0 — reproduction of FLOGA/BAM-CD; the BAM-CD V1 analysis notebook |
| `temporal-bushfire-segmentation` (public) | 31005 ML A2 — uni- vs bi-temporal U-Net on FLOGA |

## Prior work

- **U-Net fire-boundary segmentation** from Sentinel-2 (Deep Learning & CNNs subject, HD;
  UTS TechFest AI Showcase 2025). Known weakness: inconsistent labels taught the model
  "dark = maybe burnt" — motivates the `uncertain` class and self-agreement QA.
- **TRP literature review and proposal** targeting an Australian ML-ready burnt-area
  benchmark; flagged Sentinel-1 SAR as a possible extra modality.
- **ML A2 (2026)** — bi-temporal vs uni-temporal on FLOGA; Australian test deferred.

## FLOGA — reference

- Sdraka et al. (2024), *FLOGA: A Machine-Learning-Ready Dataset, a Benchmark, and a Novel
  Deep Learning Model for Burnt Area Mapping With Sentinel-2*, IEEE JSTARS 17, 7801–7824.
  DOI 10.1109/JSTARS.2024.3381737. Code: `github.com/Orion-AI-Lab/FLOGA`.
- 326 Greek fire events 2017–2021; pre/post Sentinel-2 + MODIS; labels from the Hellenic
  Fire Service. Label values: `0` unburnt, `1` burnt, `2` burnt in *another* event that
  year (excluded from training/evaluation).
- **V1** (Dropbox HDF5) matches the paper's weights but proved undownloadable.
  **V2** (Hugging Face GeoTIFFs) holds Copernicus-reprocessed pixels carrying the
  baseline-04.00 +1000 BOA offset.
- BAM-CD input: 9 Sentinel-2 20 m bands (B02–B07, B8A, B11, B12), pre + post, clamped at
  10000 and scaled /10000.
- `create_dataset.py` always makes its own random split (ignores `data_split.csv`) — a
  leakage risk; the repo ships no requirements file.

## Related datasets and models (short list)

CaBuAr (California, agency-perimeter labels), Sen2Fire (NSW 2019–20, coarse MODIS labels),
TS-SatFire (US, multi-task), MSR-BACD, HLS Burn Scars / PANGAEA (where a plain U-Net
matched or beat geospatial foundation models at full labels). Full survey:
[`data-source-survey.md`](data-source-survey.md).

## TRM assessment context

| Task | Weight | Due |
|---|---|---|
| 1A Individual Learning Plan | 20% | Submitted 19 Aug |
| 5 cp of external online learning modules | — | Before 1B, by 25 Oct |
| 1B Reflective Portfolio (~3000 words) | 40% | 25 Oct |
| A2 Draft Introduction + Methodology | 40% | 25 Oct |

- **1B needs evidence artefacts** (completed tasks, screenshots, notes) — capture as work
  happens; this log and the meeting notes are part of that.
- **All generative-AI use must be declared with a full appendix of prompts and
  responses** — see [`ai-sessions/`](ai-sessions/README.md). This includes Claude Code.
- Supervisor sign-off required on 1A and 1B.
- Research steps count as project work, not as 1A learning activities.

Planned modules: TRM Compulsory Research Module; The Carpentries *Geospatial Raster and
Vector Data with Python*; EO College *Land in Focus*; Hugging Face CV Course Units 3 and 6
(verify Unit 6 quality); EO College *Echoes in Space* (SAR, later).

## Hardware and environment

Dell laptop (16 GB RAM, RTX 3050 4 GB, Windows, Git Bash); Samsung T7 1 TB SSD; Seagate
2 TB HDD; access to a friend's 16 GB-VRAM PC for training (limited time); Huion tablet for
QGIS tracing. Plain Python venv (3.13); QGIS 3.40 LTR + Geo-SAM (SAM2.1 Base).

## Contacts

- **NSW RFS** — GIPA disclosures R20/599 (linescans) and R21/276; access to R20/599 granted.
  Requests via gipa@rfs.nsw.gov.au citing file numbers.
- **ANU Bushfire Research Centre of Excellence** — Prof Marta Yebra (director; fire severity,
  flammability/OzFuel; group expecting FireSat access). Met at a seminar, Sept 2026.
