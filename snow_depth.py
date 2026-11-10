import logging
from typing import List, Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)


def hex_to_hsv(hex_color: str) -> Tuple[int, int, int]:
    """Convert a hex color string to OpenCV HSV (H: 0..179, S: 0..255, V: 0..255)."""
    hex_color = hex_color.lstrip("#")
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)

    pixel = np.uint8([[[b, g, r]]])
    hsv = cv2.cvtColor(pixel, cv2.COLOR_BGR2HSV)[0][0]
    return int(hsv[0]), int(hsv[1]), int(hsv[2])


def get_mask_for_color(
    hsv_img: np.ndarray, hex_color: str, tolerance: int = 50
) -> np.ndarray:
    """Create a binary HSV mask for a target hex color, handling red hue wrap-around."""
    h_val, s_val, v_val = hex_to_hsv(hex_color)
    h_tol = 15

    s_low = max(10, s_val - tolerance)
    s_high = min(255, s_val + tolerance + 60)
    v_low = max(10, v_val - tolerance)
    v_high = min(255, v_val + tolerance + 120)

    if h_val - h_tol < 0:
        lower1 = np.array([0, s_low, v_low], dtype=np.uint8)
        upper1 = np.array([h_val + h_tol, s_high, v_high], dtype=np.uint8)
        lower2 = np.array([180 + (h_val - h_tol), s_low, v_low], dtype=np.uint8)
        upper2 = np.array([179, s_high, v_high], dtype=np.uint8)
        return cv2.bitwise_or(
            cv2.inRange(hsv_img, lower1, upper1),
            cv2.inRange(hsv_img, lower2, upper2),
        )
    if h_val + h_tol > 179:
        lower1 = np.array([h_val - h_tol, s_low, v_low], dtype=np.uint8)
        upper1 = np.array([179, s_high, v_high], dtype=np.uint8)
        lower2 = np.array([0, s_low, v_low], dtype=np.uint8)
        upper2 = np.array([(h_val + h_tol) - 180, s_high, v_high], dtype=np.uint8)
        return cv2.bitwise_or(
            cv2.inRange(hsv_img, lower1, upper1),
            cv2.inRange(hsv_img, lower2, upper2),
        )

    lower_bound = np.array([h_val - h_tol, s_low, v_low], dtype=np.uint8)
    upper_bound = np.array([h_val + h_tol, s_high, v_high], dtype=np.uint8)
    return cv2.inRange(hsv_img, lower_bound, upper_bound)


def _clean_1d_mask(
    mask: np.ndarray, close_gap: int = 10, min_len: int = 8
) -> np.ndarray:
    """
    Perform 1D morphological closing followed by opening without boundary bleed.
    Fills internal gaps up to `close_gap` px and removes segments < `min_len`.
    """
    m = mask.astype(bool).copy()
    n = len(m)

    # 1. Fill internal gaps bounded by True on both sides
    i = 0
    while i < n:
        if not m[i]:
            j = i
            while j < n and not m[j]:
                j += 1
            if i > 0 and j < n and (j - i) <= close_gap:
                m[i:j] = True
            i = j
        else:
            i += 1

    # 2. Drop short isolated segments
    i = 0
    while i < n:
        if m[i]:
            j = i
            while j < n and m[j]:
                j += 1
            if (j - i) < min_len:
                m[i:j] = False
            i = j
        else:
            i += 1

    return m


def _hex_to_chroma_weights(hex_color: str) -> Tuple[float, float, float]:
    """
    Convert a hex color to zero-mean chroma projection weights (w_r, w_g, w_b)
    normalized so that a pure red '#FF0000' yields (1.0, -0.5, -0.5).
    """
    hex_color = hex_color.lstrip("#")
    if len(hex_color) != 6:
        return (1.0, -0.5, -0.5)
    r = float(int(hex_color[0:2], 16))
    g = float(int(hex_color[2:4], 16))
    b = float(int(hex_color[4:6], 16))
    mean_val = (r + g + b) / 3.0
    dr, dg, db = r - mean_val, g - mean_val, b - mean_val
    max_comp = max(abs(dr), abs(dg), abs(db))
    if max_comp < 1e-3:
        return (1.0, -0.5, -0.5)
    return (dr / max_comp, dg / max_comp, db / max_comp)


