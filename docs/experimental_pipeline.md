# Weeks 2–3 experimental pipeline

This prototype estimates a Placido-ring centre, measures image statistics,
samples radial profiles, tracks visible ring candidates and reports descriptive
pixel geometry. It is an engineering experiment. It does not diagnose
keratoconus, provide a normal screening result, estimate corneal power or issue
referral recommendations. A completed or failed experimental run has status
`MANUAL_REVIEW`.

## Shared request and result

`AnalysisRequest` and `AnalysisResult` remain the authoritative models. Their
JSON schemas are generated from
[`contracts/models.py`](../src/corneal_screening/contracts/models.py); request
and result schema version is `1.1.0`. `MOCK` remains the default mode.

The HTTP request remains `POST /analyze` with multipart fields `image` (the
original JPEG or PNG) and `metadata` (JSON for `AnalysisRequest`). The existing
Week 1 metadata is unchanged apart from the schema version; callers may set
`analysis_mode` to `EXPERIMENTAL` to opt in:

```json
{
  "schema_version": "1.1.0",
  "anonymous_patient_id": "synthetic-subject-001",
  "eye": "OD",
  "capture_session_id": "synthetic-session-001",
  "device_version": "device_v1",
  "operator_id": "operator-test",
  "capture_timestamp": "2026-09-29T12:00:00+05:30",
  "analysis_mode": "EXPERIMENTAL"
}
```

All modes return the same `AnalysisResult` shape. Stage records use `PASSED`,
`FAILED`, `BLOCKED` or `NOT_RUN`; a failed prerequisite blocks only dependent
stages. Missing numeric observations serialize as JSON `null` with a matching
false entry in `validity_mask`. Candidate detections are retained per angle as
arrays, including empty arrays where no candidate was found.

For review overlays, P2 can call `POST /analyze?include_overlays=true`. The
usual request returns `artifact_references: []`. The opt-in call places PNG
bytes in the same result’s artifact references as base64, with a SHA-256 and
`retained: false`. The service does not write these artifacts to disk. P2 can
decode `data_base64` and display `centre_overlay`, `ring_candidate_overlay`
and `polar_view`. Overlays are rendered after analysis from copies and are not
used as analytical inputs.

### Successful experimental response

This compact synthetic example uses four angle samples to keep the contract
readable; the checked-in runtime configuration samples 360 angles. It shows a
successful pixel-space run, still marked for manual review:

