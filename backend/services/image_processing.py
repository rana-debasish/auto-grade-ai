"""Image Processing Module — Memory-optimized preprocessing for Render free tier."""

import gc

import cv2
import numpy as np

# Maximum image dimension to prevent memory issues on 512MB RAM
MAX_IMAGE_DIM = 1200


def preprocess_image(image_path):
    """
    Preprocess an answer script image for text extraction.
    
    Optimized pipeline for low memory:
    1. Read and resize image (limit dimensions)
    2. Convert to grayscale
    3. Light denoising
    4. Adaptive thresholding
    5. Memory cleanup

    Returns: preprocessed image as numpy array
    """
    # Read image
    image = cv2.imread(image_path)
    if image is None:
        raise ValueError(f"Could not read image: {image_path}")

    # Resize early to save memory
    image = resize_if_needed(image, MAX_IMAGE_DIM)
    
    # Convert to grayscale
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    del image  # Free memory
    
    # Light denoising (reduced parameters for speed and memory)
    denoised = cv2.fastNlMeansDenoising(gray, h=8, templateWindowSize=5,
                                         searchWindowSize=15)
    del gray
    
    # Increase contrast using CLAHE
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(denoised)
    del denoised
    
    # Adaptive thresholding
    binary = cv2.adaptiveThreshold(
        enhanced, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        blockSize=11,
        C=2
    )
    del enhanced
    
    # Skip deskew to save memory (minimal impact on text extraction)
    gc.collect()
    
    return binary


def resize_if_needed(image, max_dim=MAX_IMAGE_DIM):
    """Resize large images to fit within max dimension (preserves aspect ratio)."""
    h, w = image.shape[:2]
    
    if max(h, w) <= max_dim:
        return image
    
    if w > h:
        scale = max_dim / w
        new_size = (max_dim, int(h * scale))
    else:
        scale = max_dim / h
        new_size = (int(w * scale), max_dim)
    
    resized = cv2.resize(image, new_size, interpolation=cv2.INTER_AREA)
    return resized


def get_image_size_mb(image):
    """Get approximate memory size of image in MB."""
    return image.nbytes / (1024 * 1024)
