# The canonical way to reproduce the headline result: no local Python, no API key, no network.
#
#   docker build -t caliper .
#   docker run --rm caliper
#
# The default command replays recorded model responses, so the run is offline and free.

FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Dependencies first, so the layer survives edits to the source.
COPY pyproject.toml uv.lock* README.md ./
COPY src ./src
RUN pip install --no-cache-dir -e ".[dev]"

COPY data ./data
COPY eval ./eval
COPY tests ./tests
COPY scripts ./scripts
COPY Makefile ./

RUN python -m caliper.cli data verify

CMD ["python", "-m", "caliper.cli", "eval", "--replay"]
