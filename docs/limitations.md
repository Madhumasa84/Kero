# Experimental pipeline limitations

The current centre detector, polar sampler, candidate detector, tracker and
geometric features are exploratory image-processing methods. Their parameters
are versioned under `experimental-v1.1.0` and have not been calibrated or
validated as capture-quality rules.

The checked-in evidence is limited to synthetic circles with known centres,
synthetic obstruction sectors, a uniform no-ring image, serialization checks
and local API integration tests. These inputs establish implementation
behavior and synthetic centre error only. They do not establish accuracy,
repeatability or safety on real device captures.

At integration time, no approved real-device images, confirmed camera/lens
identity, capture settings, physical Placido dimensions, working distance,
device orientation convention or reviewed calibration/repeatability results
were available in the repository. The `device_v1` physical fields remain
`null`, and calibration remains `UNVALIDATED`.

On the clean synthetic fixture with six circles at known centre `(173, 204)` in
a 384×384 image, the current detector returned `(173.0, 204.0)`, for a measured
centre error of `0.00 px` (the test acceptance tolerance is 2 px). This single
idealized result does not estimate error on real captures.

All centre, quality, tracking and geometric outputs require human review.
Pixel measurements must not be interpreted as corneal dimensions, power,
diagnostic evidence or screening outcomes. Automatic negative screening and
referral recommendations remain disabled.

Full-frame regression testing additionally covers 12 deterministic square
images with textured synthetic skin-coloured surroundings, four eye scales,
off-centre placement and a bright rectangular distractor. All five synthetic
rings were recovered in each case. Maximum centre error was 0.5351 px;
maximum error in a track's mean radius was 0.6454 px. Three corresponding
no-ring cases rejected centre estimation. Before these corrections, small
ring regions could be missed or assigned an incorrect centre, and short
boundary fragments could become tracks.

The full suite passed 82 tests after these changes. Local synthetic review
images and detailed measurements are in `artifacts/full-frame-review/`
(ignored by Git). This deliberately saved synthetic demonstration does not
change the API's default no-retention behaviour. The fixtures are simplified
renderings, not representative clinical photographs. Reflections, eyelashes,
colour casts, severe obstruction, thick/blurred rings and very small ring
regions still require testing on approved real captures.
