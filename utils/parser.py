"""
Receipt Text Parser
--------------------
OCR output is unstructured plain text. This module uses regex patterns
and simple heuristics to pull out structured fields: amount, date, merchant.

Why heuristics instead of fixed positions?
Every receipt has a different layout, so we can't assume "total is always
on line 5". Instead we search for patterns (keywords + number formats)
anywhere in the text.
"""

import re
from datetime import datetime


def extract_amount(text):
    """
    Look for total amount using common patterns like:
    'Total: $45.00', 'TOTAL 1200.50', 'Grand Total: ₹350'
    Strategy: search for keyword-anchored amounts first (most reliable),
    fall back to the largest number in the text if no keyword match found.
    """
    # Pattern 1: keyword followed by a currency symbol and number
    keyword_pattern = r'(?:total|grand total|amount due|net amount|amount)\s*[:\-]?\s*[\$₹]?\s*(\d+[.,]?\d*)'
    matches = re.findall(keyword_pattern, text, re.IGNORECASE)

    if matches:
        # Take the last match — totals often appear after subtotals/taxes
        amount_str = matches[-1].replace(',', '')
        try:
            return float(amount_str)
        except ValueError:
            pass

    # Fallback: find all currency-like numbers, return the largest
    # (the total is usually the largest line-item on a receipt)
    all_numbers = re.findall(r'[\$₹]?\s*(\d+\.\d{2})', text)
    if all_numbers:
        try:
            amounts = [float(n) for n in all_numbers]
            return max(amounts)
        except ValueError:
            pass

    return None


def extract_date(text):
    """
    Look for common date formats:
    DD/MM/YYYY, MM-DD-YYYY, DD-MM-YY, YYYY-MM-DD, etc.
    """
    date_patterns = [
        r'\b(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})\b',   # 12/05/2024 or 12-05-24
        r'\b(\d{4}-\d{1,2}-\d{1,2})\b',             # 2024-05-12
    ]

    for pattern in date_patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1)

    return None


def extract_merchant(text):
    """
    Heuristic: the merchant/store name is usually one of the first
    non-empty lines on a receipt (before address/items start).
    """
    lines = [line.strip() for line in text.split('\n') if line.strip()]

    if not lines:
        return None

    # Skip lines that look like dates, numbers only, or are too short
    for line in lines[:5]:  # check first 5 lines only
        if len(line) > 2 and not re.match(r'^[\d\s\-/:.,]+$', line):
            return line

    return lines[0] if lines else None


def parse_receipt_text(raw_text):
    """
    Main entry point: run all extractors and return a structured dict.
    """
    if not raw_text:
        return {"merchant": None, "amount": None, "date": None}

    return {
        "merchant": extract_merchant(raw_text),
        "amount": extract_amount(raw_text),
        "date": extract_date(raw_text),
    }
