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

def measure_snow_depth(
    image_bytes: bytes,
    stick_colors: List[str],
    stick_total_cm: float,
    pixels_per_cm: float,
) -> Optional[float]:
    
    arr = np.asarray(bytearray(image_bytes), dtype=np.uint8)
    img = cv2.imdecode(arr, -1)
    if img is None:
        logger.error("Could not decode image bytes for snow depth measurement.")
        return None

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

    if best_candidate_height > 0:
        visible_cm = best_candidate_height / pixels_per_cm
        snow_depth_cm = stick_total_cm - visible_cm
        logger.info(f"Detected visible stick height: {best_candidate_height}px, which is {visible_cm:.2f}cm. Snow depth: {snow_depth_cm:.2f}cm")
        return round(snow_depth_cm, 2)
    else:
        logger.warning("No valid snow stick found for depth measurement.")
        return None
