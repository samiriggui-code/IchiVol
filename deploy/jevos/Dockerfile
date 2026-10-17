# jevos-v4 — JEV local (github.com/feder-cr/jev, MIT), CPU only, ~1 GB RAM.
# Ève's fallback when the hosted JEV refuses a call, and the judge of the EVE_JEVOS_V1 paper account.
FROM ubuntu:24.04
ARG JEV_RELEASE=jevos-v4
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates curl unzip \
 && rm -rf /var/lib/apt/lists/*
WORKDIR /opt
RUN curl -fsSL "https://github.com/feder-cr/jev/releases/download/${JEV_RELEASE}/jev-linux-x64.tar.gz" | tar -xz \
 && curl -fsSL -o /tmp/model.zip "https://github.com/feder-cr/jev/releases/download/${JEV_RELEASE}/jevos-v4-openvino-int8.zip" \
 && cd /opt/jev && unzip -q /tmp/model.zip && rm /tmp/model.zip
WORKDIR /opt/jev
EXPOSE 8017
# The model takes about a minute to load on first start.
HEALTHCHECK --interval=30s --timeout=5s --start-period=180s --retries=3 \
  CMD curl -fsS http://127.0.0.1:8017/health || exit 1
CMD ["./jev", "serve", "--host", "0.0.0.0", "--port", "8017"]
