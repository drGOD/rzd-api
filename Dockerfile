FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml .
COPY rzd_api/ rzd_api/
COPY mcp_server/ mcp_server/

RUN pip install --no-cache-dir .

ENV MCP_TRANSPORT=streamable-http
ENV MCP_HOST=0.0.0.0
ENV MCP_PORT=8000

EXPOSE 8000

CMD ["rzd-mcp-server"]
