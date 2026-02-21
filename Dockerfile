FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Move HTML files into static/ if not already there
RUN mkdir -p static && \
    cp -n index.html static/index.html 2>/dev/null || true && \
    cp -n landing.html static/landing.html 2>/dev/null || true

EXPOSE 7860

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860"]
