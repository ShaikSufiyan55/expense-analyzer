"""
OCR Processor
-------------
Handles image preprocessing (to improve OCR accuracy) and text extraction
using pytesseract.

Why preprocessing matters:
Raw receipt photos often have noise, shadows, skew, or low contrast.
Tesseract performs much better on clean, high-contrast, grayscale images.
"""

import cv2
import pytesseract
from PIL import Image

# Point pytesseract to the Tesseract OCR engine installed on Windows.
# If Tesseract is installed elsewhere, update this path to match.
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'


def preprocess_image(image_path):
    """
    Apply preprocessing steps to improve OCR accuracy:
    1. Convert to grayscale
    2. Apply thresholding (binarization) to increase contrast
    3. Denoise the image
    """
    img = cv2.imread(image_path)

    if img is None:
        raise ValueError(f"Could not read image at {image_path}")

    # Convert to grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Denoise
    denoised = cv2.fastNlMeansDenoising(gray, h=30)

    # Adaptive thresholding works well for receipts with uneven lighting
    thresh = cv2.adaptiveThreshold(
        denoised, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        11, 2
    )

    return thresh


def extract_text_from_image(image_path):
    """
    Main entry point: preprocess the image, then run Tesseract OCR.
    Returns raw extracted text as a string.
    """
    try:
        processed_img = preprocess_image(image_path)

        # pytesseract works with PIL Images or numpy arrays directly
        raw_text = pytesseract.image_to_string(processed_img)

        return raw_text.strip()

    except Exception as e:
        print(f"OCR extraction failed: {e}")
        # Fallback: try OCR on the raw image without preprocessing
        try:
            raw_text = pytesseract.image_to_string(Image.open(image_path))
            return raw_text.strip()
        except Exception as fallback_error:
            print(f"Fallback OCR also failed: {fallback_error}")
            return ""