```json
{
  "schema_version": "1.1.0",
  "software_version": "0.1.0",
  "analysis_id": "018f1a2b-3c4d-7e8f-9012-3456789abcde",
  "analysis_mode": "EXPERIMENTAL",
  "timestamp": "2026-09-29T06:30:00+00:00",
  "anonymous_patient_id": "synthetic-subject-001",
  "eye": "OD",
  "capture_session_id": "synthetic-session-001",
  "operator_id": "operator-test",
  "capture_timestamp": "2026-09-29T12:00:00+05:30",
  "status": "MANUAL_REVIEW",
  "reason_codes": ["CALIBRATION_UNVALIDATED", "CLINICAL_OUTPUT_BLOCKED"],
  "message": "Experimental image-space analysis completed. Results require manual review and are not calibrated or diagnostic.",
  "stage_execution": [
    {"stage_name":"INPUT_VALIDATION","state":"PASSED","started_at":null,"finished_at":null,"reason_codes":[],"message":"Metadata validated."},
    {"stage_name":"DEVICE_CONFIGURATION_VALIDATION","state":"PASSED","started_at":null,"finished_at":null,"reason_codes":[],"message":"Device configuration matches the request."},
    {"stage_name":"IMAGE_LOADING","state":"PASSED","started_at":null,"finished_at":null,"reason_codes":[],"message":"Original image bytes were hashed and decoded without modification."},
    {"stage_name":"CALIBRATION_VALIDATION","state":"FAILED","started_at":null,"finished_at":null,"reason_codes":["CALIBRATION_UNVALIDATED"],"message":"Physical calibration remains unvalidated; this does not calibrate pixel-space measurements."},
    {"stage_name":"QUALITY_ASSESSMENT","state":"PASSED","started_at":null,"finished_at":null,"reason_codes":[],"message":"Experimental blur, exposure and saturation statistics were calculated; they have no validated pass/fail thresholds."},
    {"stage_name":"CENTRE_DETECTION","state":"PASSED","started_at":null,"finished_at":null,"reason_codes":[],"message":"A candidate centre is supported by multiple circular edge bands; diagnostics are experimental."},
    {"stage_name":"SEGMENTATION","state":"NOT_RUN","started_at":null,"finished_at":null,"reason_codes":["STAGE_NOT_IMPLEMENTED"],"message":"A separate segmentation stage was not run."},
    {"stage_name":"POLAR_SAMPLING","state":"PASSED","started_at":null,"finished_at":null,"reason_codes":[],"message":"Image intensities were sampled around the estimated centre."},
    {"stage_name":"RING_TRACKING","state":"PASSED","started_at":null,"finished_at":null,"reason_codes":[],"message":"Ordered radial candidates were tracked with missing angles preserved as null."},
    {"stage_name":"FEATURE_EXTRACTION","state":"PASSED","started_at":null,"finished_at":null,"reason_codes":[],"message":"Descriptive image-space geometry was calculated in pixels; no physical calibration or disease score was applied."},
    {"stage_name":"OUTCOME_POLICY","state":"PASSED","started_at":null,"finished_at":null,"reason_codes":["CLINICAL_OUTPUT_BLOCKED"],"message":"Automatic screening and referral recommendations are disabled; manual review is required."}
  ],
  "device_version": "device_v1",
  "device_configuration_hash": "3c3a05da3516075e902ad60e0798a0c40e6ce211b696d7580f6b5c052157ac4e",
  "calibration_status": "UNVALIDATED",
  "calibration_identifier": "device_v1-week1-placeholder",
  "processing_configuration_version": "experimental-v1.1.0",
  "original_image_sha256": "100538a66a3ccc65011961ad81263522d6d182eebd6decc32f8ba4dc6f644969",
  "quality_measurements": {
    "status":"MEASURED","experimental":true,"image_width_px":384,"image_height_px":384,"channel_count":3,"source_format":"PNG","orientation_transformation":"none",
    "brightness_mean":16.5,"contrast_stddev":54.6,"blur_laplacian_variance":2928.8,"underexposed_pixel_fraction":0.90,"saturated_pixel_fraction":0.0,
    "visible_ring_coverage_fraction":1.0,"missing_sector_count":0,"sector_count":36,"validity":"MEASURED"
  },
  "centre_information": {
    "status":"DETECTED","x_px":173.0,"y_px":204.0,"coordinate_system":"image_pixels_xy","source":"gradient_radial_symmetry_v1","experimental":true,"failure_reason":null,
    "diagnostics":{"candidate_x_px":173.0,"candidate_y_px":204.0,"edge_point_count":27871,"peak_vote_count":284.27,"supporting_edge_band_count":12,"supporting_edge_radii_px":[32.3,38.4,50.7,56.8,72.2,78.3,90.6,96.8,112.1,118.3,130.6,136.7],"ring_angular_coverage":[1.0,1.0,1.0,1.0,1.0,1.0,1.0,1.0,1.0,1.0,1.0,1.0],"search_region_xyxy_px":[0.0,27.4,349.6,380.6]}
  },
  "ring_tracking": {
    "status":"TRACKED","experimental":true,"ring_count":null,"tracked_ring_count":2,"tracked_points":null,
    "angle_samples_deg":[0.0,90.0,180.0,270.0],"candidate_radii_by_angle_px":[[35.0,55.0],[35.0,55.0],[35.0,55.0],[35.0,55.0]],
    "rings":[
      {"ordered_index":1,"mean_radius_px":35.0,"radius_range_px":0.2,"radius_asymmetry_px":0.1,"coverage_fraction":1.0,"radii_px":[35.0,35.1,34.9,35.0],"validity_mask":[true,true,true,true]},
      {"ordered_index":2,"mean_radius_px":55.0,"radius_range_px":0.2,"radius_asymmetry_px":0.1,"coverage_fraction":1.0,"radii_px":[55.0,55.1,54.9,55.0],"validity_mask":[true,true,true,true]}
    ],
    "angular_coverage_fraction":1.0,"missing_sector_count":0,"sector_count":36,"failure_reasons":[],"validity":"MEASURED"
  },
  "features": {
    "status":"EXTRACTED","experimental":true,"measurement_unit":"px","sim_k1_diopters":null,"sim_k2_diopters":null,"mean_k_diopters":null,"astigmatism_diopters":null,
    "mean_ring_spacing_px":20.0,"ring_spacing_stddev_px":0.0,"mean_radial_asymmetry_px":0.1,"angular_coverage_fraction":1.0,"missing_sector_count":0,"validity":"MEASURED"
  },
  "artifact_references": [],
  "screening_disclaimer": "Engineering prototype only; not a diagnosis or a normal screening result. Experimental results require manual review; clinical confirmation requires Pentacam and clinician review."
}
```

