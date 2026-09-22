FROM python:3.11-slim

# tesseract-ocr: OCR on embedded images (pytesseract calls it via PATH, no TESSERACT_CMD needed on Linux)
# libgl1: required by opencv/pillow-backed image codecs pulled in transitively
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# requirements.lock.txt is a full `pip freeze` of a working local venv (exact versions for
# every transitive dep). Installing from it skips pip's resolver entirely, which otherwise
# backtracks for many minutes on deepeval's unpinned llama-index dependency chain.
COPY requirements.lock.txt .
RUN pip install --no-cache-dir -r requirements.lock.txt --extra-index-url https://download.pytorch.org/whl/cpu

COPY . .

EXPOSE 8600

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8600"]
