FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    MCP_TRANSPORT=streamable-http \
    MCP_HOST=0.0.0.0 \
    MCP_PORT=8000

WORKDIR /app

RUN groupadd --gid 10001 rzd \
    && useradd --uid 10001 --gid rzd --no-create-home --shell /usr/sbin/nologin rzd

COPY pyproject.toml README.md LICENSE constraints.txt ./
COPY rzd_api/ rzd_api/
COPY mcp_server/ mcp_server/

RUN python -m pip install --no-cache-dir -c constraints.txt ".[mcp]"

USER 10001:10001
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).read()"

CMD ["rzd-mcp-server"]
