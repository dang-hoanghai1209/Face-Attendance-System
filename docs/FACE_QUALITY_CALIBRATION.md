# Face Quality Calibration

## Purpose

Face Quality Gate is a pre-embedding check. It rejects unclear or unsuitable face images before the system creates embeddings or compares identity with cosine similarity.

This gate is not an identity check. Landmarks are used only to validate image conditions such as face position, rough pose, and landmark geometry. Identity verification must still come from face embeddings, similarity thresholds, liveness, and attendance business rules.

## Calibration Status

The current `FACE_QUALITY_*` thresholds are temporary defaults. They have not been calibrated with real camera samples from the actual classroom/device setup.

Do not treat the current values as final production thresholds. Keep them configurable through environment variables until enough real images are collected and reviewed.

## Environment Variables

`FACE_QUALITY_MIN_SHARPNESS`

Minimum edge-variance sharpness. Higher values reject more blurry or low-detail images.

`FACE_QUALITY_MIN_BRIGHTNESS`

Minimum grayscale brightness on a 0-255 scale. Higher values reject darker images.

`FACE_QUALITY_MAX_BRIGHTNESS`

Maximum grayscale brightness on a 0-255 scale. Lower values reject more overexposed images.

`FACE_QUALITY_MIN_FACE_SIZE_RATIO`

Minimum detected face bounding-box area divided by full image area. Higher values reject faces that are too small or too far from the camera.

`FACE_QUALITY_MIN_DETECTION_PROBABILITY`

Minimum MTCNN detection confidence. Higher values reject weak face detections.

`FACE_QUALITY_MAX_YAW_RATIO`

Maximum allowed horizontal pose estimate from landmark geometry. Lower values reject stronger left/right head turns.

## Temporary `.env` Example

These values are examples only, not final calibrated settings:

```env
FACE_QUALITY_MIN_SHARPNESS=8.0
FACE_QUALITY_MIN_BRIGHTNESS=45.0
FACE_QUALITY_MAX_BRIGHTNESS=220.0
FACE_QUALITY_MIN_FACE_SIZE_RATIO=0.08
FACE_QUALITY_MIN_DETECTION_PROBABILITY=0.90
FACE_QUALITY_MAX_YAW_RATIO=0.35
```

## Debug Script

Run the debug tool against real sample images:

```powershell
python backend/scripts/debug_face_quality.py path/to/image.jpg --pretty
```

The output includes detection status, bbox, detection confidence, landmarks, sharpness, brightness, face size ratio, yaw estimate, reason code, and final `PASS` or `FACE_UNCLEAR`.

## Real Image Test Checklist

Collect and compare samples for:

- Clear face looking straight at camera
- Face with mask
- Face turned left and right
- Blurry or motion-shaken image
- Low-light image
- Face too far from camera

## Known Limitations

- MTCNN landmarks can still be guessed when parts of the face are covered.
- Thresholds must be based on real camera and lighting data.
- Landmarks must not be used to verify identity.
- Landmarks are only for checking image conditions before embedding.

## Next Calibration Step

1. Collect real images from the target camera/device and expected classroom lighting.
2. Run `backend/scripts/debug_face_quality.py` for each image.
3. Compare metrics between images that should pass and images that should return `FACE_UNCLEAR`.
4. Adjust `FACE_QUALITY_*` values in `.env`.
5. Run `pytest`.
6. Test the frontend recognition and alert review flow with the calibrated backend.
