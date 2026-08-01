# Smart Expense / Receipt Analyzer

A Flask + MongoDB app that extracts structured expense data from receipt
photos using OCR (Tesseract), then categorizes and visualizes spending.

## How it works (pipeline)

1. User uploads a receipt image
2. Image is preprocessed with OpenCV (grayscale, denoise, threshold) to
   improve OCR accuracy
3. Tesseract OCR extracts raw text from the cleaned image
4. Regex-based parser pulls out merchant, amount, and date from the
   unstructured text
5. Rule-based keyword matching assigns a spending category
6. Result is stored in MongoDB and shown on the dashboard with charts

## Setup

### 1. Install Tesseract OCR (the actual OCR engine — separate from the Python library)

**Windows:**
Download installer from: https://github.com/UB-Mannheim/tesseract/wiki
After installing, note the install path (usually `C:\Program Files\Tesseract-OCR\tesseract.exe`)
and add this line near the top of `utils/ocr_processor.py`:
```python
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
```

**Mac:**
```bash
brew install tesseract
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt-get install tesseract-ocr
```

### 2. Install MongoDB

Easiest option: use **MongoDB Atlas** (free cloud tier) — no local install needed.
- Create a free cluster at https://www.mongodb.com/cloud/atlas
- Get your connection string
- Replace this line in `app.py`:
  ```python
  client = MongoClient("mongodb://localhost:27017/")
  ```
  with your Atlas connection string:
  ```python
  client = MongoClient("mongodb+srv://<user>:<password>@yourcluster.mongodb.net/")
  ```

Or install MongoDB locally: https://www.mongodb.com/try/download/community

### 3. Install Python dependencies

```bash
python -m venv venv
source venv/bin/activate   # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 4. Run the app

```bash
python app.py
```

Visit `http://localhost:5000` to upload receipts, and
`http://localhost:5000/dashboard` to see analytics.

## Project structure

```
expense-analyzer/
├── app.py                  # Flask routes & MongoDB logic
├── requirements.txt
├── utils/
│   ├── ocr_processor.py    # Image preprocessing + OCR
│   ├── parser.py           # Regex extraction of amount/date/merchant
│   └── categorizer.py      # Keyword-based category assignment
├── templates/
│   ├── index.html          # Upload page
│   └── dashboard.html      # Analytics dashboard
└── static/uploads/         # Saved receipt images
```

## Things to mention in an interview

- **Why preprocessing matters**: raw photos have noise/shadows/skew;
  grayscale + adaptive thresholding significantly improves Tesseract's
  accuracy.
- **Why regex/heuristics instead of fixed positions**: every receipt has
  a different layout, so parsing has to be pattern-based, not position-based.
- **Why MongoDB**: receipt data is semi-structured and varies a lot between
  merchants — a flexible schema is a better fit than rigid SQL tables.
- **Known limitation**: OCR isn't 100% accurate, so the app flags low-confidence
  extractions (`needs_review`) and lets users manually correct them — this
  is a realistic production pattern (human-in-the-loop validation).
- **Next steps to mention**: swap rule-based categorization for a trained
  ML text classifier once enough labeled data exists; add multi-currency
  support; add user authentication for multi-user support.
