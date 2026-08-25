# Handoff: Bushfire Boundary Detection Research
 
Living status snapshot — edited in place, not appended to. Refresh before each
supervisor meeting or at milestones. For the full history of *how* the project
got here, see `log.md`; this doc only reflects *now*.
 
## Where things stand (last updated: 2026-08-23)
 
Step 0 (FLOGA reproduction) in progress, target completion ~26 Aug 2026.
Project repo and docs structure just set up today. FLOGA v1 dataset download
in progress via a resumable `curl` workaround after repeated browser failures.
 
## What's done
 
- TRM 1A Individual Learning Plan submitted (19 Aug 2026)
- Three-step research plan agreed with Wenjing:
  - **Step 0** — reproduce FLOGA's reported BAM-CD results on the Greek
    dataset, using their pretrained model
  - **Step 1** — fine-tune FLOGA's model on our own 2019 Australian data
  - **Step 2** — replace FLOGA's model with a SOTA segmentation architecture
    (e.g. SAM2) for improved performance
- Repo structure decided: `FLOGA-reproduction` (Step 0 code, external) +
  `au-bushfire-segmenation-research` (docs, Step 1/2 onward)
- `/docs/` scaffold created (this file, log, data-source-survey,
  meeting-notes, ai-sessions)
## What's next
 
- Finish FLOGA v1 dataset download, run `create_dataset.py`
- Complete Step 0 reproduction against the paper's reported BAM-CD numbers
- Begin Step 1 planning: confirm label availability/quality for 2019

## Open questions / blockers
 
- `create_dataset.py` **issue #6** — creates patches with size 0. First script
  in the pipeline, so this blocks everything downstream. Open upstream since
  March 2025, no maintainer response expected (issue creation restricted on
  the repo).

## Key decisions
 
- **FLOGA v1, not v2, for Step 0** — v1 (Dropbox/HDF) matches what the
  published BAM-CD benchmark was trained/evaluated on; v2's Copernicus-
  reprocessed imagery isn't guaranteed comparable. V2's GeoTIFF format may be
  worth revisiting for Step 1/2 georeferencing needs.