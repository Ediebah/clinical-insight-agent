# Container for the Clinical Insight Agent (Streamlit). Portable across Cloud Run / Hugging Face
# Spaces (Docker) / Render / Railway / Fly. The OpenAI key is supplied at RUNTIME as the
# OPENAI_API_KEY env var — it is never baked into the image.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false \
    PORT=8080

WORKDIR /app

# Install the lean runtime deps first (cached layer). The requirements file installs both local
# libraries, so their source directories must be present before pip resolves the requirements.
COPY requirements.txt .
COPY packages/caveat packages/caveat
COPY packages/assurance packages/assurance
RUN python -m pip install --upgrade pip==26.2.2 && \
    python -m pip install -r requirements.txt

# App code + the committed slim demo warehouse. The full 200MB DB is excluded via .dockerignore,
# so warehouse._resolve_db_path() falls back to data/healthcare_demo.duckdb.
COPY . .

# Run as a non-root user: nothing here needs root, and any RCE in the large dependency surface
# (plotly, vl-convert, duckdb) should not get it for free. The app appends to /app/logs at runtime.
RUN useradd --create-home appuser && chown -R appuser /app
USER appuser

EXPOSE 8080

# Restart a wedged Streamlit process: the built-in health endpoint answers when the server loop is
# alive. Uses python (already in the image) — slim has no curl.
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import os,urllib.request;urllib.request.urlopen(f'http://localhost:{os.environ.get(\"PORT\",\"8080\")}/_stcore/health', timeout=4)"

# Shell form so ${PORT} expands at runtime (Cloud Run / Render / Railway inject PORT; default 8080).
# Retain Streamlit's CORS and XSRF protections. Configure a trusted proxy for the deployment.
CMD streamlit run app.py \
    --server.port=${PORT:-8080} \
    --server.address=0.0.0.0 \
    --server.headless=true
