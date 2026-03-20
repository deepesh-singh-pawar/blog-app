# ── Stage 1: base image ───────────────────────────────────────────────────────
FROM python:3.12-slim

# Keeps Python from buffering stdout/stderr so logs appear immediately
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# ── System deps ───────────────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# ── Working directory ─────────────────────────────────────────────────────────
WORKDIR /app

# ── Install Python dependencies first (better layer caching) ──────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir gunicorn==22.0.0

# ── Copy application code ─────────────────────────────────────────────────────
COPY app.py .
COPY app/ app/

# ── Create a folder for the SQLite database file ──────────────────────────────
RUN mkdir -p /data

# ── Non-root user for security ────────────────────────────────────────────────
RUN adduser --disabled-password --gecos "" bloguser \
    && chown -R bloguser:bloguser /app /data
USER bloguser

# ── Environment defaults (override with -e or docker-compose) ─────────────────
ENV SECRET_KEY="change-me-in-production" \
    DATABASE_URL="sqlite:////data/blog.db" \
    FLASK_ENV="production"

# ── Expose port ───────────────────────────────────────────────────────────────
EXPOSE 5000

# ── Health check ──────────────────────────────────────────────────────────────
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/health')"

# ── Start with gunicorn ───────────────────────────────────────────────────────
CMD ["gunicorn", \
     "--bind", "0.0.0.0:5000", \
     "--workers", "2", \
     "--threads", "2", \
     "--timeout", "60", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "app:app"]
