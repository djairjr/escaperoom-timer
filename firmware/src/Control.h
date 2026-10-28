#pragma once
#include <string>

// Local remote control of the game. The web configurator sends one-word datagrams to a UNIX socket
// and reads a small JSON snapshot; neither side ever waits for the other, so the web being slow or
// down cannot touch the game loop.
class Control {
public:
    ~Control();
    bool init();
    // One pending command ("play", "accel", "stop" or "reset") or "" when there is none. Never blocks.
    std::string poll();
    // Replaces the snapshot file atomically.
    void publish(const std::string& json);
private:
    int fd = -1;
};
