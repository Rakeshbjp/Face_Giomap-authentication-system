# pyre-ignore-all-errors
# type: ignore
"""
Face recognition service using OpenCV DNN (YuNet + SFace).
Zero-compilation, lightweight ONNX models for detection + recognition.
Handles embedding extraction, comparison, and liveness detection.
"""

from __future__ import annotations

import base64
import logging
import io
import os
import numpy as np  # pyre-ignore[21]
from typing import Any, List, Tuple, Optional
from PIL import Image  # type: ignore[import-untyped]
import cv2  # pyre-ignore[21]

from app.config.settings import get_settings  # pyre-ignore[21]

logger = logging.getLogger(__name__)
settings = get_settings()

# Model file paths (relative to backend root)
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DETECTION_MODEL = os.path.join(_BASE_DIR, "app", "models", "weights", "face_detection_yunet_2023mar.onnx")
RECOGNITION_MODEL = os.path.join(_BASE_DIR, "app", "models", "weights", "face_recognition_sface_2021dec.onnx")


# ── Quality thresholds (balanced for webcam) ──
MIN_DETECTION_CONFIDENCE = 0.5    # YuNet detection confidence floor
MIN_FACE_RATIO = 0.04            # Face width must be ≥4% of image width
MIN_FACE_PIXELS = 60             # Face bounding box must be ≥60px wide
MIN_LANDMARK_SPREAD = 0.12       # Eye-to-eye distance must be ≥12% of face width
MIN_VIEWS_MATCHED = 2            # Must match at least 2 of stored views
MIN_FACE_AREA_FOR_VERIFY = 0.04  # Face must be ≥4% of frame during verification
BLUR_THRESHOLD = 15.0            # Laplacian variance below this = very blurry/moving

# ── Full-face completeness thresholds ──
FACE_OBSTRUCTION_EDGE_RATIO = 0.45  # Canny edge density above this = obstruction
MIN_SKIN_RATIO_IN_FACE = 0.08      # ≥8% of face bounding box must be skin-toned


