FROM python:3.11-slim 
RUN apt-get update && apt-get install -y tesseract-ocr libgl1 && rm -rf /var/lib/apt/lists/* 
WORKDIR /app 
COPY requirements.txt . 
RUN pip install --no-cache-dir -r requirements.txt 
COPY . . 
RUN mkdir -p static/uploads 
EXPOSE 5000 
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"] 
