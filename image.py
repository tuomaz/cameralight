import requests
import cv2
from requests.auth import HTTPDigestAuth
from PIL import Image
from io import BytesIO
import numpy as np
import random
import time

def brightness(image, dim=10, thresh=0.5):
    # Resize image to 10x10
    image = cv2.resize(image, (dim, dim))
    # Convert color space to LAB format and extract L channel
    L, A, B = cv2.split(cv2.cvtColor(image, cv2.COLOR_BGR2LAB))
    # Normalize L channel by dividing all pixel values with maximum pixel value
    L = L/np.max(L)
    # Return mean value
    return np.mean(L)

def fetch(uri):
    response = requests.get(uri, verify=False, stream=False)
    if response.ok:
        return response.content
    else :
       return f"Error: Received status code {response.status_code} with message: {response.text}"

def process(image_bytes):
    arr = np.asarray(bytearray(image_bytes), dtype=np.uint8)
    img = cv2.imdecode(arr, -1)
    return round(brightness(img), 3)