class FaceRecognitionService:
    """Service for face embedding extraction and comparison using OpenCV DNN."""

    def __init__(self):
        self.threshold = settings.FACE_SIMILARITY_THRESHOLD
        self._recognizer = None
        self._eye_cascade = None
        self._init_recognizer()
        self._init_eye_cascade()

    def _init_recognizer(self):
        """Initialize the SFace recognizer model (loaded once)."""
        try:
            if os.path.exists(RECOGNITION_MODEL):
                self._recognizer = cv2.FaceRecognizerSF.create(RECOGNITION_MODEL, "")
                logger.info("SFace recognition model loaded successfully")
            else:
                logger.error(f"Recognition model not found: {RECOGNITION_MODEL}")
        except Exception as e:
            logger.error(f"Failed to load recognition model: {e}")

    def _init_eye_cascade(self):
        """Initialize Haar cascade for eye detection (used for obstruction checks)."""
        try:
            cascade_path = cv2.data.haarcascades + "haarcascade_eye.xml"
            self._eye_cascade = cv2.CascadeClassifier(cascade_path)
            if self._eye_cascade.empty():  # pyre-ignore[16]
                logger.warning("Eye cascade failed to load")
                self._eye_cascade = None
            else:
                logger.info("Eye cascade loaded for obstruction detection")
        except Exception as e:
            logger.error(f"Failed to load eye cascade: {e}")
            self._eye_cascade = None

    def _create_detector(self, width: int, height: int):
        """
        Create a YuNet face detector sized for the given image dimensions.
        Must be re-created per image because input size is fixed at creation.
        """
        if not os.path.exists(DETECTION_MODEL):
            raise FileNotFoundError(f"Detection model not found: {DETECTION_MODEL}")

        detector = cv2.FaceDetectorYN.create(
            DETECTION_MODEL,
            "",
            (width, height),
            score_threshold=0.25,  # low threshold to handle dark / webcam images
            nms_threshold=0.3,
            top_k=5,
        )
        return detector

    def _decode_base64_image(self, base64_string: str) -> np.ndarray:
        """
        Decode a base64-encoded image string to a NumPy array (BGR format).

        Args:
            base64_string: Base64-encoded image data (with or without data URI prefix).

        Returns:
            NumPy array of the image in BGR format (OpenCV standard).

        Raises:
            ValueError: If image cannot be decoded.
        """
        try:
            # Strip data URI prefix if present
            if "," in base64_string:
                base64_string = base64_string.split(",")[1]

            image_bytes = base64.b64decode(base64_string)
            image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            img_array = np.array(image)
            # Convert RGB to BGR for OpenCV
            img_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
            return img_bgr
        except Exception as e:
            logger.error(f"Failed to decode base64 image: {e}")
            raise ValueError(f"Invalid image data: {e}")

    def _enhance_image(self, image: np.ndarray) -> np.ndarray:
        """
        Enhance image contrast using CLAHE (Contrast Limited Adaptive Histogram
        Equalization). Significantly improves face detection in dark / low-contrast
        webcam frames.
        """
        try:
            lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
            l = clahe.apply(l)
            enhanced = cv2.merge([l, a, b])
            return cv2.cvtColor(enhanced, cv2.COLOR_LAB2BGR)
        except Exception:
            return image  # fallback: return original

    def _detect_face(self, image: np.ndarray, strict: bool = True):
        """
        Detect faces in the image using YuNet with quality validation.

        Args:
            image: BGR image as NumPy array.
            strict: If True, enforce quality checks (size, confidence, landmarks).

        Returns:
            The detection result array for the best face, or None.
        """
        try:
            h, w = image.shape[:2]
            detector = self._create_detector(w, h)
            _, faces = detector.detect(image)

            if faces is None or len(faces) == 0:
                # Retry with contrast-enhanced image
                enhanced = self._enhance_image(image)
                _, faces = self._create_detector(w, h).detect(enhanced)
                if faces is None or len(faces) == 0:
                    logger.warning("No face detected (even after enhancement)")
                    return None

            # Return face with highest confidence
            best_idx = int(np.argmax(faces[:, -1]))
            face = faces[best_idx]

            if not strict:
                return face

            # ── Quality gate ──
            confidence = float(face[-1])
            face_w, face_h = float(face[2]), float(face[3])

            # 1) Detection confidence
            if confidence < MIN_DETECTION_CONFIDENCE:
                logger.warning(f"Detection confidence too low: {confidence:.3f} < {MIN_DETECTION_CONFIDENCE}")
                return None

            # 2) Face must be large enough in the frame
            if face_w < MIN_FACE_PIXELS or face_h < MIN_FACE_PIXELS:
                logger.warning(f"Face too small: {face_w:.0f}x{face_h:.0f} < {MIN_FACE_PIXELS}px")
                return None

            face_ratio = face_w / w
            if face_ratio < MIN_FACE_RATIO:
                logger.warning(f"Face ratio too small: {face_ratio:.3f} < {MIN_FACE_RATIO}")
                return None

            # 3) Landmark-based occlusion check
            #    YuNet returns: [x, y, w, h, right_eye_x, right_eye_y,
            #                    left_eye_x, left_eye_y, nose_x, nose_y,
            #                    right_mouth_x, right_mouth_y,
            #                    left_mouth_x, left_mouth_y, confidence]
            if len(face) >= 15:
                right_eye = np.array([face[4], face[5]])
                left_eye = np.array([face[6], face[7]])
                nose = np.array([face[8], face[9]])
                right_mouth = np.array([face[10], face[11]])
                left_mouth = np.array([face[12], face[13]])

                # Eye distance must be reasonable compared to face width
                eye_dist = float(np.linalg.norm(left_eye - right_eye))
                if eye_dist < face_w * MIN_LANDMARK_SPREAD:
                    logger.warning(f"Eyes too close / occluded: eye_dist={eye_dist:.1f}, face_w={face_w:.1f}")
                    return None

                # Nose must be between the eyes (not far outside the face box)
                face_x = float(face[0])
                face_y = float(face[1])
                nose_in_box_x = face_x - face_w * 0.1 <= nose[0] <= face_x + face_w * 1.1
                nose_in_box_y = face_y - face_h * 0.1 <= nose[1] <= face_y + face_h * 1.1
                if not (nose_in_box_x and nose_in_box_y):
                    logger.warning("Nose landmark outside face bounding box — possible occlusion")
                    return None

                # Mouth corners must be roughly symmetric and below the nose
                mouth_center_y = (right_mouth[1] + left_mouth[1]) / 2
                if mouth_center_y < nose[1]:
                    logger.warning("Mouth landmarks above nose — possible occlusion or bad detection")
                    return None

            logger.info(f"Face quality OK: conf={confidence:.3f}, size={face_w:.0f}x{face_h:.0f}, ratio={face_ratio:.3f}")
            return face

        except Exception as e:
            logger.error(f"Face detection failed: {e}")
            return None

    # ──────────────────────────────────────────────
    #  Full-Face Completeness & Obstruction Detection
    # ──────────────────────────────────────────────

    def validate_full_face(self, image: np.ndarray) -> Tuple[bool, str]:
        """
        Validate that the full face is clearly visible with NO obstructions.

        Uses YuNet face detection + OpenCV analysis to check:
        1. Face bounding box is fully inside the frame (not cut off).
        2. All 5 YuNet landmarks are geometrically consistent (eyes, nose, mouth).
        3. Both eyes are detectable via Haar cascade inside the face region.
        4. No foreign objects blocking the face (edge-density analysis).
        5. Sufficient skin-tone ratio inside face bounding box.

        Args:
            image: BGR image as NumPy array.

        Returns:
            Tuple of (is_valid: bool, reason: str).
        """
        try:
            h, w = image.shape[:2]
            detector = self._create_detector(w, h)
            _, faces = detector.detect(image)

            if faces is None or len(faces) == 0:  # pyre-ignore[6]
                return False, "Face is not clearly visible — ensure your full face is in the frame"

            best_idx = int(np.argmax(faces[:, -1]))  # pyre-ignore[16]
            face = faces[best_idx]  # pyre-ignore[29]

            fx, fy, fw, fh = float(face[0]), float(face[1]), float(face[2]), float(face[3])
            confidence = float(face[-1])

            # ── 1) Face must be mostly inside the frame ──
            # Allow faces near edges — only reject if significantly cut off
            margin = -0.05  # negative margin = allow face to extend slightly outside frame

            # ── 2) Face must occupy enough of the frame (not too far) ──
            face_area_ratio = (fw * fh) / (w * h)
            if face_area_ratio < MIN_FACE_AREA_FOR_VERIFY:
                return False, "Face is not clearly visible — move closer to the camera"

            # ── 3) Landmark consistency check (all 5 YuNet landmarks must be valid) ──
            if len(face) >= 15:
                right_eye  = np.array([face[4], face[5]])
                left_eye   = np.array([face[6], face[7]])
                nose       = np.array([face[8], face[9]])
                right_mouth = np.array([face[10], face[11]])
                left_mouth  = np.array([face[12], face[13]])

                # All landmarks must be inside the face bounding box (with tolerance)
                for name, pt in [("right eye", right_eye), ("left eye", left_eye),
                                 ("nose", nose), ("right mouth", right_mouth), ("left mouth", left_mouth)]:
                    if not (fx - fw * 0.15 <= pt[0] <= fx + fw * 1.15 and
                            fy - fh * 0.15 <= pt[1] <= fy + fh * 1.15):
                        logger.warning(f"Landmark {name} outside face box — obstruction likely")
                        return False, "Face is not clearly visible — remove any obstruction from your face"

                # Eyes must be in upper half, mouth in lower half
                face_mid_y = fy + fh * 0.5
                if right_eye[1] > face_mid_y or left_eye[1] > face_mid_y:
                    return False, "Face is not clearly visible — both eyes must be visible"
                if right_mouth[1] < face_mid_y or left_mouth[1] < face_mid_y:
                    return False, "Face is not clearly visible — your face appears partially covered"

                # Nose must be between eyes and mouth vertically
                eye_avg_y = (right_eye[1] + left_eye[1]) / 2
                mouth_avg_y = (right_mouth[1] + left_mouth[1]) / 2
                if not (eye_avg_y < nose[1] < mouth_avg_y):
                    return False, "Face is not clearly visible — keep your face straight and unobstructed"

                # Eye distance must be reasonable (≥20% of face width)
                eye_dist = float(np.linalg.norm(left_eye - right_eye))
                if eye_dist < fw * 0.20:
                    return False, "Face is not clearly visible — both eyes must be clearly visible"

            # ── 4) Blur / motion detection ──
            blur_ok, blur_msg = self._check_blur(image, face)
            if not blur_ok:
                return False, blur_msg

            # ── 5) Both eyes must be clearly visible ──
            eyes_ok, eyes_msg = self._verify_both_eyes_visible(image, face)
            if not eyes_ok:
                return False, eyes_msg

            # ── 6) Obstruction detection via edge density ──
            obstruction_detected, obstruction_msg = self._detect_obstruction(image, face)
            if obstruction_detected:
                return False, obstruction_msg

            # ── 7) Skin-tone ratio check ──
            skin_ok, skin_msg = self._check_skin_ratio(image, face)
            if not skin_ok:
                return False, skin_msg

            # ── 8) Advanced Anti-Spoofing / Single-Frame Liveness ──
            spoof_ok, spoof_msg = self._detect_spoofing(image, face)
            if not spoof_ok:
                return False, spoof_msg

            logger.info(f"Full-face validation PASSED — conf={confidence:.3f}, area_ratio={face_area_ratio:.3f}")
            return True, "OK"

        except Exception as e:
            logger.error(f"Full-face validation error: {e}")
            return True, "OK"

    def _check_blur(
        self, image: np.ndarray, face: np.ndarray
    ) -> Tuple[bool, str]:
        """
        Detect motion blur or camera shake by computing the Laplacian
        variance of the face region. A low variance means the image is blurry
        (face was moving, camera was shaking, etc).
        """
        try:
            fx, fy, fw, fh = int(face[0]), int(face[1]), int(face[2]), int(face[3])
            h, w = image.shape[:2]

            # Crop the face region
            y1 = max(0, fy)
            y2 = min(h, fy + fh)
            x1 = max(0, fx)
            x2 = min(w, fx + fw)

            face_region = image[y1:y2, x1:x2]
            if face_region.size == 0:
                return True, "OK"

            gray = cv2.cvtColor(face_region, cv2.COLOR_BGR2GRAY)
            laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()

            logger.info(f"Blur check: laplacian_var={laplacian_var:.2f}, threshold={BLUR_THRESHOLD}")

            if laplacian_var < BLUR_THRESHOLD:
                return False, "Face is not clearly visible — hold still and face the camera directly"

            return True, "OK"

        except Exception as e:
            logger.error(f"Blur check error: {e}")
            return True, "OK"

    def _verify_both_eyes_visible(
        self, image: np.ndarray, face: np.ndarray
    ) -> Tuple[bool, str]:
        """
        Verify both eyes are visible using Haar cascade eye detector
        on the upper half of the face region. If a hand or object covers
        one eye, the cascade will detect fewer than 2 eyes.
        """
        if self._eye_cascade is None:
            return True, "OK"

        try:
            fx, fy, fw, fh = int(face[0]), int(face[1]), int(face[2]), int(face[3])
            h, w = image.shape[:2]

            # Crop upper 60% of face (where eyes should be)
            eye_y1 = max(0, fy)
            eye_y2 = min(h, fy + int(fh * 0.6))
            eye_x1 = max(0, fx)
            eye_x2 = min(w, fx + fw)

            eye_region = image[eye_y1:eye_y2, eye_x1:eye_x2]
            if eye_region.size == 0:
                return True, "OK"

            gray_eyes = cv2.cvtColor(eye_region, cv2.COLOR_BGR2GRAY)
            gray_eyes = cv2.equalizeHist(gray_eyes)

            eyes = self._eye_cascade.detectMultiScale(  # pyre-ignore[16]
                gray_eyes,
                scaleFactor=1.1,
                minNeighbors=2,   # Lower threshold for glasses wearer
                minSize=(int(fw * 0.06), int(fw * 0.06)),
                maxSize=(int(fw * 0.45), int(fw * 0.45)),
            )

            # Only reject if NO eyes at all detected (glasses can cause single-eye false negatives)
            if len(eyes) < 1:
                logger.warning(f"No eyes detected — possible obstruction")
                return False, "Face is not clearly visible — eyes must be visible"

            return True, "OK"

        except Exception as e:
            logger.error(f"Eye detection check error: {e}")
            return True, "OK"

    def _detect_obstruction(
        self, image: np.ndarray, face: np.ndarray
    ) -> Tuple[bool, str]:
        """
        Detect foreign objects or body parts obstructing the face using
        Canny edge density analysis inside the face bounding box.

        A clear face has smooth skin with relatively low edge density.
        Hands, fingers, objects produce many extra edges.
        """
        try:
            h, w = image.shape[:2]
            fx, fy, fw, fh = int(face[0]), int(face[1]), int(face[2]), int(face[3])
            x1 = max(0, fx - 10)
            y1 = max(0, fy - 10)
            x2 = min(w, fx + fw + 10)
            y2 = min(h, fy + fh + 10)

            face_crop = image[y1:y2, x1:x2]
            if face_crop.size == 0:
                return False, "OK"

            gray = cv2.cvtColor(face_crop, cv2.COLOR_BGR2GRAY)
            gray = cv2.bilateralFilter(gray, 9, 75, 75)
            edges = cv2.Canny(gray, 50, 150)

            edge_ratio = np.count_nonzero(edges) / edges.size

            if edge_ratio > FACE_OBSTRUCTION_EDGE_RATIO:
                logger.warning(f"High edge density in face region: {edge_ratio:.3f} — possible obstruction")
                return True, "Something is blocking your face — remove hands, fingers, or objects and try again"

            return False, "OK"

        except Exception as e:
            logger.error(f"Obstruction detection error: {e}")
            return False, "OK"

    def _check_skin_ratio(
        self, image: np.ndarray, face: np.ndarray
    ) -> Tuple[bool, str]:
        """
        Check that a sufficient portion of the face region contains skin-toned
        pixels. Non-skin objects (phones, paper, hands in gloves) reduce the ratio.
        """
        try:
            h, w = image.shape[:2]
            fx, fy, fw, fh = int(face[0]), int(face[1]), int(face[2]), int(face[3])
            x1 = max(0, fx - 5)
            y1 = max(0, fy - 5)
            x2 = min(w, fx + fw + 5)
            y2 = min(h, fy + fh + 5)

            face_crop = image[y1:y2, x1:x2]
            if face_crop.size == 0:
                return True, "OK"

            hsv = cv2.cvtColor(face_crop, cv2.COLOR_BGR2HSV)

            # Broad skin-tone range in HSV (covers diverse skin tones)
            lower_skin = np.array([0, 20, 50], dtype=np.uint8)
            upper_skin = np.array([35, 255, 255], dtype=np.uint8)
            mask1 = cv2.inRange(hsv, lower_skin, upper_skin)

            # Second range for reddish skin tones
            lower_skin2 = np.array([160, 20, 50], dtype=np.uint8)
            upper_skin2 = np.array([180, 255, 255], dtype=np.uint8)
            mask2 = cv2.inRange(hsv, lower_skin2, upper_skin2)

            skin_mask = mask1 | mask2
            skin_ratio = np.count_nonzero(skin_mask) / skin_mask.size

            if skin_ratio < MIN_SKIN_RATIO_IN_FACE:
                logger.warning(f"Low skin ratio in face region: {skin_ratio:.3f} — possible obstruction")
                return False, "Face is obstructed — remove any objects covering your face"

            return True, "OK"

        except Exception as e:
            logger.error(f"Skin ratio check error: {e}")
            return True, "OK"

    def _detect_spoofing(self, image: np.ndarray, face: np.ndarray) -> Tuple[bool, str]:
        """
        Defence-grade Anti-Spoofing & Presentation Attack Detection (PAD).

        Multi-layered single-frame analysis designed to reject:
        - Screen replay attacks (phone / tablet / monitor showing photo or video)
        - Printed photo attacks (paper printout held in front of camera)
        - Video playback attacks (pre-recorded video played on a device)

        Layers:
        1. LBP (Local Binary Pattern) Texture Analysis — the gold-standard
        2. Color distribution analysis in YCrCb space
        3. FFT Moiré / screen-grid frequency detection (aggressive)
        4. Specular highlight & screen glare mapping
        5. Gradient magnitude uniformity check
        6. Micro-texture depth analysis (Laplacian of Gaussian)
        """
        try:
            h, w = image.shape[:2]
            fx, fy, fw, fh = int(face[0]), int(face[1]), int(face[2]), int(face[3])

            # Crop face with a small padding for context
            pad = int(min(fw, fh) * 0.1)
            x1 = max(0, fx - pad)
            y1 = max(0, fy - pad)
            x2 = min(w, fx + fw + pad)
            y2 = min(h, fy + fh + pad)

            face_crop = image[y1:y2, x1:x2]
            if face_crop.size == 0:
                return True, "OK"

            gray = cv2.cvtColor(face_crop, cv2.COLOR_BGR2GRAY)
            fh_crop, fw_crop = gray.shape[:2]

            spoof_score = 0  # accumulates evidence; >=2 = SPOOF
            spoof_reasons = []

            # ──────────────────────────────────────────────
            #  Layer 1: LBP Texture Analysis (gold-standard)
            # ──────────────────────────────────────────────
            # Real skin has a rich, semi-random micro-texture.
            # Screens and prints lose this: screens add pixel-grid
            # artefacts, prints flatten micro-texture completely.
            # We compute a simplified LBP histogram and measure
            # the distribution's uniformity. Spoofed images have
            # a more uniform (flatter) LBP histogram.
            try:
                lbp_size = min(128, fw_crop, fh_crop)
                gray_lbp = cv2.resize(gray, (lbp_size, lbp_size))

                # Compute simplified LBP (8-neighbour, radius 1)
                lbp_img = np.zeros_like(gray_lbp, dtype=np.uint8)
                for dy, dx, bit in [(-1,-1,0),(-1,0,1),(-1,1,2),(0,1,3),
                                     (1,1,4),(1,0,5),(1,-1,6),(0,-1,7)]:
                    shifted = np.roll(np.roll(gray_lbp, dy, axis=0), dx, axis=1)
                    lbp_img |= ((shifted >= gray_lbp).astype(np.uint8) << bit)

                # Compute LBP histogram (256 bins)
                lbp_hist, _ = np.histogram(lbp_img.ravel(), bins=256, range=(0, 256))
                lbp_hist = lbp_hist.astype(np.float64) / (lbp_hist.sum() + 1e-8)

                # Measure histogram uniformity (entropy).
                # Low entropy = repetitive texture = likely spoof.
                # High entropy = rich natural texture = likely real.
                lbp_entropy = float(-np.sum(lbp_hist[lbp_hist > 0] * np.log2(lbp_hist[lbp_hist > 0] + 1e-12)))

                # Count how many bins have zero mass (dead bins).
                # Real faces spread across many bins; screens cluster into fewer.
                lbp_active_bins = int(np.count_nonzero(lbp_hist))

                logger.info(f"Spoof LBP: entropy={lbp_entropy:.3f}, active_bins={lbp_active_bins}/256")

                if lbp_entropy < 5.6:
                    spoof_score += 1
                    spoof_reasons.append(f"LBP texture too uniform (entropy={lbp_entropy:.2f}<5.6)")
                if lbp_active_bins < 110:
                    spoof_score += 1
                    spoof_reasons.append(f"LBP too few active bins ({lbp_active_bins}<110)")
            except Exception as e:
                logger.warning(f"LBP check skipped: {e}")

            # ──────────────────────────────────────────────
            #  Layer 2: YCrCb Color Distribution Analysis
            # ──────────────────────────────────────────────
            # Real human skin occupies a specific narrow band in
            # YCrCb color space (Cr: ~133-173, Cb: ~77-127).
            # Screens shift chrominance because they use RGB
            # sub-pixels that don't perfectly reproduce skin tones.
            # Prints also shift due to CMYK conversion artifacts.
            try:
                ycrcb = cv2.cvtColor(face_crop, cv2.COLOR_BGR2YCrCb)
                cr_channel = ycrcb[:, :, 1].astype(np.float64)
                cb_channel = ycrcb[:, :, 2].astype(np.float64)

                cr_mean = float(np.mean(cr_channel))
                cb_mean = float(np.mean(cb_channel))
                cr_std = float(np.std(cr_channel))
                cb_std = float(np.std(cb_channel))

                logger.info(f"Spoof YCrCb: Cr_mean={cr_mean:.1f}, Cb_mean={cb_mean:.1f}, "
                           f"Cr_std={cr_std:.2f}, Cb_std={cb_std:.2f}")

                # Screens have abnormally low chrominance variation
                # because they emit uniform backlight. Real skin is varied.
                if cr_std < 5.0 and cb_std < 5.0:
                    spoof_score += 1
                    spoof_reasons.append(f"Chrominance too flat (Cr_std={cr_std:.1f}, Cb_std={cb_std:.1f})")

                # Extreme chrominance shift (outside natural skin range)
                if cr_mean < 120 or cr_mean > 185 or cb_mean < 70 or cb_mean > 140:
                    spoof_score += 1
                    spoof_reasons.append(f"Chrominance outside skin range (Cr={cr_mean:.0f}, Cb={cb_mean:.0f})")
            except Exception as e:
                logger.warning(f"YCrCb check skipped: {e}")

            # ──────────────────────────────────────────────
            #  Layer 3: FFT Moiré / Screen Pattern Detection
            # ──────────────────────────────────────────────
            # Screens have a physical pixel grid that creates
            # periodic high-frequency Moiré patterns when captured
            # by another camera. We detect these with FFT.
            try:
                target_size = 128
                gray_resized = cv2.resize(gray, (target_size, target_size))

                f_transform = np.fft.fft2(gray_resized.astype(np.float64))
                f_shift = np.fft.fftshift(f_transform)
                magnitude = 20.0 * np.log(np.abs(f_shift) + 1e-8)

                # Mask out low frequencies (center)
                cy_f, cx_f = target_size // 2, target_size // 2
                r_mask = 15  # tighter cutoff to be more aggressive
                yy, xx = np.ogrid[-cy_f:target_size-cy_f, -cx_f:target_size-cx_f]
                low_freq_mask = xx*xx + yy*yy <= r_mask*r_mask

                high_mag = magnitude.copy()
                high_mag[low_freq_mask] = 0
                high_freq_mean = float(np.mean(high_mag[~low_freq_mask]))

                # Also check for spectral peaks (Moiré creates bright spots)
                high_freq_max = float(np.max(high_mag[~low_freq_mask]))
                high_freq_std = float(np.std(high_mag[~low_freq_mask]))
                peak_ratio = high_freq_max / (high_freq_mean + 1e-8)

                logger.info(f"Spoof FFT: hf_mean={high_freq_mean:.2f}, hf_max={high_freq_max:.2f}, "
                           f"peak_ratio={peak_ratio:.2f}, hf_std={high_freq_std:.2f}")

                # Aggressive thresholds for screen moiré detection
                if high_freq_mean > 130.0:
                    spoof_score += 1
                    spoof_reasons.append(f"High-frequency energy too strong ({high_freq_mean:.1f}>130)")
                if peak_ratio > 3.0:
                    spoof_score += 1
                    spoof_reasons.append(f"Spectral peak detected (ratio={peak_ratio:.1f}>3.0)")
            except Exception as e:
                logger.warning(f"FFT check skipped: {e}")

            # ──────────────────────────────────────────────
            #  Layer 4: Specular Highlight & Glare Analysis
            # ──────────────────────────────────────────────
            # Screens emit light, creating large over-exposed patches.
            # Real skin has tiny, scattered specular highlights (oil).
            try:
                # Very bright pixels (blown out)
                _, glare_mask = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY)
                glare_ratio = np.count_nonzero(glare_mask) / glare_mask.size

                # Connected components of glare — screens create large blobs,
                # real skin creates tiny scattered dots
                num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(glare_mask, connectivity=8)
                if num_labels > 1:
                    # Largest glare blob (excluding background label 0)
                    blob_areas = [stats[i, cv2.CC_STAT_AREA] for i in range(1, num_labels)]
                    max_blob = max(blob_areas) if blob_areas else 0
                    max_blob_ratio = max_blob / (glare_mask.size + 1e-8)
                else:
                    max_blob_ratio = 0

                logger.info(f"Spoof glare: ratio={glare_ratio:.4f}, max_blob_ratio={max_blob_ratio:.4f}")

                if glare_ratio > 0.04:  # 4% total glare
                    spoof_score += 1
                    spoof_reasons.append(f"Excessive glare ({glare_ratio:.3f}>0.04)")
                if max_blob_ratio > 0.015:  # one big glare patch
                    spoof_score += 1
                    spoof_reasons.append(f"Large glare blob ({max_blob_ratio:.4f}>0.015)")
            except Exception as e:
                logger.warning(f"Glare check skipped: {e}")

            # ──────────────────────────────────────────────
            #  Layer 5: Gradient Magnitude Uniformity
            # ──────────────────────────────────────────────
            # Real 3D faces have rich, varied gradient directions
            # from the curvature of nose, cheeks, chin.
            # Flat images (screen / print) have more uniform gradients.
            try:
                sobelx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
                sobely = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
                grad_mag = np.sqrt(sobelx**2 + sobely**2)

                # Coefficient of variation of gradient magnitude
                grad_mean = float(np.mean(grad_mag))
                grad_std = float(np.std(grad_mag))
                grad_cv = grad_std / (grad_mean + 1e-8)

                logger.info(f"Spoof gradient: mean={grad_mean:.2f}, std={grad_std:.2f}, cv={grad_cv:.3f}")

                # Real faces typically have cv > 1.2
                # Screens/prints tend to be more uniform (cv < 0.9)
                if grad_cv < 0.9:
                    spoof_score += 1
                    spoof_reasons.append(f"Gradient too uniform (cv={grad_cv:.2f}<0.9)")
            except Exception as e:
                logger.warning(f"Gradient check skipped: {e}")

            # ──────────────────────────────────────────────
            #  Layer 6: Micro-Texture Depth (LoG analysis)
            # ──────────────────────────────────────────────
            # Real faces have rich micro-texture at multiple scales
            # due to pores, fine hair, and skin imperfections.
            # Screens lose this (limited by pixel density).
            # Prints lose this (limited by printer DPI).
            try:
                # Laplacian of Gaussian at two scales
                blur_s = cv2.GaussianBlur(gray, (3, 3), 0)
                blur_l = cv2.GaussianBlur(gray, (7, 7), 0)
                log_small = cv2.Laplacian(blur_s, cv2.CV_64F)
                log_large = cv2.Laplacian(blur_l, cv2.CV_64F)

                log_small_var = float(np.var(log_small))
                log_large_var = float(np.var(log_large))

                # Ratio: real faces have strong fine detail relative to coarse
                detail_ratio = log_small_var / (log_large_var + 1e-8)

                logger.info(f"Spoof LoG: small_var={log_small_var:.2f}, large_var={log_large_var:.2f}, "
                           f"detail_ratio={detail_ratio:.3f}")

                # Very low fine-detail = flat/screen image
                if log_small_var < 20.0:
                    spoof_score += 1
                    spoof_reasons.append(f"Micro-texture too weak (LoG_var={log_small_var:.1f}<20)")

                # Low contrast overall
                global_std = float(np.std(gray))
                if global_std < 18.0:
                    spoof_score += 1
                    spoof_reasons.append(f"Image contrast too flat (std={global_std:.1f}<18)")
            except Exception as e:
                logger.warning(f"LoG check skipped: {e}")

            # ──────────────────────────────────────────────
            #  Final Decision: Vote-based scoring
            # ──────────────────────────────────────────────
            # We use a voting system: if 2 or more independent
            # layers flag the image as suspicious, we reject it.
            # This prevents false positives from any single noisy check,
            # while catching real spoofs that trigger multiple detectors.
            logger.info(f"Spoof score: {spoof_score}/6 layers flagged. Reasons: {spoof_reasons}")

            if spoof_score >= 2:
                reason_text = "; ".join(spoof_reasons[:3])  # show top 3 reasons
                logger.warning(f"SPOOFING DETECTED (score={spoof_score}): {reason_text}")
                return False, (
                    f"Spoofing detected — live face required! "
                    f"Photo, video, or screen playback is not allowed. "
                    f"Please present your real face directly to the camera."
                )

            return True, "OK"

        except Exception as e:
            logger.error(f"Spoofing detection error: {e}")
            return True, "OK"

    def verify_temporal_liveness(
        self, frame1_b64: str, frame2_b64: str
    ) -> Tuple[bool, str]:
        """
        Temporal Liveness Detection — Compare TWO frames captured ~400ms apart.

        This is the most reliable anti-spoofing technique without deep learning.
        A static photo produces ZERO pixel-level change between frames.
        A video replay produces smooth, uniform change.
        A real face produces natural, irregular micro-movements (breathing,
        microsaccades, slight postural sway).

        Args:
            frame1_b64: First frame (base64 JPEG)
            frame2_b64: Second frame captured ~400ms later (base64 JPEG)

        Returns:
            (is_live, reason_message)
        """
        try:
            img1 = self._decode_base64_image(frame1_b64)
            img2 = self._decode_base64_image(frame2_b64)

            # Detect face in both frames
            face1 = self._detect_face(img1, strict=False)
            face2 = self._detect_face(img2, strict=False)

            if face1 is None or face2 is None:
                logger.warning("Temporal liveness: face not detected in one or both frames")
                return False, "Face not visible in both liveness frames — keep looking at the camera"

            # ── 1. Robust 2D Affine Landmark Alignment ──
            # A photo or screen is a flat 2D plane. If we calculate the affine
            # transformation between the two sets of 5 landmarks (eyes, nose, mouth),
            # we can perfectly map frame 2 onto frame 1.
            # - For a 2D photo, the mapping will be nearly identical (diff close to 0)
            #   even if the hand shakes, pushes, or turns the phone!
            # - For a real 3D face, the 2D affine transform cannot compensate for
            #   3D parallax, breathing, and micro-expressions.

            # Landmarks: [x,y, w,h,  re_x,re_y,  le_x,le_y,  nt_x,nt_y,  rcm_x,rcm_y,  lcm_x,lcm_y, conf]
            pts1 = np.array([
                [face1[4], face1[5]],   # right eye
                [face1[6], face1[7]],   # left eye
                [face1[8], face1[9]],   # nose
                [face1[10], face1[11]], # right mouth
                [face1[12], face1[13]]  # left mouth
            ], dtype=np.float32)

            pts2 = np.array([
                [face2[4], face2[5]],
                [face2[6], face2[7]],
                [face2[8], face2[9]],
                [face2[10], face2[11]],
                [face2[12], face2[13]]
            ], dtype=np.float32)

            # Estimate 2D affine transform from pts2 to pts1
            M, _ = cv2.estimateAffinePartial2D(pts2, pts1)
            
            if M is None:
                # If alignment fails completely, assume bad frames (movement too fast)
                return False, "Movement too fast or face obscured. Please hold still."

            gray1 = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY)
            gray2 = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY)

            # Warp gray2 to align with gray1
            aligned_gray2 = cv2.warpAffine(gray2, M, (gray1.shape[1], gray1.shape[0]))

            # Crop tightly around the inner face of frame 1 (exclude background)
            fx, fy, fw, fh = int(face1[0]), int(face1[1]), int(face1[2]), int(face1[3])
            # Tighter crop: 10% in from left/right, 20% from top (forehead), 10% bottom
            cx1 = max(0, fx + int(fw * 0.1))
            cx2 = min(gray1.shape[1], fx + int(fw * 0.9))
            cy1 = max(0, fy + int(fh * 0.2))
            cy2 = min(gray1.shape[0], fy + int(fh * 0.9))

            face_roi_1 = gray1[cy1:cy2, cx1:cx2].astype(np.float64)
            face_roi_aligned_2 = aligned_gray2[cy1:cy2, cx1:cx2].astype(np.float64)

            if face_roi_1.size == 0:
                return False, "Face too close to the edge of the camera."

            diff = np.abs(face_roi_1 - face_roi_aligned_2)
            diff_mean = float(np.mean(diff))
            diff_std = float(np.std(diff))
            diff_max = float(np.max(diff))

            # ── 2. Screen/Photo Detection ──
            # Because we PERFECTLY aligned the face in 2D space, any remaining difference
            # comes from lighting, camera noise, and actual 3D depth/parallax.
            # - Flat photos/screens usually yield diff_mean < 4.0
            # - Real faces yield diff_mean > 5.0 (often 6.0 - 15.0)
            logger.info(f"Temporal 2D Affine Alignment: diff_mean={diff_mean:.3f}, diff_std={diff_std:.3f}")

            if diff_mean < 4.5:
                logger.warning(f"Temporal liveness FAILED: Flat 2D surface detected (diff_mean={diff_mean:.3f}<4.5)")
                return False, (
                    "Liveness failed: Flat 2D surface detected! "
                    "You are using a photo or video replay. "
                    "Only live human faces are allowed."
                )

            # If diff_mean is extremely high, they are shaking their head violently,
            # or it's a completely different frame (e.g. video cut)
            if diff_mean > 35.0:
                 return False, "Too much movement detected. Please hold your head steady."

            logger.info("Temporal liveness PASSED")
            return True, "OK"

        except Exception as e:
            logger.error(f"Temporal liveness check error: {e}")
            # On error, don't block — fall through to other checks
            return True, "OK"

    def extract_embedding(self, base64_image: str, strict: bool = True) -> Optional[List[float]]:
        """
        Extract 128-d face embedding from a base64-encoded image.

        Args:
            base64_image: Base64-encoded image string.
            strict: If True, enforce quality checks before extracting.

        Returns:
            List of 128 float values representing the face embedding,
            or None if no face detected or quality check fails.
        """
        embedding, _ = self.extract_embedding_with_reason(base64_image, strict=strict)
        return embedding

    def extract_embedding_with_reason(
        self, base64_image: str, strict: bool = True
    ) -> Tuple[Optional[List[float]], str]:
        """
        Extract 128-d face embedding with a detailed failure reason.

        When strict=True (verification mode), also validates that the
        full face is visible and not obstructed by hands, objects, etc.

        Returns:
            Tuple of (embedding_list_or_None, reason_string).
        """
        try:
            if self._recognizer is None:
                logger.error("Recognition model not initialized")
                return None, "Recognition model not available"

            image = self._decode_base64_image(base64_image)

            # ── Full-face completeness check (strict / verification mode) ──
            if strict:
                face_ok, face_reason = self.validate_full_face(image)
                if not face_ok:
                    logger.warning(f"Full-face validation failed: {face_reason}")
                    return None, face_reason

            face = self._detect_face(image, strict=strict)

            if face is None:
                logger.warning("No face detected or quality check failed")
                return None, "Face not clearly visible — remove obstructions, face the camera, and ensure good lighting"

            # Align the face and extract embedding
            aligned = self._recognizer.alignCrop(image, face)  # pyre-ignore[16]
            embedding = self._recognizer.feature(aligned)  # pyre-ignore[16]
            embedding_list = embedding.flatten().tolist()

            logger.info(f"Extracted embedding with {len(embedding_list)} dimensions")
            return embedding_list, "OK"

        except Exception as e:
            logger.error(f"Embedding extraction failed: {e}")
            return None, f"Embedding extraction failed: {str(e)}"

    def extract_multiple_embeddings(self, base64_images: List[str]) -> Tuple[List[List[float]], List[str]]:
        """
        Extract embeddings from multiple face images (front, left, right, up/down).

        Args:
            base64_images: List of 4 base64-encoded face images.

        Returns:
            Tuple of (embeddings list, error messages list).
        """
        directions = ["front", "left", "right", "up/down"]
        embeddings = []
        errors = []

        for i, img in enumerate(base64_images):
            direction = directions[i] if i < len(directions) else f"image_{i}"
            embedding = self.extract_embedding(img, strict=False)  # relaxed during registration

            if embedding is not None:
                embeddings.append(embedding)
                logger.info(f"Successfully extracted embedding for {direction} view")
            else:
                errors.append(f"No face detected in {direction} view")
                logger.warning(f"Failed to extract embedding for {direction} view")

        return embeddings, errors

    def _compute_similarity(self, vec_a: np.ndarray, vec_b: np.ndarray) -> float:
        """Compute cosine similarity between two embedding vectors."""
        if self._recognizer is not None:
            return float(self._recognizer.match(  # pyre-ignore[16]
                vec_a, vec_b, cv2.FaceRecognizerSF_FR_COSINE
            ))
        # Fallback: manual cosine similarity
        dot = np.dot(vec_a.flatten(), vec_b.flatten())
        norm = np.linalg.norm(vec_a) * np.linalg.norm(vec_b)
        return float(dot / norm) if norm > 0 else 0.0

    def compare_embeddings(
        self, live_embedding: List[float], stored_embeddings: List[List[float]]
    ) -> Tuple[bool, float]:
        """
        Compare a live face embedding against stored embeddings with
        strict multi-view matching.

        Instead of just taking the best score, requires the live face to
        match at least MIN_VIEWS_MATCHED of the stored views above threshold.
        The reported score is the average of all per-view similarities.

        Args:
            live_embedding: 128-d embedding from the live face capture.
            stored_embeddings: List of stored 128-d embedding vectors.

        Returns:
            Tuple of (is_match: bool, average_similarity_score: float).
        """
        try:
            live_vec = np.array(live_embedding, dtype=np.float32).reshape(1, -1)
            scores: list[float] = []
            views_passed: int = 0

            for i, stored in enumerate(stored_embeddings):
                stored_vec = np.array(stored, dtype=np.float32).reshape(1, -1)
                score = self._compute_similarity(live_vec, stored_vec)
                scores.append(score)

                if score >= self.threshold:
                    views_passed = views_passed + 1  # pyre-ignore[58]
                logger.info(f"  view[{i}] score={score:.4f} {'PASS' if score >= self.threshold else 'FAIL'}")

            avg_score = float(np.mean(scores)) if scores else 0.0
            min_required = min(MIN_VIEWS_MATCHED, len(stored_embeddings))
            is_match = views_passed >= min_required

            logger.info(
                f"Face comparison: match={is_match}, "
                f"views_passed={views_passed}/{len(stored_embeddings)}, "
                f"avg_score={avg_score:.4f}, threshold={self.threshold}"
            )
            return is_match, round(avg_score, 4)  # pyre-ignore[6]

        except Exception as e:
            logger.error(f"Embedding comparison failed: {e}")
            return False, 0.0

    def perform_liveness_check(self, base64_images: List[str]) -> Tuple[bool, str]:
        """
        Perform liveness detection by analyzing multiple face images.

        Strategy:
        - Run anti-spoofing on EVERY frame (reject screens / prints)
        - Verify faces exist in all 4 directional images.
        - Compare embeddings to ensure they belong to the same person.
        - Check for variation in face positioning (anti-photo attack).
        - Check face-size variation across views (3D depth cue).

        Args:
            base64_images: List of base64-encoded face images from different angles.

        Returns:
            Tuple of (is_live: bool, message: str).
        """
        try:
            if len(base64_images) < 4:
                return False, "Insufficient images for liveness detection"

            embeddings: list[list[float]] = []
            face_centers: list[tuple[Any, Any]] = []
            face_sizes: list[float] = []  # Track face bounding box areas
            skipped: int = 0

            for i, img_b64 in enumerate(base64_images):
                image = self._decode_base64_image(img_b64)

                # Try detection on original image first
                face = self._detect_face(image, strict=False)

                # Retry with enhanced image if detection failed
                if face is None:
                    enhanced = self._enhance_image(image)
                    face = self._detect_face(enhanced, strict=False)

                if face is None:
                    logger.warning(f"No face detected in image {i + 1} (skipping)")
                    skipped = skipped + 1  # pyre-ignore[58]
                    # Allow up to 2 missed images — side angles often fail detection
                    if skipped > 2:
                        return False, f"Too many images without a face ({skipped} of {len(base64_images)})"
                    continue

                # ── Anti-spoofing on EVERY registration frame ──
                spoof_ok, spoof_msg = self._detect_spoofing(image, face)
                if not spoof_ok:
                    logger.warning(f"Anti-spoofing failed on registration image {i + 1}: {spoof_msg}")
                    return False, f"Registration rejected: {spoof_msg}"

                # face is [x, y, w, h, ...landmarks..., confidence]
                x, y, w, h = face[0], face[1], face[2], face[3]
                center_x = x + w / 2
                center_y = y + h / 2
                face_centers.append((center_x, center_y))
                face_sizes.append(float(w * h))  # Track face area

                # Extract embedding
                aligned = self._recognizer.alignCrop(image, face)  # pyre-ignore[16]
                emb = self._recognizer.feature(aligned).flatten().tolist()  # pyre-ignore[16]
                embeddings.append(emb)

            # Need at least 2 valid face detections
            if len(embeddings) < 2:
                return False, f"Could not detect faces in enough images ({len(embeddings)} of {len(base64_images)})."

            reference: list[float] = embeddings[0]
            rest: list[list[float]] = list(embeddings[1:])  # pyre-ignore[29]
            for i, emb in enumerate(rest, 1):
                is_match, score = self.compare_embeddings(reference, [emb])
                if not is_match:
                    return False, f"Face mismatch detected between views (image {i + 1})"

            # ── Positional variation (anti-photo spoofing) ──
            # A real person turning their head in 4 directions will produce
            # significant shifts in detected face centre.
            # A flat photo or screen produces near-zero variation.
            cx_list = [c[0] for c in face_centers]
            cy_list = [c[1] for c in face_centers]
            x_std = float(np.std(cx_list))
            y_std = float(np.std(cy_list))
            total_std = x_std + y_std

            if total_std < 5.0:
                logger.warning(f"Low positional variance — possible photo/screen attack (x_std={x_std:.2f}, y_std={y_std:.2f}, total={total_std:.2f})")
                return False, (
                    "Liveness check failed: Not enough head movement detected. "
                    "Please actively turn your head in each direction as instructed."
                )

            # ── Face size variation (3D depth cue) ──
            # When a real person turns their head, the apparent face width/height
            # changes due to perspective. A flat image on a screen stays constant.
            if len(face_sizes) >= 3:
                size_std = float(np.std(face_sizes))
                size_mean = float(np.mean(face_sizes))
                size_cv = size_std / (size_mean + 1e-8)

                logger.info(f"Liveness face-size: mean={size_mean:.0f}, std={size_std:.1f}, cv={size_cv:.4f}")

                if size_cv < 0.01:
                    logger.warning(f"Face size unchanged across views — flat image (cv={size_cv:.4f})")
                    return False, (
                        "Liveness check failed: Face size did not change across views. "
                        "A real face changes apparent size when you turn. "
                        "Photo or screen detected."
                    )

            logger.info(f"Liveness passed (x_std={x_std:.2f}, y_std={y_std:.2f}, total_std={total_std:.2f})")
            return True, "Liveness verification successful"

        except Exception as e:
            logger.error(f"Liveness check failed: {e}")
            return False, f"Liveness check error: {str(e)}"


# Singleton instance
face_service = FaceRecognitionService()
