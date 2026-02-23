from typing import Optional

import cv2
import numpy as np
import requests


def brightness(image: np.ndarray, dim: int = 10, thresh: float = 0.5) -> float:
    # Resize image to 10x10
    image = cv2.resize(image, (dim, dim))
    # Convert color space to LAB format and extract L channel
    L, A, B = cv2.split(cv2.cvtColor(image, cv2.COLOR_BGR2LAB))
    # Normalize L channel by dividing all pixel values with maximum pixel value
    if np.max(L) == 0:
        return 0.0
    L = L / np.max(L)
    # Return mean value
    return float(np.mean(L))


def fetch(uri: str) -> Optional[bytes]:
    try:
        response = requests.get(uri, verify=False, stream=False)
        if response.ok:
            return response.content
        else:
            print(
                f"Error: Received status code {response.status_code} "
                f"with message: {response.text}"
            )
            return None
    except requests.RequestException as e:
        print(f"Error fetching {uri}: {e}")
        return None


def process(image_bytes: bytes) -> float:
    arr = np.asarray(bytearray(image_bytes), dtype=np.uint8)
    img = cv2.imdecode(arr, -1)
    if img is None:
        return 0.0
    return round(brightness(img), 3)
