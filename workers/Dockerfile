FROM python:3.11-slim

WORKDIR /app

# Installazione dipendenze per Playwright e browser
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    yara \
    wget \
    gnupg \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --trusted-host pypi.org --trusted-host files.pythonhosted.org -r requirements.txt

# Installazione dei browser Playwright
RUN playwright install chromium firefox --with-deps

COPY . .

CMD ["celery", "-A", "celery_app", "worker", "--loglevel=info"]