### Failed centre analysis response

The image decoded, but a reliable centre could not be supported. The pipeline
records the failure and blocks polar sampling, ring tracking and features:

```json
{
  "schema_version":"1.1.0","software_version":"0.1.0","analysis_id":"018f1a2b-3c4d-7e8f-9012-3456789abcdf","analysis_mode":"EXPERIMENTAL",
  "timestamp":"2026-09-29T06:30:00+00:00","anonymous_patient_id":"synthetic-subject-002","eye":"OD","capture_session_id":"synthetic-session-002","operator_id":"operator-test","capture_timestamp":"2026-09-29T12:00:00+05:30",
  "status":"MANUAL_REVIEW","reason_codes":["CALIBRATION_UNVALIDATED","CENTRE_NOT_FOUND","CLINICAL_OUTPUT_BLOCKED"],
  "message":"Experimental analysis stopped because no reliable Placido-ring centre was found. Manual review is required.",
  "stage_execution":[
    {"stage_name":"INPUT_VALIDATION","state":"PASSED","started_at":null,"finished_at":null,"reason_codes":[],"message":"Metadata validated."},
    {"stage_name":"DEVICE_CONFIGURATION_VALIDATION","state":"PASSED","started_at":null,"finished_at":null,"reason_codes":[],"message":"Device configuration matches the request."},
    {"stage_name":"IMAGE_LOADING","state":"PASSED","started_at":null,"finished_at":null,"reason_codes":[],"message":"Original image bytes were hashed and decoded without modification."},
    {"stage_name":"CALIBRATION_VALIDATION","state":"FAILED","started_at":null,"finished_at":null,"reason_codes":["CALIBRATION_UNVALIDATED"],"message":"Physical calibration remains unvalidated; this does not calibrate pixel-space measurements."},
    {"stage_name":"QUALITY_ASSESSMENT","state":"PASSED","started_at":null,"finished_at":null,"reason_codes":[],"message":"Experimental blur, exposure and saturation statistics were calculated; they have no validated pass/fail thresholds."},
    {"stage_name":"CENTRE_DETECTION","state":"FAILED","started_at":null,"finished_at":null,"reason_codes":["CENTRE_NOT_FOUND"],"message":"No reliable Placido-ring centre was found."},
    {"stage_name":"SEGMENTATION","state":"NOT_RUN","started_at":null,"finished_at":null,"reason_codes":["STAGE_NOT_IMPLEMENTED"],"message":"A separate segmentation stage was not run."},
    {"stage_name":"POLAR_SAMPLING","state":"BLOCKED","started_at":null,"finished_at":null,"reason_codes":[],"message":"Blocked because reliable centre detection failed."},
    {"stage_name":"RING_TRACKING","state":"BLOCKED","started_at":null,"finished_at":null,"reason_codes":[],"message":"Blocked because a reliable centre or polar sample was unavailable."},
    {"stage_name":"FEATURE_EXTRACTION","state":"BLOCKED","started_at":null,"finished_at":null,"reason_codes":[],"message":"Blocked because ring tracking depends on centre and polar sampling."},
    {"stage_name":"OUTCOME_POLICY","state":"PASSED","started_at":null,"finished_at":null,"reason_codes":["CLINICAL_OUTPUT_BLOCKED"],"message":"Automatic screening and referral recommendations are disabled; manual review is required."}
  ],
  "device_version":"device_v1","device_configuration_hash":"3c3a05da3516075e902ad60e0798a0c40e6ce211b696d7580f6b5c052157ac4e","calibration_status":"UNVALIDATED","calibration_identifier":"device_v1-week1-placeholder","processing_configuration_version":"experimental-v1.1.0",
  "original_image_sha256":"4f8727d9db1dcbdee83d5895e55274edd83f9c7c0cb9b4dcee9a648735c5f58e",
  "quality_measurements":{"status":"MEASURED","experimental":true,"image_width_px":384,"image_height_px":384,"channel_count":3,"source_format":"PNG","orientation_transformation":"none","brightness_mean":90.0,"contrast_stddev":0.0,"blur_laplacian_variance":0.0,"underexposed_pixel_fraction":0.0,"saturated_pixel_fraction":0.0,"visible_ring_coverage_fraction":null,"missing_sector_count":null,"sector_count":36,"validity":"MEASURED"},
  "centre_information":{"status":"NOT_DETECTED","x_px":null,"y_px":null,"coordinate_system":"image_pixels_xy","source":null,"experimental":true,"failure_reason":"CENTRE_NOT_FOUND","diagnostics":{"candidate_x_px":null,"candidate_y_px":null,"edge_point_count":0,"peak_vote_count":0.0,"supporting_edge_band_count":0,"supporting_edge_radii_px":[],"ring_angular_coverage":[],"search_region_xyxy_px":[0.0,0.0,384.0,384.0]}},
  "ring_tracking":{"status":"NOT_RUN","experimental":false,"ring_count":null,"tracked_ring_count":null,"tracked_points":null,"angle_samples_deg":null,"candidate_radii_by_angle_px":null,"rings":[],"angular_coverage_fraction":null,"missing_sector_count":null,"sector_count":null,"failure_reasons":[],"validity":"UNAVAILABLE"},
  "features":{"status":"NOT_RUN","experimental":false,"measurement_unit":null,"sim_k1_diopters":null,"sim_k2_diopters":null,"mean_k_diopters":null,"astigmatism_diopters":null,"mean_ring_spacing_px":null,"ring_spacing_stddev_px":null,"mean_radial_asymmetry_px":null,"angular_coverage_fraction":null,"missing_sector_count":null,"validity":"UNAVAILABLE"},
  "artifact_references":[],"screening_disclaimer":"Engineering prototype only; not a diagnosis or a normal screening result. Experimental results require manual review; clinical confirmation requires Pentacam and clinician review."
}
```