def _is_ir_monochrome(img: np.ndarray) -> bool:
    """Return True if the image is monochrome/infrared (R, G, B nearly identical)."""
    if len(img.shape) < 3 or img.shape[2] < 3:
        return True
    f = img.astype(np.float32)
    b, g, r = f[:, :, 0], f[:, :, 1], f[:, :, 2]
    color_diff = float(np.mean(np.abs(r - g) + np.abs(g - b)))
    return color_diff < 3.0


def _compute_color_ridge_response(
    img: np.ndarray, stick_colors: Optional[List[str]] = None
) -> np.ndarray:
    """
    Compute horizontal ridge contrast for a colored snow stick in daylight.
    Combines local chroma ridge with chroma-gated luminance contrast for frosty lenses.
    """
    f = img.astype(np.float32)
    b, g, r = f[:, :, 0], f[:, :, 1], f[:, :, 2]
    pad = 10

    weights_list = (
        [_hex_to_chroma_weights(c) for c in stick_colors]
        if stick_colors
        else [(1.0, -0.5, -0.5)]
    )

    chroma_ridge = np.zeros(img.shape[:2], dtype=np.float32)
    for wr, wg, wb in weights_list:
        chroma = wr * r + wg * g + wb * b
        cp = np.pad(chroma, ((0, 0), (pad, pad)), mode="edge")
        c_left = (cp[:, pad - 7 : -pad - 7] + cp[:, pad - 5 : -pad - 5]) / 2.0
        c_right = (
            cp[:, pad + 5 : cp.shape[1] - pad + 5]
            + cp[:, pad + 7 : cp.shape[1] - pad + 7]
        ) / 2.0
        ridge = np.clip(np.minimum(chroma - c_left, chroma - c_right), 0.0, None)
        chroma_ridge = np.maximum(chroma_ridge, ridge)

    # Dark line contrast against bright white snow (gated by chroma presence)
    gp = np.pad(g, ((0, 0), (pad, pad)), mode="edge")
    g_left = (gp[:, pad - 7 : -pad - 7] + gp[:, pad - 5 : -pad - 5]) / 2.0
    g_right = (
        gp[:, pad + 5 : gp.shape[1] - pad + 5]
        + gp[:, pad + 7 : gp.shape[1] - pad + 7]
    ) / 2.0
    dark_ridge = np.clip(np.minimum(g_left - g, g_right - g), 0.0, None)

    gate = np.clip((chroma_ridge - 1.5) / 2.5, 0.0, 1.0)
    return chroma_ridge * 1.5 + dark_ridge * gate


def _compute_ir_ridge_response(img: np.ndarray) -> np.ndarray:
    """
    Compute horizontal ridge contrast for an IR-illuminated snow stick at night.
    Detects thin bright ridges while rejecting wide lens-flare gradients.
    """
    if len(img.shape) == 3:
        f = img.astype(np.float32)
        gray = 0.299 * f[:, :, 2] + 0.587 * f[:, :, 1] + 0.114 * f[:, :, 0]
    else:
        gray = img.astype(np.float32)

    pad = 10
    gp = np.pad(gray, ((0, 0), (pad, pad)), mode="edge")
    left_bg = (
        gp[:, pad - 8 : -pad - 8]
        + gp[:, pad - 6 : -pad - 6]
        + gp[:, pad - 4 : -pad - 4]
    ) / 3.0
    right_bg = (
        gp[:, pad + 4 : gp.shape[1] - pad + 4]
        + gp[:, pad + 6 : gp.shape[1] - pad + 6]
        + gp[:, pad + 8 : gp.shape[1] - pad + 8]
    ) / 3.0

    bright_ridge = np.clip(0.5 * ((gray - left_bg) + (gray - right_bg)), 0.0, None)
    not_ramp = np.minimum(gray - left_bg + 2.0, gray - right_bg + 2.0) > 0
    return bright_ridge * not_ramp


