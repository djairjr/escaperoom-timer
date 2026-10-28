cmake_minimum_required(VERSION 3.20)
project(timer-sdl LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Use pkg-config for everything except nlohmann_json
find_package(PkgConfig REQUIRED)

# SDL2
find_package(SDL2 REQUIRED)
pkg_check_modules(SDL2_TTF REQUIRED SDL2_ttf)
pkg_check_modules(SDL2_MIXER REQUIRED SDL2_mixer)

# libdrm (best display mode)
pkg_check_modules(DRM REQUIRED libdrm)

# libgpiod C++
pkg_check_modules(GPIODCXX REQUIRED libgpiodcxx)

# Paho MQTT
find_package(PahoMqttCpp REQUIRED)
find_package(eclipse-paho-mqtt-c REQUIRED)

# libmicrohttpd
pkg_check_modules(MHD REQUIRED libmicrohttpd)

# nlohmann_json (header-only)
find_package(nlohmann_json REQUIRED)

set(SOURCES
    src/main.cpp
    src/Config.cpp
    src/GameState.cpp
    src/TimerEngine.cpp
    src/GPIOInput.cpp
    src/Display.cpp
    src/Audio.cpp
    src/MQTTClient.cpp
)

add_executable(timer-sdl ${SOURCES})

target_include_directories(timer-sdl PRIVATE src ${SDL2_TTF_INCLUDE_DIRS} ${SDL2_MIXER_INCLUDE_DIRS} ${GPIODCXX_INCLUDE_DIRS} ${MHD_INCLUDE_DIRS} ${DRM_INCLUDE_DIRS})
target_include_directories(timer-sdl SYSTEM PRIVATE ${SDL2_INCLUDE_DIRS})

target_link_libraries(timer-sdl PRIVATE
    SDL2::SDL2
    ${SDL2_TTF_LIBRARIES}
    ${SDL2_MIXER_LIBRARIES}
    ${GPIODCXX_LIBRARIES}
    ${DRM_LIBRARIES}
    PahoMqttCpp::paho-mqttpp3
    eclipse-paho-mqtt-c::paho-mqtt3a
    ${MHD_LIBRARIES}
    nlohmann_json::nlohmann_json
)

target_compile_options(timer-sdl PRIVATE -Wall -Wextra -O2)
