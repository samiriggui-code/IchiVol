# mt5-bridge -- Wine + MetaTrader5 terminal + mt5linux (RPyC) + FastAPI wrapper.
#
# HONESTY NOTE (read before deploying): this Dockerfile could not be built or
# run in the environment this was written in (no Wine/Windows sandbox
# available) -- it encodes the standard, documented approach for running the
# MetaTrader5 python package on Linux (scottyhardy/docker-wine base +
# mt5linux, github.com/lucas-campagna/mt5linux), but the exact Wine bootstrap
# commands are the one part that must be smoke-tested and iterated on the
# real VPS. See README.md "Verification checklist" -- treat the first build
# as a debugging session, not a known-working artifact.
#
# Deliberately its own image, never merged into ichivol-engine's Dockerfile:
# this is the only container in the whole stack allowed to depend on
# Wine/MT5 at all (docs/TRADING_ARCHITECTURE_V2.md §11 -- MT5 must never be
# a dependency the core engine needs to boot).

FROM scottyhardy/docker-wine:stable

USER root
ENV DEBIAN_FRONTEND=noninteractive \
    WINEARCH=win64 \
    WINEPREFIX=/root/.wine \
    WINEDEBUG=-all

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        python3 python3-pip python3-venv curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Native Linux side: FastAPI wrapper + mt5linux's pure-python client.
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

COPY bridge_server.py symbol_map.py docker-entrypoint.sh ./
RUN chmod +x docker-entrypoint.sh

# Windows side (runs under Wine): installed at container FIRST START, not
# build time, by docker-entrypoint.sh -- pulling installers at build time
# would bake broker-specific state into the image layer cache, and the MT5
# terminal + Windows Python installers need network access anyway. The
# persisted `/root/.wine` volume (see docker-compose.yml's
# `ichivol_mt5_wine` volume) means this one-time setup survives container
# restarts/upgrades.

EXPOSE 8000
ENTRYPOINT ["/app/docker-entrypoint.sh"]
