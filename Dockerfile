FROM python:3.13-slim@sha256:e48f59cdba69a3cbd9ed2cf0f348d90d45a8d350d98134cf1070bc106ee9ed90

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app
COPY requirements/api-linux-py313.lock ./requirements/api-linux-py313.lock
RUN --mount=type=cache,target=/root/.cache/pip python -m pip install -r requirements/api-linux-py313.lock
COPY pyproject.toml README.md ./
COPY freight_intelligence ./freight_intelligence
RUN --mount=type=cache,target=/root/.cache/pip python -m pip install --no-deps -e ".[api]" \
    && python -m pip check \
    && python -m freight_intelligence.utils.runtime_lock \
    && mkdir -p /app/data/gold/faf5 /app/models/faf5/annual /app/artifacts

USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)"
CMD ["python", "-m", "uvicorn", "freight_intelligence.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