Invalid metadata returns HTTP 422 with `code: INVALID_METADATA`. Uploads above
the request limit return HTTP 413 with `code: IMAGE_TOO_LARGE`. Corrupt or
unsupported image bytes return the shared `AnalysisResult` with
`RECAPTURE_REQUIRED`, the typed image reason code and dependent stages blocked.

### MOCK response

The existing mock path remains the default and does not run measurements:
The short `stage_execution` array below highlights the quality stage; a live
response includes every input, processing and outcome stage record.

```json
{
  "schema_version":"1.1.0","software_version":"0.1.0","analysis_id":"018f1a2b-3c4d-7e8f-9012-3456789abcd0","analysis_mode":"MOCK",
  "timestamp":"2026-09-29T06:30:00+00:00","anonymous_patient_id":"synthetic-subject-001","eye":"OD","capture_session_id":"synthetic-session-001","operator_id":"operator-test","capture_timestamp":"2026-09-29T12:00:00+05:30",
  "status":"MANUAL_REVIEW","reason_codes":["MOCK_MODE","ANALYSIS_NOT_PERFORMED","CALIBRATION_UNVALIDATED","CLINICAL_OUTPUT_BLOCKED"],
  "message":"Mock result: image analysis has not been performed.",
  "stage_execution":[{"stage_name":"QUALITY_ASSESSMENT","state":"NOT_RUN","started_at":null,"finished_at":null,"reason_codes":["STAGE_NOT_IMPLEMENTED"],"message":"Not implemented in Week 1; no analysis was performed."}],
  "device_version":"device_v1","device_configuration_hash":"3c3a05da3516075e902ad60e0798a0c40e6ce211b696d7580f6b5c052157ac4e","calibration_status":"UNVALIDATED","calibration_identifier":"device_v1-week1-placeholder","processing_configuration_version":null,
  "original_image_sha256":"431ced6916a2a21a156e38701afe55bbd7f88969fbbfc56d7fe099d47f265460",
  "quality_measurements":{"status":"NOT_ASSESSED","experimental":false,"image_width_px":1,"image_height_px":1,"channel_count":4,"source_format":"PNG","orientation_transformation":"none","brightness_mean":null,"contrast_stddev":null,"blur_laplacian_variance":null,"underexposed_pixel_fraction":null,"saturated_pixel_fraction":null,"visible_ring_coverage_fraction":null,"missing_sector_count":null,"sector_count":null,"validity":"UNAVAILABLE"},
  "centre_information":{"status":"NOT_DETECTED","x_px":null,"y_px":null,"coordinate_system":"image_pixels_xy","source":null,"experimental":false,"diagnostics":null,"failure_reason":null},
  "ring_tracking":{"status":"NOT_RUN","experimental":false,"ring_count":null,"tracked_ring_count":null,"tracked_points":null,"angle_samples_deg":null,"candidate_radii_by_angle_px":null,"rings":[],"angular_coverage_fraction":null,"missing_sector_count":null,"sector_count":null,"failure_reasons":[],"validity":"UNAVAILABLE"},
  "features":{"status":"NOT_RUN","experimental":false,"measurement_unit":null,"sim_k1_diopters":null,"sim_k2_diopters":null,"mean_k_diopters":null,"astigmatism_diopters":null,"mean_ring_spacing_px":null,"ring_spacing_stddev_px":null,"mean_radial_asymmetry_px":null,"angular_coverage_fraction":null,"missing_sector_count":null,"validity":"UNAVAILABLE"},
  "artifact_references":[],"screening_disclaimer":"Engineering prototype only; not a diagnosis or a normal screening result. Experimental results require manual review; clinical confirmation requires Pentacam and clinician review."
}
```

