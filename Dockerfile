# syntax=docker/dockerfile:1

FROM ghcr.io/linuxserver/baseimage-ubuntu:noble

# set version label
ARG BUILD_DATE
ARG VERSION
ARG CODE_RELEASE
LABEL build_version="Linuxserver.io version:- ${VERSION} Build-date:- ${BUILD_DATE}"
LABEL maintainer="aptalca"

# environment settings
ARG DEBIAN_FRONTEND="noninteractive"
ENV HOME="/config"

RUN \
  echo "**** install runtime dependencies ****" && \
  apt-get update && \
  apt-get install -y \
    git \
    libatomic1 \
    nano vim \
    build-essential cmake clang-14 \
    zsh \
    net-tools \
    python3.12 python3-pip libpcap-dev iproute2 \
    iproute2 udhcpd \
    libglib2.0-dev \
    libfdt-dev \
    libpixman-1-dev \
    zlib1g-dev \
    ninja-build libslirp-dev \
    gdb-multiarch \
    libspice-protocol-dev libspice-server-dev \
    libsdl2-dev \
    libgtk-3-dev \
    sudo && \
  echo "**** install code-server ****" && \
  if [ -z ${CODE_RELEASE+x} ]; then \
    CODE_RELEASE=$(curl -sX GET https://api.github.com/repos/coder/code-server/releases/latest \
      | awk '/tag_name/{print $4;exit}' FS='[""]' | sed 's|^v||'); \
  fi && \
  mkdir -p /app/code-server && \
  curl -o \
    /tmp/code-server.tar.gz -L \
    "https://github.com/coder/code-server/releases/download/v${CODE_RELEASE}/code-server-${CODE_RELEASE}-linux-amd64.tar.gz" && \
  tar xf /tmp/code-server.tar.gz -C \
    /app/code-server --strip-components=1 && \
  printf "Linuxserver.io version: ${VERSION}\nBuild-date: ${BUILD_DATE}" > /build_version && \
  echo "**** clean up ****" && \
  apt-get clean && \
  rm -rf \
    /config/* \
    /tmp/* \
    /var/lib/apt/lists/* \
    /var/tmp/*

# Download and install nvm:
RUN echo "*** install npm ****" && \
  curl -o /tmp/install.sh https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh && \
  chmod +x /tmp/install.sh && \
  mkdir -p /app && export HOME=/app && /tmp/install.sh && \
  export NVM_DIR="$HOME/.nvm" && \
  [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh" && \
  [ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"  && \
  nvm install 22 && \
  node -v && \
  npm -v && \
  rm -rf /tmp/*
  
# Setup opencis-manager-ui
RUN echo "*** Setup SWITCH manager UI***" && \
  mkdir -p /app && git clone https://github.com/opencis/opencis-manager-ui.git /app/opencis-manager-ui && \
  cd /app/opencis-manager-ui &&  \
  export HOME=/app && export NVM_DIR="$HOME/.nvm" && \
  [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh" && \
  [ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"  && \  
  echo NEXT_PUBLIC_SOCKET_URL={host} > .env.production && npm install && npm run build

RUN update-alternatives --install /usr/bin/python python /usr/bin/python3.12 2 && \
  update-alternatives --install /usr/bin/clang++ clang++ /usr/bin/clang++-14 100 && \
  update-alternatives --install /usr/bin/clang clang /usr/bin/clang-14 100

RUN apt update && \
    apt install -y python3.12-venv libpcap-dev iproute2 && \
    echo "*** clean up ***" && \
    apt-get clean && \
    rm -rf \
    /config/* \
    /tmp/* \
    /var/lib/apt/lists/* \
    /var/tmp/*

COPY ./opencxl-core /app/opencxl-core

RUN echo "*** Setting Poetry pakcages for Opencxl-core ***" && \
  mkdir -p /app/opencxl-core/ && cd /app/opencxl-core/ && \
  python -m venv cxl && \. /app/opencxl-core/cxl/bin/activate && \
  pip install poetry==1.8.0  && \
  poetry lock && poetry install

# Setup environment
RUN  echo '\. /app/opencxl-core/cxl/bin/activate' >> /root/.bashrc
RUN echo 'export NVM_DIR="/app/.nvm" && [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh" && [ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"' >> /root/.bashrc
RUN echo 'export PATH=/opt/tools/ARMCompiler6.16/bin/:$PATH' >> /root/.bashrc
RUN echo 'export LM_LICENSE_FILE=1700@107.110.204.247,1700@107.110.204.248,1700@107.110.204.254,27000@10.227.121.100' >> /root/.bashrc

# add local files
COPY /root /

# ports and volumes
EXPOSE 8443
