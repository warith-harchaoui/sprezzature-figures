FROM python:3.11-slim

LABEL maintainer="Warith HARCHAOUI <warithmetics@deraison.ai>"
# No catalogue size in this label. It said "162 chart types" against a
# catalogue of 167: the monorepo sweeps every quoted count back to the real
# one (scripts/bump_catalogue_count.py), and this file is in the sibling
# repository, outside that sweep. A number nothing holds to the truth drifts.
LABEL description="sprezzature-figures: CLI + HTTP API + Editor server"

WORKDIR /app

# System deps for the resvg_py rasteriser (libgomp1), and a set of system
# fonts as a last-resort fallback. The typefaces the generators actually name
# — the three Roboto, Latin Modern — ship inside the wheel under
# assets/fonts/ and are handed to resvg explicitly through
# `fonts.RESVG_FONT_DIRS`, so this package is not where the chart text comes
# from; it only covers glyphs those faces do not carry.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgomp1 \
        fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml requirements.txt ./
COPY sprezzature_figures/ ./sprezzature_figures/
COPY scripts/ ./scripts/
COPY assets/ ./assets/

# Same requirements.txt as the local conda env (environment.yaml) — one
# dependency list for both, pyproject.toml stays the real source of truth.
# There are no extras to select since 2026-11-01: the plain install carries
# the CLI, the API, the MCP server and the editor, so this image can run any
# of them.
RUN pip install --no-cache-dir -r requirements.txt

# Non-root user for production use. HOME must point at appuser's own home
# (not root's): anything that caches under $HOME on first use has to land
# somewhere writable, and appuser can't write into /root. the editor's
# project tree is one of those — it defaults to $HOME/.sprezzature-figures.
RUN useradd --create-home appuser
ENV HOME=/home/appuser
USER appuser

EXPOSE 8000

# Serve what the image was built for: the HTTP routes and the MCP endpoint,
# from one process on one port. `sprezzature-figures-mcp` runs the same
# FastAPI app as `uvicorn sprezzature_figures.api:app`, with /mcp mounted
# beside /health, /kinds and /render; the plain uvicorn line this replaces
# served the routes and left an MCP client nothing to connect to. The
# previous default before that was `ENTRYPOINT make-figure` / `CMD --list`:
# a container that starts, prints a catalogue and exits. There is no
# ENTRYPOINT now, so any of the commands replaces this one directly:
#
#   docker run --rm -v "$PWD:/work" IMAGE sprezzature-figures render bellcurve --out /work/bell.svg
#   docker run --rm -p 8080:8080 IMAGE sprezzature-figures --host 0.0.0.0 --no-browser
CMD ["sprezzature-figures-mcp", "--host", "0.0.0.0", "--port", "8000"]
