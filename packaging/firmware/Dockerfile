# Cross-build environment for timer-sdl: the boards' distribution (Debian 13 trixie) with the armhf
# libraries from the same archive, so the binary links against the versions installed on them.
FROM debian:trixie
RUN dpkg --add-architecture armhf \
 && apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      crossbuild-essential-armhf cmake pkg-config file dpkg-dev \
      libsdl2-dev:armhf libsdl2-ttf-dev:armhf libsdl2-mixer-dev:armhf \
      libgpiod-dev:armhf libmicrohttpd-dev:armhf nlohmann-json3-dev \
      libpaho-mqttpp-dev:armhf libpaho-mqtt-dev:armhf libssl-dev:armhf \
 && rm -rf /var/lib/apt/lists/*
