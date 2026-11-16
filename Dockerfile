# numcheck MCP server for ChatGPT, Claude and other remote MCP clients.
#   docker build -t numcheck-mcp .
#   docker run -p 8765:8765 numcheck-mcp      -> http://localhost:8765/mcp
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HOST=0.0.0.0 PORT=8765
WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install --no-cache-dir ".[pdf]" && useradd --create-home app
USER app

EXPOSE 8765
HEALTHCHECK --interval=60s --timeout=5s CMD python -c "import urllib.request,os; urllib.request.urlopen('http://127.0.0.1:%s/health' % os.environ['PORT'])"
CMD ["numcheck-mcp", "--http"]
