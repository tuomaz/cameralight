import cv2
import numpy as np
from typing import Optional, Tuple, List
import logging

logger = logging.getLogger(__name__)

def hex_to_hsv(hex_color: str) -> Tuple[int, int, int]:
    hex_color = hex_color.lstrip('#')
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    
    pixel = np.uint8([[[b, g, r]]]) 
    hsv = cv2.cvtColor(pixel, cv2.COLOR_BGR2HSV)
    return hsv[0][0]

def get_mask_for_color(hsv_img: np.ndarray, hex_color: str, tolerance: int = 50) -> np.ndarray:
    target_hsv = hex_to_hsv(hex_color)
    h_val, s_val, v_val = target_hsv
    
    # Wider range for S and V to catch more shades, H range kept smaller for color specificity
    lower_bound = np.array([max(0, h_val - 15), max(10, s_val - tolerance), max(10, v_val - tolerance)])
    upper_bound = np.array([min(179, h_val + 15), min(255, s_val + tolerance + 60), min(255, v_val + tolerance + 120)])
    
    return cv2.inRange(hsv_img, lower_bound, upper_bound)

def _measure_snow_depth_color(img: np.ndarray, stick_colors: List[str], debug_img: Optional[np.ndarray] = None) -> Optional[int]:
    """
    Attempts to find the snow stick using color segmentation.
    Returns the height of the detected stick in pixels, or None if not found.
    """
    hsv_img = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    combined_mask = np.zeros(img.shape[:2], dtype="uint8")
    
    for hex_code in stick_colors:
        mask = get_mask_for_color(hsv_img, hex_code)
        combined_mask = cv2.bitwise_or(combined_mask, mask)

    # Noise reduction and gap closing
    kernel_open = np.ones((5, 5), np.uint8) 
    kernel_close = np.ones((7, 7), np.uint8) 
    
    combined_mask = cv2.morphologyEx(combined_mask, cv2.MORPH_OPEN, kernel_open, iterations=1)
    combined_mask = cv2.morphologyEx(combined_mask, cv2.MORPH_CLOSE, kernel_close, iterations=2)
    
    contours, _ = cv2.findContours(combined_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    best_candidate = None
    best_candidate_height = 0

    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < 300: 
            continue
            
        x, y, w, h = cv2.boundingRect(cnt)
        aspect_ratio = float(h) / w
        
        if aspect_ratio > 2.5 and h > 100:
            if h > best_candidate_height:
                best_candidate_height = h
                best_candidate = (x, y, w, h)

    if best_candidate and debug_img is not None:
         x, y, w, h = best_candidate
         cv2.rectangle(debug_img, (x, y), (x + w, y + h), (0, 0, 255), 3)
         cv2.putText(debug_img, f"Color: {h}px", (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 2)

    return best_candidate_height if best_candidate_height > 0 else None

def _measure_snow_depth_night(img: np.ndarray, debug_img: Optional[np.ndarray] = None) -> Optional[int]:
    """
    Attempts to find the snow stick using vertical edge detection (Night Mode).
    Returns the height of the detected stick in pixels, or None if not found.
    """
    # Convert to grayscale
    if len(img.shape) == 3:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    else:
        gray = img

    # Enhance Contrast (CLAHE)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
    enhanced_gray = clahe.apply(gray)
    
    # Statistical Thresholding: Pixels brighter than mean + 1 stddev are considered part of the stick.
    # This works well if the stick is consistently brighter than its immediate surroundings.
    mean, std = cv2.meanStdDev(enhanced_gray)
    thresh_val = mean[0][0] + (std[0][0] * 1.0) # 1 sigma above mean
    _, binary_vertical = cv2.threshold(enhanced_gray, thresh_val, 255, cv2.THRESH_BINARY)
    
    # Morphological Operations (Vertical Kernel) - keep these as they connect segments and clean noise
    # Increased kernel height to 30 to better connect fragmented stick segments
    vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 30)) 
    connected_verticals = cv2.morphologyEx(binary_vertical, cv2.MORPH_CLOSE, vertical_kernel, iterations=2)
    
    # Clean noise
    # Removed OPEN operation as it was eroding thin stick segments too much.
    # open_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    # cleaned_verticals = cv2.morphologyEx(connected_verticals, cv2.MORPH_OPEN, open_kernel, iterations=1)
    
    contours, _ = cv2.findContours(connected_verticals, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    best_candidate = None
    best_candidate_height = 0
    img_h, img_w = img.shape[:2]

    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        
        # Basic filters
        if h < 10: continue # Relaxed min height
        
        # Width check
        # In a tight ROI, the stick might be a large portion of the width.
        # So we relax this significantly.
        # But we still don't want something that is purely horizontal.
        # if w > (img_w * 0.90): continue 
        
        aspect_ratio = float(h) / w
        
        # Stick check
        # Relaxed aspect ratio because noise or reflections might make it look wider
        if aspect_ratio > 1.5:
            if h > best_candidate_height:
                best_candidate_height = h
                best_candidate = (x, y, w, h)
    
    if best_candidate and debug_img is not None:
         x, y, w, h = best_candidate
         cv2.rectangle(debug_img, (x, y), (x + w, y + h), (0, 255, 0), 2)
         cv2.putText(debug_img, f"Night: {h}px", (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)

    return best_candidate_height if best_candidate_height > 0 else None


def measure_snow_depth(
    image_bytes: bytes,
    stick_colors: List[str],
    stick_total_cm: float,
    pixels_per_cm: float,
    roi: Optional[Tuple[int, int, int, int]] = None,
    roi_rotation: float = 0.0,
    debug_output_path: Optional[str] = None,
) -> Optional[float]:
    
    arr = np.asarray(bytearray(image_bytes), dtype=np.uint8)
    img = cv2.imdecode(arr, -1)
    if img is None:
        logger.error("Could not decode image bytes for snow depth measurement.")
        return None

    # Handle ROI
    if roi:
        roi_x, roi_y, roi_w, roi_h = roi
        # Validate ROI
        img_h, img_w = img.shape[:2]
        if roi_x >= 0 and roi_y >= 0 and roi_w > 0 and roi_h > 0 and \
           (roi_x + roi_w) <= img_w and (roi_y + roi_h) <= img_h:
            
            logger.info(f"Applying ROI: x={roi_x}, y={roi_y}, w={roi_w}, h={roi_h}")
            processed_img = img[roi_y:roi_y+roi_h, roi_x:roi_x+roi_w].copy()
        else:
             logger.error(f"Invalid ROI dimensions: {roi} for image size {img.shape[:2]}")
             return None
    else:
        processed_img = img

    # Handle Rotation
    # This is useful if the stick is leaning. We rotate the ROI so the stick becomes vertical,
    # improving the vertical edge detection and morphology.
    if abs(roi_rotation) > 0.1:
         logger.info(f"Rotating ROI by {roi_rotation} degrees")
         h, w = processed_img.shape[:2]
         center = (w // 2, h // 2)
         # Positive angle = Counter-clockwise
         M = cv2.getRotationMatrix2D(center, roi_rotation, 1.0)
         # Use borderReplicate to avoid black borders affecting edge detection
         processed_img = cv2.warpAffine(processed_img, M, (w, h), borderMode=cv2.BORDER_REPLICATE)

    debug_img = processed_img.copy() if debug_output_path else None

    # 1. Try Color Mode
    detected_height = _measure_snow_depth_color(processed_img, stick_colors, debug_img)
    
    mode = "Color"
    
    # 2. If Color Mode fails, Try Night Mode
    if not detected_height:
        logger.info("Color detection failed. Attempting Night Mode (Vertical Edge Detection)...")
        detected_height = _measure_snow_depth_night(processed_img, debug_img)
        mode = "Night"

    if debug_output_path and debug_img is not None:
        if roi:
            # If we used ROI, we want to draw the result on the FULL image for context
            full_debug_img = img.copy()
            roi_x, roi_y, roi_w, roi_h = roi
            
            # Draw ROI box
            cv2.rectangle(full_debug_img, (roi_x, roi_y), (roi_x+roi_w, roi_y+roi_h), (255, 255, 0), 2)
            
            # Paste the debugged crop back (optional, or just draw on top)
            # A better way for visualization is to take the debug_img (which has the green/red detection box)
            # and overlay it back onto the full image.
            full_debug_img[roi_y:roi_y+roi_h, roi_x:roi_x+roi_w] = debug_img
            
            cv2.imwrite(debug_output_path, full_debug_img)
        else:
            cv2.imwrite(debug_output_path, debug_img)
            
        logger.info(f"Saved debug image to {debug_output_path}")

    if detected_height:
        visible_cm = detected_height / pixels_per_cm
        snow_depth_cm = stick_total_cm - visible_cm
        logger.info(f"[{mode} Mode] Detected visible stick height: {detected_height}px, which is {visible_cm:.2f}cm. Snow depth: {snow_depth_cm:.2f}cm")
        return round(snow_depth_cm, 2)
    else:
        logger.warning("No valid snow stick found for depth measurement (tried Color and Night modes).")
        return None