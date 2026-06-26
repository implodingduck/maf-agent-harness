# Hosted Agent container for the MAF agent harness.
# Serves the Responses protocol on port 8088.

FROM python:3.12-slim

WORKDIR /app

# bash is required by the LocalShellTool harness on Linux.
RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies first for better layer caching.
COPY requirements.txt .
RUN pip install --no-cache-dir --pre -r requirements.txt

# Application code.
COPY main.py .

# Hosted agent listens on 8088.
EXPOSE 8088

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8088/health')" || exit 1

CMD ["python", "main.py"]