def _detect_markers_along_line(
    img: np.ndarray,
    xs: np.ndarray,
    y1: int,
    y2: int,
) -> List[Tuple[int, float]]:
    """
    Detect bright retroreflective marker bands along the fitted stick line [y1..y2].
    Returns a list of (y_index, strength) tuples sorted from top to bottom.
    """
    h, w = img.shape[:2]
    if len(img.shape) == 3:
        f = img.astype(np.float32)
        gray = 0.299 * f[:, :, 2] + 0.587 * f[:, :, 1] + 0.114 * f[:, :, 0]
    else:
        gray = img.astype(np.float32)

    pad = 10
    gp = np.pad(gray, ((0, 0), (pad, pad)), mode="edge")
    left_bg = (
        gp[:, pad - 8 : -pad - 8]
        + gp[:, pad - 6 : -pad - 6]
        + gp[:, pad - 4 : -pad - 4]
    ) / 3.0
    right_bg = (
        gp[:, pad + 4 : gp.shape[1] - pad + 4]
        + gp[:, pad + 6 : gp.shape[1] - pad + 6]
        + gp[:, pad + 8 : gp.shape[1] - pad + 8]
    ) / 3.0
    bright_narrow = np.clip(np.minimum(gray - left_bg, gray - right_bg), 0.0, None)

    ys = np.arange(h)
    xs_c = np.clip(xs, 2, w - 3)
    marker_prof = np.zeros(h, dtype=np.float32)
    for offset in (-2, -1, 0, 1, 2):
        marker_prof = np.maximum(marker_prof, bright_narrow[ys, xs_c + offset])

    search_top = max(2, y1 - 8)
    search_bot = min(h - 2, y2 + 4)
    peaks: List[Tuple[int, float]] = []
    for y_idx in range(search_top, search_bot):
        val = float(marker_prof[y_idx])
        win_start = max(search_top, y_idx - 8)
        win_end = min(search_bot, y_idx + 9)
        if val > 25.0 and val >= float(np.max(marker_prof[win_start:win_end])):
            if not peaks or (y_idx - peaks[-1][0]) >= 18:
                peaks.append((y_idx, val))
            elif val > peaks[-1][1]:
                peaks[-1] = (y_idx, val)

    return peaks


