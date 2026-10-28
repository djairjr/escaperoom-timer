#pragma once
#include <string>
#include <functional>
#include "Config.h"
#include "GameState.h"

class MQTTClient {
public:
    MQTTClient();
    ~MQTTClient();
    bool init(const Config& cfg);
    void loop();
    void publish_state(GameState s);
    void publish_time_remaining(int sec);
    void publish_speed(int mult);
    void publish_disarmed(bool a);
    void publish_volume(int vol);
    void publish_trap(bool active);
    void publish_game_over();
    void publish_duration(int sec);
    bool is_connected() const;
    void set_command_callback(std::function<void(const std::string&)> cb);
    void set_volume_callback(std::function<void(int)> cb);
    void set_duration_callback(std::function<void(int)> cb);
    void set_trap_callback(std::function<void(bool)> cb);
private:
    std::string topic_prefix, ha_prefix, room;
    std::function<void(const std::string&)> cmd_cb;
    std::function<void(int)> volume_cb, duration_cb;
    std::function<void(bool)> trap_cb;
};
