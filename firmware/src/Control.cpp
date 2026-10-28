#include "Control.h"
#include <cerrno>
#include <cstdio>
#include <cstring>
#include <iostream>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/un.h>
#include <unistd.h>

static const char* DIR_PATH = "/run/timer-nicolau";
static const char* SOCK_PATH = "/run/timer-nicolau/control.sock";
static const char* STATE_PATH = "/run/timer-nicolau/game.json";
static const char* STATE_TMP = "/run/timer-nicolau/game.json.tmp";

Control::~Control() {
    if (fd >= 0) close(fd);
    unlink(SOCK_PATH);
}

bool Control::init() {
    mkdir(DIR_PATH, 0755);
    fd = socket(AF_UNIX, SOCK_DGRAM | SOCK_NONBLOCK | SOCK_CLOEXEC, 0);
    if (fd < 0) { std::cerr << "Control socket: " << strerror(errno) << std::endl; return false; }
    sockaddr_un addr{};
    addr.sun_family = AF_UNIX;
    snprintf(addr.sun_path, sizeof(addr.sun_path), "%s", SOCK_PATH);
    unlink(SOCK_PATH);
    if (bind(fd, reinterpret_cast<sockaddr*>(&addr), sizeof(addr)) < 0) {
        std::cerr << "Control bind: " << strerror(errno) << std::endl;
        close(fd); fd = -1;
        return false;
    }
    // The web configurator runs as another user; it only gets to send the one allowed word.
    chmod(SOCK_PATH, 0666);
    return true;
}

std::string Control::poll() {
    if (fd < 0) return "";
    char buf[32];
    ssize_t n = recv(fd, buf, sizeof(buf) - 1, 0);
    if (n <= 0) return "";
    buf[n] = '\0';
    std::string s(buf);
    while (!s.empty() && (s.back() == '\n' || s.back() == '\r' || s.back() == ' ')) s.pop_back();
    return (s == "play" || s == "accel" || s == "stop" || s == "reset") ? s : "";
}

void Control::publish(const std::string& json) {
    FILE* f = fopen(STATE_TMP, "w");
    if (!f) return;
    fputs(json.c_str(), f);
    fclose(f);
    chmod(STATE_TMP, 0644);
    rename(STATE_TMP, STATE_PATH);
}
