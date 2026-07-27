FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8

ARG INSTALL_MODE=local
ENV INSTALL_MODE=${INSTALL_MODE}

ENV PATH="/opt/pipa_harness/bin:/root/.local/share/pipa-harness/bin:/root/.opencode/bin:/root/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    ca-certificates \
    python3 \
    python3-pip \
    jq \
    zstd \
    xdg-utils \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://ollama.com/install.sh | sh || true && \
    command -v ollama >/dev/null || { echo "Ollama binary not found after install"; exit 1; }

RUN pip3 install --break-system-packages --no-cache-dir fastapi uvicorn pyyaml

# Pre-install the core pipa_harness CLI tools so battery tests do not have to
# wait for runtime downloads. uv is installed first; the rest are uv tools.
RUN curl -LsSf https://astral.sh/uv/install.sh | sh && \
    export PATH="/root/.local/bin:$PATH" && \
    uv tool install 'litellm[proxy]' && \
    uv tool install graphifyy --with mcp && \
    curl -fsSL https://opencode.ai/install | bash -s -- --no-modify-path

COPY . /opt/pipa_harness/

WORKDIR /tmp

COPY docker/test-pipa.sh /usr/local/bin/test-pipa.sh
COPY docker/test-battery.sh /usr/local/bin/test-battery.sh
RUN chmod +x /usr/local/bin/test-pipa.sh /usr/local/bin/test-battery.sh

WORKDIR /opt/pipa_harness
ENTRYPOINT ["/usr/local/bin/test-pipa.sh"]
