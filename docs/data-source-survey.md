# Wildfire Data Source & Dataset Survey

*Feasibility scoping for AI-driven wildfire spread estimation (32931 TRM)*
Oliver Revis · prepared for discussion with A/Prof Wenjing Jia · first written 22 Aug 2026

> **Repo copy, updated 2026-10-11.** Copied from the project-knowledge version (marked
> "not fully complete"). Changes from that version are tagged **[Oct 2026]**; image
> placeholders were removed. This is an initial scan — always assume there are sources
> not yet found.

# 1. Imagery Sources

Roughly ordered by resolution.

## 1.1 At a glance

| Source | Type | Resolution | Revisit | Access / Cost |
| :---- | :---- | :---- | :---- | :---- |
| Planet PlanetScope | Optical (commercial) | 3 m | Daily | Free via Education & Research Program (limited) |
| Sentinel-2 | Optical (10 band) | 10–60 m | 5 days (2 sats) | Free |
| Landsat 8/9 | Optical + thermal | 30 m (100 m thermal) | ~8 days combined | Free |
| HLS (Harmonized L/S2) | Optical, co-registered | 30 m | ~2–3 days | Free (NASA) |
| Sentinel-1 | SAR (C-band) | 10–20 m | 6 days (nominal) | Free |
| Sentinel-3 OLCI/SLSTR | Optical + thermal | 300 m–1 km | ~1–2 days | Free |
| VIIRS | Thermal (active fire) | 375 m / 750 m | Several passes/day | Free (NASA FIRMS) |
| MODIS (Terra/Aqua) | Thermal (active fire) | 1 km | 1–2 days | Free, being retired 2027 |
| Himawari-8/9 AHI | Geostationary optical + thermal | 500 m–2 km | 10 min (2.5 min sectored) | Free |
| DEA Hotspots | Aggregated thermal | Varies by source | ~20 min pipeline latency | Free, CC BY 4.0 |
| Aerial linescan (NSW RFS / Vic DEECA) | Airborne IR/multispectral | 5–15 m | Ad hoc per incident | Agency-held, not public |
| FireSat (from Q4 2026) | Purpose-built IR constellation | **~50 m ground sampling; detects fires as small as 5×5 m** **[Oct 2026: corrected — previously listed as 5 m resolution]** | Twice-daily, then 20 min by 2030s | Early Adopter Program only, not yet public |

## 1.2 Tier A: realistic candidates

### Sentinel-2 (A/B/C)

This is the workhorse of almost all burnt-area segmentation work, including FLOGA. It has 13 spectral bands: 10 m for visible/NIR, 20 m for red-edge/SWIR, and 60 m for the atmospheric bands, with a 290 km swath. With two satellites running we get a 5-day revisit. Sentinel-2C joined the constellation in 2024 and is gradually replacing 2A.

* The SWIR bands (B11/B12) are what actually make burn scars visible spectrally. This is the basis of NBR/dNBR and most burnt-area indices.
* It's free and open through the Copernicus Data Space Ecosystem, AWS, Google Earth Engine, and Digital Earth Australia.
* The catch is cloud and smoke block it completely, so it's not usable while a fire is actively producing a lot of smoke.
* **[Oct 2026]** Products processed with baseline ≥ 04.00 (from early 2022, and all reprocessed archive products) carry a +1000 DN BOA offset. Mixing offset and non-offset scenes silently corrupts indices and model inputs — `download_scenes.py` detects and tags it per band.

*Where to find it:* <https://dataspace.copernicus.eu/>

### Landsat 8/9 (+ HLS)

30 m multispectral, 100 m thermal (TIRS), 16-day revisit per satellite, around 8 days combined with both satellites running. The Landsat archive goes back to 1972, which nothing else matches, so it's really the only option if we ever want to look at fires before 2015. Harmonized Landsat Sentinel-2 (HLS) co-registers both onto a common 30 m grid at roughly 2 to 3 day effective revisit. Worth mentioning HLS is what Prithvi-EO (a leading geospatial foundation model) was pretrained on, so it matters if we go down the foundation-model route.

