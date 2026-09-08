# Microsoft SmartKC reference review

## Upstream identity and revision

The requested legacy URL was:

`https://github.com/microsoft/SmartKC`

At inspection time, `git ls-remote https://github.com/microsoft/SmartKC.git HEAD`
returned “Repository not found”. Microsoft Research identifies the current
official source as:

`https://github.com/microsoft/SmartKC-A-Smartphone-based-Corneal-Topographer`

Microsoft Research’s project page links to that repository as its source code.
The canonical repository was shallow-cloned and inspected at the exact `main`
commit:

`8404350b35d7b6eb3c5714c2e9aa779b1120d065`

The commit was verified with `git ls-remote` and `git rev-parse HEAD` on 2026-09-08.

Useful upstream links are the [repository](https://github.com/microsoft/SmartKC-A-Smartphone-based-Corneal-Topographer/tree/8404350b35d7b6eb3c5714c2e9aa779b1120d065),
[README](https://github.com/microsoft/SmartKC-A-Smartphone-based-Corneal-Topographer/blob/8404350b35d7b6eb3c5714c2e9aa779b1120d065/README.md),
[code license](https://github.com/microsoft/SmartKC-A-Smartphone-based-Corneal-Topographer/blob/8404350b35d7b6eb3c5714c2e9aa779b1120d065/LICENSE-CODE),
and [documentation/content license](https://github.com/microsoft/SmartKC-A-Smartphone-based-Corneal-Topographer/blob/8404350b35d7b6eb3c5714c2e9aa779b1120d065/LICENSE).

## License and reuse requirements

The upstream README states that code is under the MIT License in `LICENSE-CODE`
and Microsoft documentation and other content are under CC BY 4.0 in `LICENSE`.
The MIT license requires the copyright and permission notices in copies or
substantial portions of code. CC BY requires attribution, a link to the
license and an indication of changes when applicable. The upstream project
also includes a research-use disclaimer and does not establish clinical
performance for another device.

No SmartKC code, model weights, images, STL files, ring distributions or text
was copied into KERASCAN. Consequently, no upstream code notice is embedded in
the implementation. This review preserves attribution by naming the source,
revision and licenses here.

## Relevant source paths and findings

| Upstream path at the reviewed commit | Role and observation |
| --- | --- |
| `README.md` | Describes the image-to-topography pipeline, dependencies, command-line parameters, JPEG/3,000×4,000 input assumption, outputs and research-use disclaimer. |
| `main.py` | `corneal_top_gen` runner. Creates dated/per-image output directories, calls preprocessing, segmentation, mire localization, cleaning, Arc-Step and Zernike smoothing, then writes maps, overlays, a surface CSV and a Sim-K CSV. It also contains hard-coded gap calibration polynomials selected by setup. |
| `preprocess.py` | Reads with `cv2.imread`, applies a fixed undo-zoom operation, crops around a centre, supports automatic/manual centre modes, converts to grayscale and writes intermediate images. Its comments assume a particular 3,000×4,000 capture arrangement. |
| `get_center/get_center.py` | Loads a U-Net checkpoint, resizes a crop to 512×512, segments a mask and estimates the centre from the mean of mask pixels. |
| `segment_mires.py` | Chooses either an image-processing enhancement path or a learned segmentation path. The image-processing path uses enhancement, inversion, Canny edges and an inner-circle removal. |
| `mire_detection.py` | Radial scanning over angles; combines detected centres, computes radii, median-filters and removes outliers, and marks or repairs missing points. |
| `mire_detection_graph.py` | Graph/connected-component style mire localization using spatial relationships in the segmentation. |
| `mire_detection_dl.py` | Converts a learned segmentation mask to radial mire radii and meridional points. |
| `camera_size.py` | Converts pixel dimensions using sensor dimensions, focal length and distance, then reads Placido model ring positions for Arc-Step parameters. |
| `arc_step_method.py` | Reads ring radius/height pairs, estimates slopes and reconstructs a surface using the Arc-Step procedure with working distance and gap terms. |
| `get_maps.py` | Converts curvature/elevation arrays into axial and tangential colour maps using lookup palettes. |
| `zernike_smartkc.py`, `metrics.py`, `utils.py` | Zernike fitting/curvature support, quantitative metrics and plotting/point utilities used by the final stages. |
| `hardware/README.md`, `hardware/ring_distribution.txt`, `hardware/hardware_constants.py` | Describe the 3D-printed attachment, LED ring, tested phones, ring model and hardware constants. |
| `mobile_app/smartkc_mobile_app_src/app/src/main/java/com/example/kt/CameraActivityNew.kt` and `NgCameraActivityNew.kt` | Camera capture path that writes numbered `.jpg` files and uses the phone capture stack. |
| `mobile_app/smartkc_mobile_app_src/app/src/main/java/com/example/kt/CheckImages.kt` and `UploadWorker.kt` | Local image review/centre-marking and optional upload workflow. Upload is configurable in the app and is separate from KERASCAN’s offline API. |

## Hardware-dependent assumptions

SmartKC’s README and hardware documentation describe a 3D-printed conical
Placido attachment, diffuser, circular LED and smartphone camera. The sample
run uses 22 mires, a 75.0 distance value, camera parameters such as sensor
dimensions and focal length, and a `ring_distribution.txt` model. The
documentation names tested phones and reports that some phones fail because
their minimum focusing distance is too large. The processing README says its
pipeline supports JPEG images at 3,000×4,000 resolution and asks users to
rescale/pad zoomed images. These are assumptions of that setup, not KERASCAN
configuration values.

The upstream code also assumes compatible ring geometry, working distance,
camera intrinsics, image orientation, centre conventions, segmentation assets
and gap calibration. KERASCAN leaves every unknown device measurement as
`null`, binds a calibration package to a device fingerprint and blocks any
future clinical output until validation is explicit.

## Ideas suitable for KERASCAN’s architecture

The upstream staged sequence is a useful seam: input preparation, centre and
segmentation, mire localization, geometric mapping, surface reconstruction and
derived outputs. KERASCAN keeps those stages behind `QualityAssessment`,
`CentreDetector`, `Segmentation`, `RingTracker` and `FeatureExtractor`
interfaces. Its versioned device configuration and calibration manifest make
the upstream assumptions explicit instead of silently applying them. Its
artifact-oriented output influenced KERASCAN’s empty-but-typed artifact list,
while the upstream intermediate-output behavior motivated explicit stage
states and a no-retention default.

## Code actually reused

None. KERASCAN’s loader, contracts, hashing, API, policy and pipeline are new
code. No upstream implementation was copied or adapted.

## Deferred beyond Week 1

Centre detection, image enhancement, segmentation, radial/graph ring tracking,
Placido geometry mapping, working-distance estimation, Arc-Step reconstruction,
Zernike fitting, topography maps, disease classification, clinical thresholds,
model weights, clinical validation and capture protocol acceptance are all
deferred. No SmartKC phone, camera, ring geometry, resolution, working distance,
calibration polynomial or model weight is treated as valid for KERASCAN.
