"""
Expense Categorizer
--------------------
Simple rule-based categorization using keyword matching.

This is intentionally simple (good interview talking point: "I started
with rule-based matching, and the natural next step would be a trained
ML text classifier once I have enough labeled data").
"""

CATEGORY_KEYWORDS = {
    "Food & Dining": [
        "swiggy", "zomato", "restaurant", "cafe", "pizza", "burger",
        "food", "kitchen", "dine", "starbucks", "mcdonald", "kfc", "domino"
    ],
    "Transport": [
        "uber", "ola", "taxi", "fuel", "petrol", "diesel", "metro",
        "parking", "toll", "rapido"
    ],
    "Groceries": [
        "supermarket", "grocery", "mart", "bigbasket", "reliance fresh",
        "dmart", "more"
    ],
    "Shopping": [
        "amazon", "flipkart", "myntra", "mall", "store", "shop"
    ],
    "Utilities": [
        "electricity", "water bill", "broadband", "recharge", "mobile bill",
        "wifi"
    ],
    "Healthcare": [
        "pharmacy", "hospital", "clinic", "medical", "medicine", "doctor"
    ],
    "Entertainment": [
        "netflix", "movie", "cinema", "pvr", "inox", "bookmyshow", "spotify"
    ],
}


def categorize_expense(merchant, raw_text):
    """
    Check merchant name and full raw text against keyword lists.
    Returns the first matching category, or 'Uncategorized' if none match.
    """
    combined_text = f"{merchant or ''} {raw_text or ''}".lower()

    for category, keywords in CATEGORY_KEYWORDS.items():
        for keyword in keywords:
            if keyword in combined_text:
                return category

    return "Uncategorized"