*Where to find it (Landsat):* <https://earthexplorer.usgs.gov/> · *(HLS):* <https://hls.gsfc.nasa.gov/>

### Sentinel-1 (SAR, C-band)

10 to 20 m, free, and it can see through cloud and smoke, which is the main reason it's appealing for during-event mapping or heavily obscured post-fire scenes. The constellation just went through a big transition. Sentinel-1A stopped operating on 30 June 2026 after 12 years, and Sentinel-1C and 1D are now the operating pair, back to the normal 6-day revisit. One thing to flag: there was a degraded period from 2022 to 2024 after Sentinel-1B failed, so any time series covering that window has gaps.

* It picks up changes in backscatter from altered vegetation structure rather than spectral colour, so it's a genuinely different kind of signal to optical imagery.
* L-band sensors like ALOS-2 and NISAR (see Tier B) penetrate canopy better than Sentinel-1's C-band does, but that comes at the cost of easy free access.

*Where to find it:* <https://dataspace.copernicus.eu/>

### Himawari-8/9 AHI (JMA)

This is the key sensor if we want to actually reach sub-daily resolution over Australia. It has 16 bands: 500 m for red, 1 km for green/blue/NIR, and 12 mid-infrared/thermal bands (1.6 to 13.3 μm) at 2 km, imaging the full disk every 10 minutes (2.5 minutes for sectored regions). There's already an established algorithm for this, AHI-FSA (Fire Surveillance Algorithm), which uses the MIR/NIR/RED bands to give 500 m fire-line detections every 10 minutes, and it's been tested specifically on Australian fires including across the Northern Territory.

* The honest limitation is that at 500 m to 2 km this is good for fire-line detection and tracking progression, not pixel-level segmentation like our previous U-Net work.
* No other continent has this cadence paired with an established, validated fire algorithm. I think this is probably our strongest argument for why this should be an Australian project specifically.
* Accessible through BoM, NCI, AWS Open Data and Google Earth Engine. It's also what underlies the Himawari mosaics shown in DEA Hotspots, linked below.

*Where to find it (via DEA Hotspots):* <https://hotspots.dea.ga.gov.au>

### VIIRS / MODIS via NASA FIRMS

VIIRS at 375 m (VNP14IMG, on Suomi-NPP, NOAA-20 and NOAA-21) is currently the best polar-orbiting active-fire product, with several satellites giving multiple passes a day. MODIS at 1 km (Terra/Aqua) has been the historical backbone but it's actually being retired now. NASA plans to stop Terra MODIS data collection in February 2027 and Aqua MODIS in September 2027, and both satellites are already drifting in their orbits. CAMS added VIIRS to its Global Fire Assimilation System from December 2025, marking the start of that transition. If we use a long historical time series, we need to account for this changeover.

*Where to find it:* <https://firms.modaps.eosdis.nasa.gov/>

### DEA Hotspots (Geoscience Australia)

This is the Australian national aggregator, and it genuinely suits this project well. It's updated every 10 minutes and can be viewed online, downloaded, or pulled in as WMS/WFS web services. For any given Australian location a thermal image is captured 4 to 7 times a day, and the pipeline from satellite pass to hotspot map takes about 20 minutes. It overlays Landsat and Himawari-9 mosaics, MODIS burnt areas, population data (NEXIS) and land cover, and it's released under CC BY 4.0. There's both a public site and a restricted secure site for authorised users.

*Where to find it:* <https://hotspots.dea.ga.gov.au>

### Planet (PlanetScope)

This is the realistic commercial option, through the Education and Research Program. Any university-affiliated student, staff member or researcher can apply with a university email for limited non-commercial access to PlanetScope and RapidEye imagery. PlanetScope gives daily 4-band imagery (8-band from 2020) at 3 m resolution, going back to 2014. The free Basic tier gives 3,000 km² a month, with a 30-day delay on the imagery.

* 3,000 km² a month isn't much. A single large fire could use up the whole monthly allocation on its own.
* The 30-day delay rules out anything near real-time, but it doesn't matter if we're just building a historical training set.
* It costs nothing and takes a few minutes to apply, so I think it's worth doing regardless of which direction we end up going.

