FROM python:3.11-slim

LABEL maintainer="Warith Harchaoui <warith.harchaoui@gmail.com>"
LABEL description="sprezzature-figures: 84 chart types as a CLI command"

# vl-convert requires a writeable home for font caching
ENV HOME=/root
WORKDIR /app

# System deps for matplotlib (headless) and vl-convert
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgomp1 \
        fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY sprezzature_figures/ ./sprezzature_figures/
COPY scripts/ ./scripts/
COPY assets/ ./assets/

RUN pip install --no-cache-dir -e ".[cli]"

# Non-root user for production use
RUN useradd --create-home appuser
USER appuser

ENTRYPOINT ["make-figure"]
CMD ["--list"]