## Measurements and configuration

The versioned defaults are in `configs/application.yaml` under
`experimental`, with `configuration_version: experimental-v1.1.0`. They are
algorithm settings for this prototype, not validated thresholds:

| Output or parameter | Meaning |
|---|---|
| `blur_laplacian_variance` | Variance of the grayscale Laplacian; a descriptive high-frequency/edge statistic. It is not a blur pass/fail rule. |
| `brightness_mean`, `contrast_stddev` | Mean and standard deviation of 8-bit grayscale samples from 0 to 255. |
| `underexposed_pixel_fraction` | Fraction at or below configured grayscale value 8. |
| `saturated_pixel_fraction` | Fraction at or above configured grayscale value 250. |
| `visible_ring_coverage_fraction` | Fraction of sampled angles with at least one bright radial candidate. |
| `missing_sector_count` | Count of configured sectors whose candidate-present fraction is below `sector_min_detection_fraction` (default 0.5). This does not identify why detections are missing. |
| `mean_ring_spacing_px` | Mean difference between adjacent ordered tracks’ mean radii. |
| `mean_radial_asymmetry_px` | Mean absolute radius difference between opposite sampled angles for each track. |
| `radius_range_px` | Maximum minus minimum observed radius on one track. |

`edge_gradient_floor`, centre support counts, candidate intensity/prominence,
tracking radius step, allowed gap and progression coverage are configurable
engineering choices. They have not been tuned or validated on approved device
captures. A failed progression gate reports a tracking failure; it does not
classify capture quality.

The software image convention is origin at top-left, x increasing right, y
increasing down; polar angle starts to the right and increases with the image’s
downward y direction. The physical phone/device orientation remains unknown.
Ring counts and all geometric outputs remain in pixels. No conversion to
millimetres, corneal power or disease score is implemented.

## Interfaces for P1

The image-processing functions use the common Pydantic result models and have
these signatures:

