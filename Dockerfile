FROM python:3.11-slim

LABEL maintainer="Warith Harchaoui <warith.harchaoui@gmail.com>"
LABEL description="sprezzature-figures: CLI + Studio server, ~95 chart types"

WORKDIR /app

# System deps for matplotlib (headless) and the resvg_py rasteriser
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgomp1 \
        fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml requirements.txt ./
COPY sprezzature_figures/ ./sprezzature_figures/
COPY scripts/ ./scripts/
COPY assets/ ./assets/

# Same requirements.txt as the local conda env (environment.yaml) — one
# dependency list for both, pyproject.toml's extras stay the real source
# of truth (cli, dataviz, studio: this image can serve the Studio app, not
# just run the CLI).
RUN pip install --no-cache-dir -r requirements.txt

# Non-root user for production use. HOME must point at appuser's own home
# (not root's) — matplotlib's config dir writes there on first use, and
# appuser can't write into /root.
RUN useradd --create-home appuser
ENV HOME=/home/appuser
USER appuser

ENTRYPOINT ["make-figure"]
CMD ["--list"]
