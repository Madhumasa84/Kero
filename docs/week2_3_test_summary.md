# Week 2-3 Test Summary



## Scope



Week 2-3 testing focused on synthetic fixtures, image-loading safety,

interface-level behaviour, and capture documentation.



No centre-detection, ring-tracking, disease-prediction, or core-processing

algorithms were modified as part of this work.



## Test Results



| Check | Result |

|---|---|

| Automated pytest suite | 39 passed |

| Ruff lint check | Passed |

| Synthetic fixture generation | Passed |

| Deterministic generation with fixed seed | Passed |

| Fixture metadata generation | Passed |

| Fixture inventory | 9 reusable synthetic cases |



## Synthetic Cases



The reusable generator covers:



- Clear centred rings

- Shifted ring centre

- Different image size

- Different ring count and spacing

- Partially hidden rings

- Blurred rings

- Bright glare patch

- Blank image

- Non-ring image



Each reusable fixture has:



- A synthetic-test filename

- Matching JSON metadata

- Known image dimensions

- Known centre where applicable

- Known ring radii where applicable

- Recorded transformations

- Fixed random seed where randomness is used



## Failure Log



No unresolved failures were observed in the current automated test suite.



Any future algorithm failures should be recorded with:



- Test-case ID

- Expected result

- Actual result

- Command used

- Error or diagnostic output, if available



Algorithm behaviour should be reported to the algorithm owner rather than

silently changed in the fixture/test work.



## Real-Image Evaluation



Real clinical-image collection and independent labelling were not performed.



Approved deidentified clinical-image evaluation remains pending lead/device-team

guidance. Synthetic testing is therefore the current reproducible evaluation

basis.

## Verification Commands

```text
python -m ruff check .
All checks passed!

python -m pytest -q
39 passed in 0.91s

git diff --check
No output / passed


Since you're in PowerShell, easiest is to open it:

```powershell
code docs\week2_3_test_summary.md
