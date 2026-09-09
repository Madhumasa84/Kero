# KERASCAN capture protocol — draft

> Status: Draft for technical-lead and device-team review. This document does not define diagnostic thresholds or replace approved clinical procedures.

## Purpose

This protocol describes how an operator should capture a Placido-ring eye image for KERASCAN’s Week 1 image-input workflow.

A successfully uploaded image is not a diagnosis and does not prove that the capture is clinically acceptable. Screening/referral support only; not a diagnosis. Pentacam and clinician review are required for confirmation.

## Required equipment

- Approved KERASCAN Placido attachment or capture device
- Compatible phone or camera approved by the device team
- Stable mounting or alignment arrangement
- Adequate controlled lighting
- Clean device optics
- Approved local storage location for clinical captures

Do not use a personal cloud folder or place clinical images inside the Git repository.

## Device setup

- Inspect the device and phone camera before capture.
- Ensure the camera lens and Placido-ring surface are clean.
- Use the approved device arrangement and avoid handheld movement during capture.
- Keep lighting consistent and avoid direct reflections into the camera.
- Do not use unapproved camera filters, portrait mode, enhancement, sharpening, cropping, or automatic replacement of the original image.
- Do not invent fixed device distances, brightness values, or thresholds until they are approved by the device team.

## Patient positioning

- Explain the procedure and obtain consent according to the approved local process.
- Position the patient comfortably and keep the head stable.
- Ask the patient to keep the eye being captured open.
- Ask the patient to look at the central fixation point.
- Minimise blinking and movement during image capture.
- Capture one eye at a time.

## Image-capture procedure

1. Confirm the anonymous patient ID, eye, session ID, operator ID, device version, and timestamp.
2. Select the correct eye: `OD` for the right eye or `OS` for the left eye.
3. Align the phone and Placido device using the approved physical setup.
4. Ask the patient to look at the central fixation point with the selected eye open.
5. Check that the Placido rings are visible around the corneal region.
6. Capture the original image without editing it.
7. Check that the file is present and non-empty.
8. Record the matching metadata.
9. If capture conditions are not acceptable, reject the image and recapture it.

## Acceptable-capture conditions

A capture may proceed to the Week 1 software workflow only when:

- The image is a JPEG or PNG file.
- The image is not visibly blurred.
- Strong glare, saturation, or major reflections are absent.
- Eyelashes and eyelids do not cover the important Placido-ring region.
- The eye is not severely off-centre.
- The eye is open and directed towards the central fixation point.
- Placido rings are visible around the corneal region.
- The source image is the original capture and has not been edited, cropped, sharpened, resized, or replaced.
- The correct anonymous metadata is available.

These are capture-quality instructions, not disease criteria.

## Capture-rejection conditions

Reject and recapture when any of the following applies:

- The file is missing, empty, corrupted, or not a JPEG/PNG image.
- The image is visibly blurred.
- Strong glare or saturation obscures the relevant region.
- Eyelashes, eyelids, fingers, device edges, or other objects obstruct important rings.
- The eye is severely off-centre.
- The patient blinked or moved during capture.
- Placido rings are not adequately visible.
- The image orientation or eye side cannot be confirmed.
- The image has been edited, cropped, enhanced, sharpened, resized, or replaced.
- Required metadata is missing or inconsistent.

## Left/right-eye instructions

- Capture and record each eye separately.
- Use `OD` for the patient’s right eye.
- Use `OS` for the patient’s left eye.
- Confirm the selected eye before each capture.
- Do not assume both eyes have the same image quality or capture conditions.
- Do not use one eye’s image or metadata for the other eye.

## File-naming convention

Use this format:

```text
anonymousPatientID_eye_session_captureNumber.extension