*Where to find it:* <https://www.planet.com/markets/education-and-research/>

## 1.3 Tier B: considered, lower priority

I looked at these for completeness, but I don't think they'll form the core dataset, mostly because of cost, access barriers, or overlap with something already in Tier A.

| Source | Note | Link |
| :---- | :---- | :---- |
| Sentinel-3 OLCI/SLSTR | 300 m to 1 km, roughly 1 to 2 day revisit, has a dedicated FRP product. Positioned as part of the post-MODIS continuity plan. | [Copernicus](https://dataspace.copernicus.eu/) |
| ASTER | On-demand tasking rather than systematic coverage, so not suitable for time-series work. | [EarthExplorer](https://earthexplorer.usgs.gov/) |
| GOES-R ABI / Meteosat / GK-2A | Geostationary equivalents covering the Americas, Europe/Africa and Korea. Useful for methodology transfer but not for Australia directly. | – |
| ALOS-2 PALSAR-2 / NISAR | L-band SAR with better vegetation-structure sensitivity than Sentinel-1's C-band. NISAR (NASA-ISRO) has a free data policy but is newer with less archive depth. | – |
| RADARSAT Constellation Mission | Has published burnt-area deep learning work using compact-pol SAR. Canadian mission, access conditions vary. | – |
| ICEYE / Capella / TerraSAR-X | Commercial smallsat SAR with sub-daily tasking. Expensive, and I couldn't find a student tier. | – |
| Maxar / Airbus / BlackSky / Satellogic | Commercial high-res optical with no free academic tier that I could find. Noted for completeness only. | – |
| OroraTech FOREST / WildFireSat / LSTM / TRISHNA | Upcoming thermal/fire-focused missions, still pre-operational. Good for framing future work, not usable as data right now. | – |
| Aerial linescan (NSW RFS, Vic DEECA, Air Affairs Australia) | 5 to 15 m IR/multispectral, smoke-penetrating, and honestly the highest-resolution fire-line data available in Australia. Agency property, not publicly downloadable; prior academic use (Storey et al., UOW) came through a direct agency relationship. **[Oct 2026]** Access to NSW RFS GIPA R20/599 (Black Summer linescans) now granted — but the released files are flattened JPGs with no georeferencing and no recoverable spectral bands; georeferenced originals / world files must be requested separately. | – |
| FireSat (Muon Space / Earth Fire Alliance) | First three operational satellites launched July 2026, 6-band multispectral IR, sees through smoke. **[Oct 2026]** ~50 m ground sampling distance at nadir; *detects* fires as small as 5×5 m (sensitivity, not pixel size). Twice-daily data reaches Early Adopters (fire agencies and scientists, incl. NSW RFS) by end 2026, expanding through 2027 toward global access by 2028; 20 min revisit targeted by the early 2030s. No historical archive — not usable for training during Honours, but strong framing for future work. | – |

# 2. Contextual & Auxiliary Layers

These are the non-imagery layers we could encode alongside satellite data, which matters most if we go down the multi-modal route.

## 2.1 Weather & atmospheric

| Layer | Source | Resolution | Frequency | Link |
| :---- | :---- | :---- | :---- | :---- |
| BARRA2 reanalysis | Bureau of Meteorology | 12 km (4.4 km inner grid) | Hourly, 1979–present | [NCI (BARRA2)](https://dx.doi.org/10.25914/1x6g-2v48) |
| BARRA1 subdomains (incl. Eastern NSW) | BoM | 1.5 km convection-permitting | Hourly | – |
| ERA5 | ECMWF / Copernicus | ~28 km (0.25°) | Hourly, 1940–present | [Copernicus CDS](https://cds.climate.copernicus.eu/) |
| ADFD (gridded forecast) | BoM operational | ~6 km | Forecast cadence | – |

BoM says fire agencies already use this reanalysis dataset to better understand bushfires in Australia, and the high-resolution sub-regions support detailed analysis of historic major fires. That makes BARRA2 a credible primary weather source. ADFD is forecast data rather than reanalysis, so it has real forecast error baked in — more realistic for anything deployable (and required to avoid future-state leakage for "time-until" features).

## 2.2 Terrain

| Layer | Resolution | Coverage | Link |
| :---- | :---- | :---- | :---- |
| ELVIS national DEM (LiDAR-derived) | 1 m to 1 second grid, 5 m national bare-earth | Patchy, concentrated on populated coastal zone, Murray-Darling floodplains, population centres (2001–2015 surveys) | [elevation.fsdf.org.au](https://elevation.fsdf.org.au) |
| SRTM 1-second | ~30 m | Complete national coverage | [EarthExplorer](https://earthexplorer.usgs.gov/) |
| Copernicus DEM | 30 m / 90 m | Global | [Copernicus](https://dataspace.copernicus.eu/) |

Derived layers (slope, aspect, curvature, ruggedness) would be computed from the above. Slope especially matters for spread modelling since rate of spread increases roughly exponentially with upslope angle.

## 2.3 Fuel & vegetation

| Layer | Resolution | Notes | Link |
| :---- | :---- | :---- | :---- |
| DEA Fuel Moisture Content | 20 m | Satellite-derived live vegetation moisture, continent-wide, developed with the ANU Bushfire Research Centre of Excellence | [DEA FMC](https://www.ga.gov.au/scientific-topics/dea/dea-data-and-products/dea-fuel-moisture-content) |
| Sentinel-2 LFMC product (2026) | 20 m | First continental operational LFMC from Sentinel-2, Random Forest trained on ~680,000 paired S2/MODIS-LFMC samples | – |
| CSIRO Bushfire Fuel Classification map | Structural, national | 89% accuracy for native forest, 71% for non-forest, combines LiDAR, radar, optical and land use data | [CSIRO Data Access Portal](https://data.csiro.au/collection/csiro:63764) |
| NVIS v6 | 100 m | National vegetation characterisation across 85 major subgroups | – |
| Time-since-fire / fuel accumulation | Derived | Computed from the fire history layers in Section 3, drives fuel-accumulation curves in AFDRS | – |
| Grass curing | Weekly | Feeds AFDRS, matters a lot for grassland fires specifically | – |

## 2.4 Fire danger indices

| Layer | Resolution | Notes | Link |
| :---- | :---- | :---- | :---- |
| AFDRS Fire Behaviour Index | 1.5 km, hourly | Replaced McArthur FFDI nationally in 2022. Outputs rate of spread, fireline intensity, flame height and spotting distance per fuel type. Historical climatology hourly Jan 2000 – Feb 2019 at 1.5 km — usable as an input or a baseline to beat. | [afdrs.com.au](https://www.afdrs.com.au) |
| Wind Change Danger Index | 1.5 km grid | Largest when there's both a rapid direction change and a strong synoptic change. Wind changes turn a flank into a front — worth encoding explicitly. | [afdrs.com.au](https://www.afdrs.com.au) |
| McArthur FFDI (historical) | Point/grid | Superseded by AFDRS in 2022 but common in older literature. | [background](https://en.wikipedia.org/wiki/McArthur_Forest_Fire_Danger_Index) |

## 2.5 Less obvious layers, possibly high value

* **PyroCb occurrence.** Rick McRae's public Australian pyroCb register. PyroCb events are where spread models break down (fire-generated weather, long-range spotting). Encoding pyroconvection at time t could let a model learn when to distrust its own extrapolation — an uncertainty-quantification angle. [register](https://www.highfirerisk.com.au/pyrocb/register.htm)
* **Lightning strikes** (GPATS / WWLLN). GPATS distinguishes cloud-to-ground strikes but is commercial (a reviewer flagged reproducibility); WWLLN is free with lower detection efficiency.
* **Smoke and aerosol as signal** (Sentinel-5P TROPOMI, OMPS Aerosol Index). Sen2Fire tried a simple version; not yet explored properly. [Copernicus (Sentinel-5P)](https://dataspace.copernicus.eu/)
* **Weather radar.** BoM radar observes plumes directly (echo tops ~12 km at Dargo, ~10 km at Beechworth on Black Saturday) — sub-10-minute intensity proxy that works at night and through smoke. Almost unused in ML.
* **Soil moisture** (AWRA-L / Australian Water Outlook) — drives fuel availability at monthly–seasonal scale; already feeds AFDRS.
* **Human and infrastructure layers** — roads, power-line easements, building footprints, ABS mesh-block population. Ignition sources and a suppression confound. [OpenStreetMap](https://www.openstreetmap.org)
* **Land use and tenure (ALUM v8)** — affects fuel management and suppression priority.
* **Prescribed burn history** — separate from wildfire history; relevant for mitigation effects.
* **Canopy height and vertical structure** (Scarth et al., Lang et al.) — proxy for canopy bulk density and crown-fire potential.

**The encoding problem this creates:** these layers sit at wildly different resolutions and update rates (Sentinel-2 10 m; DEA FMC 20 m weekly; NVIS 100 m static; AFDRS 1.5 km hourly; BARRA2 12 km hourly; Himawari 0.5–2 km every 10 min; lightning/hotspots as irregular point processes). Stacking them as raster channels on one grid and timestep throws away most of what makes each useful — the heterogeneity problem Wenjing flagged as a genuine long-run research question.

# 3. Existing Datasets & Label Sources

## 3.1 Closest existing work

### Sen2Fire (Xu, Berg & Haglund, IGARSS 2024, 4-page conference paper)

* Australian and high-resolution: 2,466 patches at 512×512, 13 bands (12-band Sentinel-2 L2A plus a Sentinel-5P UV aerosol index channel at ~1 km). Four NSW regions from the 2019–20 season, over 30,000 km².
* Binary wildfire detection only.
* Key weakness is the labels: MOD14A1 V6.1 (1 km MODIS active fire), a 50–100× resolution mismatch with the imagery, and active fire rather than burnt extent. One season; 2.5–5.8% fire pixels.
* The aerosol channel (smoke as signal) is interesting but lightly explored.

*Paper:* <https://arxiv.org/abs/2403.17884>

### TS-SatFire (Zhao, Gerard & Ban, KTH, Scientific Data, 2025)

* Peer-reviewed; same group as WildfireSpreadTS.
* Contiguous US, Jan 2017 – Oct 2021: 3,552 VIIRS images at 375 m plus weather, topography, land cover and fuel; 71 GB.
* Three tasks: active fire detection, daily burned-area mapping, next-day progression. Labels from FIRMS and NIFC with manual QA on the test set.
* Essentially the multi-task vision Wenjing described — built for the US, not Australia.

*Paper:* <https://www.nature.com/articles/s41597-025-06271-3>

|  | Sen2Fire | TS-SatFire |
| :---- | :---- | :---- |
| Venue | IGARSS conference (4pp) | Scientific Data (Nature) |
| Region | NSW, Australia | Contiguous US |
| Imagery | Sentinel-2, 10–20 m | VIIRS, 375 m |
| Labels | MODIS 1 km active fire | FIRMS/NIFC + manual test QA |
| Tasks | Detection only | Detection + daily BA + progression |
| Multi-modal | S2 + aerosol | Weather, topo, land cover, fuel |

**The gap this leaves:** neither sits at the intersection of high-resolution Australian imagery, good labels and multiple tasks. A defensible framing: neither existing benchmark addresses high-resolution Australian burnt-area delineation using the 10 m operational products available here (e.g. FESM). That is narrower — and stronger — than claiming no Australian benchmark exists. **[Oct 2026]** Prior Australian test areas do exist in single-model papers (e.g. BiAU-Net's Bredbo test area; Burnt-Net's two Australian forest sites), so the claim should be *systematic, stratified* evaluation across many events and label sources, not "first on Australia".

## 3.2 ML-ready burnt-area segmentation datasets

| Dataset | Region | Key facts | Link |
| :---- | :---- | :---- | :---- |
| FLOGA (Sdraka et al. 2024) | Greece | 326 events 2017–2021, bi-temporal Sentinel-2 + MODIS, expert-annotated by the Hellenic Fire Service. The design gold standard here. | [GitHub](https://github.com/Orion-AI-Lab/FLOGA) |
| MSR-BACD (Liu et al. 2026) | Global | 1.4M dual-temporal Sentinel-2 pairs including negative samples, built for generalisation. | [DOI](https://doi.org/10.1016/j.rse.2025.115137) |
| CaBuAr | California | Pre/post Sentinel-2; masks rasterised from CAL FIRE perimeters (agency-perimeter labels, like HBB). HDF5, one entry per scene, 5-fold CV splits. Useful second domain for cross-region testing. | [Hugging Face](https://huggingface.co/datasets/DarthReca/california_burned_areas) |
| Land8Fire | Global (Landsat-8) | 20,000+ human-annotated multispectral patches, built to fix coarse-label and class-imbalance problems. | [DOI](https://doi.org/10.3390/rs17162776) |
| Landsat-8 Active Fire (Pereira et al. 2021) | Global, incl. Australia | 150,000+ patches (200 GB) from Aug–Sep 2020, with a human-annotated subset (9,044 patches). | [arXiv](https://arxiv.org/abs/2101.03409) |
| CanadaFire2023 | Canada | Multi-sensor (Landsat-8/9, Sentinel-2) benchmark for the 2023 season. | – |
| Sardinia case study (2026) | Italy | Multi-temporal Sentinel-2 + Random Forest; Dice 91.8% vs EFFIS's operational 79.9%. | [MDPI](https://www.mdpi.com/2072-4292/18/2/267) |
| ONFIRE | Global | Monthly gridded burned area — too coarse temporally. | – |
| HLS Burn Scars (via PANGAEA) | US | **[Oct 2026]** In the PANGAEA GFM benchmark a plain supervised U-Net (84.5 mIoU) beat all geospatial foundation models at 100% labels; some GFMs led at 10% labels. | [arXiv](https://arxiv.org/abs/2412.04204) |

## 3.3 Fire spread prediction datasets

| Dataset | Region | Key facts | Link |
| :---- | :---- | :---- | :---- |
| Next Day Wildfire Spread (Huot et al. 2022) | US | ~1 km, next-day, mono-temporal. The standard baseline in most spread papers. | [arXiv](https://arxiv.org/abs/2112.02447) |
| WildfireSpreadTS (Gerard et al. 2023) | US | 607 fires 2018–2021, 13,607 daily images, 23 channels, VIIRS-based masks, land cover and weather forecasts; leave-one-year-out CV. | [OpenReview](https://openreview.net/forum?id=RgdGkPRQ03) |
| CFSDS (Canadian Fire Spread Dataset) | Canada | Fires >1,000 ha, 2002–2021, 180 m; day-of-burning by ordinary kriging of MODIS/VIIRS detections; 50 covariates per pixel. Kriging approach looks directly transferable to Australia. | – |
| Mesogeos / FireCube | Mediterranean | Regional equivalent. | – |
| SeasFire Cube | Global | 8–64 day horizons; seasonal framing. | – |
| BCWildfire | British Columbia | 25-year record. | – |

**No Australian equivalent of any of these exists** — the clearest single open gap in the survey.

## 3.4 Australian label sources

| Product | Detail | Res. | Coverage | Link / caveats |
| :---- | :---- | :---- | :---- | :---- |
| NSW FESM | Fire extent + 5 severity classes, semi-automated random forest on Sentinel-2 | 10 m | NSW, 2016/17– (Landsat back to 1989/90 for priority regions) | [SEED](https://datasets.seed.nsw.gov.au/dataset/fire-extent-and-severity-mapping-fesm) |
| AUS GEEBAM | Fire severity, 4 classes, rapid GEE-based mapping | S2 | 2019/20 only, within NIAFED envelope | [DCCEEW](https://fed.dcceew.gov.au/maps/b97b4b1206814b5e8bfdd83c9086dbe2) |
| NIAFED | Aggregated national fire extent | Poly. | 1 Jul 2019 – 24 Feb 2020 | [DCCEEW](https://fed.dcceew.gov.au/datasets/erin::national-indicative-aggregated-fire-extent-dataset/about) |
| Historical Bushfire Boundaries (v2; bulk V4 2025 in use) | Harmonised national fire history | Poly. | Early 1900s–2023 (v2); excludes NT | [Digital Atlas](https://digital.atlas.gov.au/datasets/historical-bushfire-boundaries-version-2-0/about) |
| DEA Bushfire Burnt Area NRT | Near-real-time burnt area | S2 | National, ongoing | [DEA](https://www.dea.ga.gov.au/products/dea-bushfire-burnt-area-near-real-time-services) |
| Vic DEECA severity mapping | Fire severity, 6 classes | S2 | Victoria | – |
| NAFI | Fire scars | 250 m | Northern Australia, 2000– | [firenorth.org.au](https://www.firenorth.org.au) |
| 2020 National Operational Bushfire Boundaries | Operational boundary layer | Poly. | Black Summer only | [data.gov.au](https://data.gov.au/data/dataset/2020-operational-bushfire-boundaries) |

Caveats: FESM is the best label source but still a model output, not field-verified truth; its accuracy is high for unburnt and crown scorch/consumption and notably lower for low-severity classes, and grass fires are mapped as extent only. GEEBAM was built rapidly for impact assessment. NIAFED is documented by DCCEEW as lacking national coherency. HBB was produced to harmonise state agency data (ARDC Bushfire Data Challenge), making it the most promising multi-decade base.

**[Oct 2026] HBB specifics found while building the registry:**

* The Digital Atlas *service* version removes interior holes ("donut" polygons) and chunks fires at 10,000 vertices — unburnt islands become burnt, and one fire can be several records. Check whether the bulk geodatabase preserves holes before using either as a label.
* Bulk V4 (2025) and the live service have diverged (e.g. 345,345 vs 311,984 features); each has records the other lacks (Gospers Mountain and Currowan 2 missing from bulk). `registry/supplement_from_live_service.py` merges additively.
* Opening the bulk gdb in QGIS/GDAL can hang on multipolygon assembly; `OGR_ORGANIZE_POLYGONS=SKIP` fixes it (`registry/split_by_season.py`).
* `capt_method` records the capture method per polygon (aerial photography, linescan, satellite interpretation, ground, …) — the key stratifier for the label audit.
* Coverage varies by jurisdiction, mixes wildfires and prescribed burns, and has no labels past its cut-off (relevant to the 2025–26 holdout).

## 3.5 Weak or global label products

MCD64A1 (MODIS, 500 m), FireCCI51, VIIRS BA, CLMS Global BA v3 and EFFIS are free but coarse, with known omission bias on small or fragmented fires — useful for weak supervision or as baselines, not as primary 10–20 m labels.

## 3.6 Small-scale / aerial datasets

FLAME / FLAME2 (UAV, prescribed slash-pile burns, RGB + IR) and the Corsican Fire Database (ground-level imagery) — pixel-precise but small-scale; noted for completeness.

## 3.7 What we could realistically build

* A FLOGA-style Australian bi-temporal benchmark: labels paired with pre/post Sentinel-2, tiled, event-level splits from the start. **[Oct 2026]** Now being built with own photo-interpreted labels, using HBB/FESM as references to audit rather than as ground truth.
* A kriged day-of-burning progression dataset (CFSDS method on VIIRS/Himawari hotspots, with HBB as the extent envelope) — highest-novelty option for the spread direction.
* Himawari AHI-FSA 10-minute fire-line tracking as a sub-daily progression source.
* Agency linescan as a validation layer — access to RFS R20/599 now granted (see 1.3).

# 4. Open Questions (as of Aug 2026)

* Task: segmentation, progression, or staged (segmentation first)? **[Oct 2026: settled — segmentation + label quality first; progression later.]**
* Novelty angle: model design vs multi-modal fusion, or both, sequenced?
* TRM baseline: reproduce FLOGA first, or start on Australian labels directly? **[Oct 2026: FLOGA reproduced (Step 0 complete).]**
* If multi-modal, which layer first — SAR, Himawari, or fuel/weather?
* How much weight on the label-quality problem itself? **[Oct 2026: central — label viability is priority 1 per the 28 Sep meeting.]**
* What's the smallest defensible TRM feasibility study that sets up a strong Honours proposal?