def _fit_stick_line_and_measure(
    img: np.ndarray,
    resp: np.ndarray,
    is_ir: bool,
    debug_img: Optional[np.ndarray] = None,
) -> Tuple[Optional[float], List[float]]:
    """
    Fit the dominant straight line across the ridge response map and measure the
    Euclidean length of the visible stick segment in pixels, along with marker offsets.
    """
    h, w = resp.shape
    if h < 20 or w < 12:
        return None, []

    ys = np.arange(h)
    max_dx = min(40, w - 10)
    best_score = -1.0
    best_line = (w // 2, w // 2)

    for x_top in range(4, w - 4):
        for dx in range(-max_dx, max_dx + 1):
            x_bot = x_top + dx
            if x_bot < 2 or x_bot >= w - 2:
                continue
            xs = np.round(x_top + (dx * ys) / (h - 1)).astype(int)
            prof = np.maximum(
                resp[ys, xs - 1], np.maximum(resp[ys, xs], resp[ys, xs + 1])
            )
            score = float(np.sum(np.minimum(prof, 25.0)))
            if score > best_score:
                best_score = score
                best_line = (x_top, x_bot)

    x_top, x_bot = best_line
    dx = x_bot - x_top
    xs = np.clip(np.round(x_top + (dx * ys) / (h - 1)).astype(int), 2, w - 3)
    prof = np.zeros(h, dtype=np.float32)
    for offset in (-2, -1, 0, 1, 2):
        prof = np.maximum(prof, resp[ys, xs + offset])

    q75 = float(np.percentile(prof, 75))
    min_q75 = 12.0 if is_ir else 15.0
    if q75 < min_q75:
        return None, []

    thresh = float(np.clip(0.18 * q75, 7.5 if is_ir else 10.0, 18.0))
    cleaned = _clean_1d_mask(prof >= thresh, close_gap=12, min_len=8)
    active_ys = np.where(cleaned)[0]
    if len(active_ys) < 25:
        return None, []

    y1, y2 = int(active_ys[0]), int(active_ys[-1])
    if y1 > max(35, int(h * 0.25)):
        return None, []

    peaks = _detect_markers_along_line(img, xs, y1, y2)
    # Snap top endpoint to the top reflective marker cap if present near y1
    if peaks and abs(peaks[0][0] - y1) <= 8 and peaks[0][1] > 40.0:
        y1 = peaks[0][0]
    # Snap bottom endpoint to the bottom reflective marker if present just below y2
    if peaks and 0 < (peaks[-1][0] - y2) <= 8 and peaks[-1][1] > 35.0:
        y2 = peaks[-1][0]

    x1 = x_top + (dx * y1) / (h - 1)
    x2 = x_top + (dx * y2) / (h - 1)
    euclid_len = float(np.hypot(x2 - x1, y2 - y1))

    # Convert marker y positions into Euclidean distances from the top endpoint (x1, y1)
    marker_dists_px: List[float] = []
    for py, _ in peaks:
        if py >= y1 - 2 and py <= y2 + 2:
            px = x_top + (dx * py) / (h - 1)
            dist = float(np.hypot(px - x1, max(0, py - y1)))
            marker_dists_px.append(dist)

    if debug_img is not None:
        pt1 = (int(round(x1)), y1)
        pt2 = (int(round(x2)), y2)
        color = (0, 255, 0) if is_ir else (0, 0, 255)
        label_prefix = "Night" if is_ir else "Color"
        cv2.line(debug_img, pt1, pt2, color, 2)
        for py, _ in peaks:
            px_i = int(round(x_top + (dx * py) / (h - 1)))
            cv2.circle(debug_img, (px_i, py), 2, (0, 255, 255), -1)
        cv2.circle(debug_img, pt1, 3, (0, 255, 255), -1)
        cv2.circle(debug_img, pt2, 3, (255, 0, 0), -1)
        cv2.putText(
            debug_img,
            f"{label_prefix}: {euclid_len:.1f}px",
            (max(2, pt1[0] - 20), max(15, pt1[1] - 6)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            color,
            1,
        )

    return euclid_len, marker_dists_px


def _measure_snow_depth_color(
    img: np.ndarray,
    stick_colors: List[str],
    debug_img: Optional[np.ndarray] = None,
) -> Optional[float]:
    """
    Detect the snow stick in daylight/color images using local chroma ridge filtering
    and line fitting. Returns the visible length of the stick in pixels, or None.
    """
    if _is_ir_monochrome(img):
        return None
    resp = _compute_color_ridge_response(img, stick_colors)
    length_px, _ = _fit_stick_line_and_measure(
        img, resp, is_ir=False, debug_img=debug_img
    )
    return length_px


def _measure_snow_depth_night(
    img: np.ndarray, debug_img: Optional[np.ndarray] = None
) -> Optional[float]:
    """
    Detect the snow stick in nighttime/IR images using local luminance ridge filtering
    and line fitting. Returns the visible length of the stick in pixels, or None.
    """
    resp = _compute_ir_ridge_response(img)
    length_px, _ = _fit_stick_line_and_measure(
        img, resp, is_ir=True, debug_img=debug_img
    )
    return length_px


def _compute_visible_cm_with_markers(
    detected_length_px: float,
    marker_dists_px: List[float],
    pixels_per_cm: float,
    marker_interval_cm: Optional[float],
) -> float:
    """
    Calculate visible stick length in cm, anchoring to grid-verified reflective
    markers when available to compensate for camera perspective.
    """
    if not marker_interval_cm or marker_interval_cm <= 0 or len(marker_dists_px) < 2:
        return detected_length_px / pixels_per_cm

    expected_step_px = marker_interval_cm * pixels_per_cm
    if expected_step_px < 8.0:
        return detected_length_px / pixels_per_cm

    # Verify markers against the expected interval grid starting from the top (0px)
    valid_markers: List[Tuple[int, float]] = []
    for dist_px in marker_dists_px:
        k = int(round(dist_px / expected_step_px))
        if abs(dist_px - k * expected_step_px) <= 0.25 * expected_step_px:
            if not valid_markers or valid_markers[-1][0] != k:
                valid_markers.append((k, dist_px))

    if len(valid_markers) < 2 or valid_markers[0][0] != 0:
        return detected_length_px / pixels_per_cm

    k_max, dist_max_px = valid_markers[-1]
    if k_max <= 0:
        return detected_length_px / pixels_per_cm

    # Anchor at the lowest visible grid marker and interpolate the remaining tail
    tail_px = max(0.0, detected_length_px - dist_max_px)
    return k_max * marker_interval_cm + (tail_px / pixels_per_cm)


def measure_snow_depth(
    image_bytes: bytes,
    stick_colors: List[str],
    stick_total_cm: float,
    pixels_per_cm: float,
    roi: Optional[Tuple[int, int, int, int]] = None,
    roi_rotation: float = 0.0,
    debug_output_path: Optional[str] = None,
    return_pixels_only: bool = False,
    marker_interval_cm: Optional[float] = None,
) -> Optional[float]:
    arr = np.asarray(bytearray(image_bytes), dtype=np.uint8)
    img = cv2.imdecode(arr, -1)
    if img is None:
        logger.error("Could not decode image bytes for snow depth measurement.")
        return None

    # Handle ROI
    if roi:
        roi_x, roi_y, roi_w, roi_h = roi
        img_h, img_w = img.shape[:2]
        if (
            roi_x >= 0
            and roi_y >= 0
            and roi_w > 0
            and roi_h > 0
            and (roi_x + roi_w) <= img_w
            and (roi_y + roi_h) <= img_h
        ):
            logger.info(f"Applying ROI: x={roi_x}, y={roi_y}, w={roi_w}, h={roi_h}")
            processed_img = img[roi_y : roi_y + roi_h, roi_x : roi_x + roi_w].copy()
        else:
            logger.error(
                f"Invalid ROI dimensions: {roi} for image size {img.shape[:2]}"
            )
            return None
    else:
        processed_img = img

    # Handle optional manual rotation if configured
    if abs(roi_rotation) > 0.1:
        logger.info(f"Rotating ROI by {roi_rotation} degrees")
        h, w = processed_img.shape[:2]
        center = (w // 2, h // 2)
        matrix = cv2.getRotationMatrix2D(center, roi_rotation, 1.0)
        processed_img = cv2.warpAffine(
            processed_img, matrix, (w, h), borderMode=cv2.BORDER_REPLICATE
        )

    debug_img = processed_img.copy() if debug_output_path else None
    marker_dists_px: List[float] = []

    if _is_ir_monochrome(processed_img):
        mode = "Night"
        resp = _compute_ir_ridge_response(processed_img)
        detected_height, marker_dists_px = _fit_stick_line_and_measure(
            processed_img, resp, is_ir=True, debug_img=debug_img
        )
    else:
        mode = "Color"
        resp = _compute_color_ridge_response(processed_img, stick_colors)
        detected_height, marker_dists_px = _fit_stick_line_and_measure(
            processed_img, resp, is_ir=False, debug_img=debug_img
        )
        if not detected_height:
            logger.info(
                "Color detection low-confidence. Attempting Night Mode fallback..."
            )
            resp_ir = _compute_ir_ridge_response(processed_img)
            detected_height, marker_dists_px = _fit_stick_line_and_measure(
                processed_img, resp_ir, is_ir=True, debug_img=debug_img
            )
            mode = "Night"

    if debug_output_path and debug_img is not None:
        if roi:
            full_debug_img = img.copy()
            roi_x, roi_y, roi_w, roi_h = roi
            full_debug_img[roi_y : roi_y + roi_h, roi_x : roi_x + roi_w] = debug_img
            cv2.rectangle(
                full_debug_img,
                (roi_x, roi_y),
                (roi_x + roi_w, roi_y + roi_h),
                (255, 255, 0),
                2,
            )
            cv2.imwrite(debug_output_path, full_debug_img)
        else:
            cv2.imwrite(debug_output_path, debug_img)

        logger.info(f"Saved debug image to {debug_output_path}")

    if detected_height:
        if return_pixels_only:
            return round(detected_height, 1)
        visible_cm = detected_height / pixels_per_cm
        snow_depth_cm = max(0.0, stick_total_cm - visible_cm)
        logger.info(
            f"[{mode} Mode] Detected visible stick length: {detected_height:.1f}px "
            f"({len(marker_dists_px)} markers, {visible_cm:.2f}cm). "
            f"Snow depth: {snow_depth_cm:.2f}cm"
        )
        return round(snow_depth_cm, 2)

    logger.warning(
        "No valid snow stick found for depth measurement (low confidence/obscured)."
    )
    return None
