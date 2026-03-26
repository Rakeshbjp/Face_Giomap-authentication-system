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
        - Verify faces exist in all 4 directional images.
        - Compare embeddings to ensure they belong to the same person.
        - Check for variation in face positioning (anti-photo attack).

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

                # face is [x, y, w, h, ...landmarks..., confidence]
                x, y, w, h = face[0], face[1], face[2], face[3]
                center_x = x + w / 2
                center_y = y + h / 2
                face_centers.append((center_x, center_y))

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

            # Check for positional variation (anti-photo spoofing)
            # Use standard deviation instead of variance for more intuitive thresholding.
            # A real person turning their head in 4 directions will produce at least
            # a tiny shift in detected face centre; a flat photo produces near-zero.
            cx_list = [c[0] for c in face_centers]
            cy_list = [c[1] for c in face_centers]
            x_std = float(np.std(cx_list))
            y_std = float(np.std(cy_list))
            total_std = x_std + y_std

            if total_std < 1.0:
                logger.warning(f"Low positional variance — possible photo attack (x_std={x_std:.2f}, y_std={y_std:.2f})")
                return False, "Liveness check failed: no movement detected"

            logger.info(f"Liveness passed (x_std={x_std:.2f}, y_std={y_std:.2f}, total_std={total_std:.2f})")
            return True, "Liveness verification successful"

        except Exception as e:
            logger.error(f"Liveness check failed: {e}")
            return False, f"Liveness check error: {str(e)}"


# Singleton instance
face_service = FaceRecognitionService()