```python
def assess_quality(
    image: np.ndarray,
    configuration: ExperimentalConfiguration | None = None,
) -> QualityMeasurements: ...

def estimate_centre(
    image: np.ndarray,
    configuration: ExperimentalConfiguration | None = None,
) -> CentreInformation: ...

def sample_polar(
    image: np.ndarray,
    centre: CentreInformation,
    configuration: ExperimentalConfiguration | None = None,
) -> PolarSamples: ...

def detect_ring_candidates(
    polar: PolarSamples,
    configuration: ExperimentalConfiguration | None = None,
) -> RingCandidates: ...

def track_ring_candidates(
    candidates: RingCandidates,
    configuration: ExperimentalConfiguration | None = None,
) -> RingTrackingInformation: ...

def extract_geometric_features(
    tracking: RingTrackingInformation,
) -> FeatureMeasurements: ...

def analyze_capture(
    image_path: str | Path,
    metadata: AnalysisRequest,
    device_config: DeviceConfiguration,
    *,
    software_version: str = SOFTWARE_VERSION,
    experimental_configuration: ExperimentalConfiguration | None = None,
    include_overlays: bool = False,
) -> AnalysisResult: ...
```

The agreed synthetic acceptance cases use six circles centred at `(173, 204)`
in a 384×384 image, with radii 35, 55, 75, 95, 115 and 135 px. The centre
Euclidean error tolerance is 2 px. A uniform image must return
`CENTRE_NOT_FOUND` with null centre coordinates. A black obstruction wedge from
25° to 70° must retain empty candidate rows and null tracked observations for
those angles; it must not interpolate them. These are code-level synthetic
checks and are not evidence of real-device accuracy.

The current clean synthetic centre fixture returned `(173.0, 204.0)`, a
measured Euclidean error of `0.00 px` against its known `(173, 204)` centre.

## Device and calibration inputs

The current `device_v1` configuration leaves camera/lens identity, capture
settings, physical ring geometry, working distance and device orientation
unset. The placeholder calibration package is `UNVALIDATED`, and its presence
does not establish calibration. The draft capture instructions are not an
approved clinical protocol. No approved real captures or device repeatability
results were present in the repository at integration time. These values must
remain null until the device team provides and reviews them and an approved
calibration/repeatability procedure has been completed.

## Validation limits

The tests demonstrate deterministic behaviour on synthetic circles, a
synthetic obstruction and a no-ring image, plus API serialization and inline
overlay delivery. They do not measure accuracy on a physical Placido device,
patient captures, varied phones, image compression, real glare or real
occlusions. Treat all measurements and centre/ring overlays as exploratory
review aids.

## Full square frames with surrounding skin

An eye-only crop is not required. The detector searches the whole image for
concentric bright ridges, including smaller off-centre ring regions. A local
morphological white top-hat suppresses broad skin/sclera brightness; it does
not classify skin colour. `ring_background_window_px` (default 15, rounded up
to odd) controls the background-removal diameter. Rings wider than this window
can be suppressed, so this remains a configurable engineering assumption.
`candidate_min_intensity` now refers to local bright-ridge contrast (0–255),
not raw image brightness. Quality statistics still describe the original image.
The polar view displays this local-contrast analytical view.

Centre votes start at 1.5% of the smaller frame dimension with 0.2% radial
steps (minimum 1.5 px). Squared angular support ranks candidates, favouring
consistent circles over numerous weak edge fragments. At least the configured
number of bright circular bands must also support the centre; pupil/iris
boundaries alone do not suffice. `supporting_bright_ring_radii_px` records
these bands. Polar sampling ends just beyond the outermost supported bright
band, limiting unrelated surrounding structures. This may exclude extremely
obstructed outer rings and does not establish the physical ring count.

`tracking_min_coverage_fraction` now applies to each retained track as well
as overall candidate coverage. Short fragments remain in the raw candidates,
but are excluded from ring spacing and other geometric features. Missing
observations in retained tracks remain null; no gaps are filled.

Regression cases cover 12 square-frame combinations of three synthetic
background colours and four eye scales, with texture and a bright rectangular
distractor. They require centre error ≤2 px, five recovered synthetic rings,
radius error ≤1.5 px and per-ring coverage ≥60%. Three no-ring counterparts
must fail centre detection. These are implementation checks, not validation
of real skin tones, real captures, or capture-quality thresholds.
