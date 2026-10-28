#include "MQTTClient.h"
#include <iostream>
#include <cstdio>
#include <thread>
#include <chrono>
#include <fstream>
#include <cstring>
#include <sys/stat.h>
#include <nlohmann/json.hpp>

// Module-level state
static struct {
    std::string topic_prefix, ha_prefix, room;
    std::function<void(const std::string&)> cmd_cb;
    std::function<void(int)> vol_cb, dur_cb;
    std::function<void(bool)> trap_cb;
    std::thread* reader = nullptr;
    bool running = false;
} s;

/* Append to command file (atomic per line - bridge reads all lines + truncates) */
static void py_cmd(const std::string& topic, const std::string& payload, bool retained) {
    std::ofstream f("/tmp/timer_mqtt.cmd", std::ios::app);
    if (f.is_open()) {
        f << "PUB|" << topic << "|" << payload << "|" << (retained ? "1" : "0") << "\n";
        f.flush();
    }
}

static void event_loop() {
    FILE* fp = popen("python3 /usr/lib/timer-nicolau/mqtt_bridge.py 2>/dev/null", "r");
    if (!fp) { std::cerr << "MQTT: bridge start failed\n"; return; }

    char line[1024];
    while (s.running && fgets(line, sizeof(line), fp)) {
        std::string sline(line);
        if (!sline.empty() && sline.back() == '\n') sline.pop_back();
        auto pipe = sline.find('|');
        if (pipe == std::string::npos) continue;

        std::string topic = sline.substr(0, pipe);
        std::string payload = sline.substr(pipe + 1);

        if (topic == s.topic_prefix + "/command" && s.cmd_cb) s.cmd_cb(payload);
        if (topic == s.topic_prefix + "/disarmed/set" && s.cmd_cb)
            s.cmd_cb((payload == "1" || payload == "ON" || payload == "true") ? "disarm" : "arm");
        if (topic == s.topic_prefix + "/volume/set" && s.vol_cb) {
            try { s.vol_cb(std::stoi(payload)); } catch (...) {}
        }
        if (topic == s.topic_prefix + "/duration/set" && s.dur_cb) {
            try { s.dur_cb(std::stoi(payload)); } catch (...) {}
        }
        if (topic == s.topic_prefix + "/trap/set" && s.trap_cb) {
            s.trap_cb(payload == "ON" || payload == "1");
        }
    }
    pclose(fp);
}

MQTTClient::MQTTClient() = default;
MQTTClient::~MQTTClient() { s.running = false; }

bool MQTTClient::init(const Config& cfg) {
    if (cfg.mqtt_broker.empty()) return true;

    topic_prefix = cfg.mqtt_topic_prefix + cfg.room_name;
    ha_prefix = cfg.ha_discovery_prefix;
    room = cfg.room_name;
    s.topic_prefix = topic_prefix;
    s.ha_prefix = ha_prefix;
    s.room = room;

    {
        // Everything the bridge needs to connect, from config.json (the bridge used to carry a
        // fixed broker and credentials). Mode 600: it holds the MQTT password.
        nlohmann::json bridge_cfg = {
            {"room", room}, {"prefix", topic_prefix}, {"ha_prefix", ha_prefix},
            {"broker", cfg.mqtt_broker}, {"port", cfg.mqtt_port > 0 ? cfg.mqtt_port : 1883},
            {"username", cfg.mqtt_username}, {"password", cfg.mqtt_password},
        };
        const char* path = "/tmp/timer_mqtt_config.json";
        std::ofstream f(path, std::ios::trunc);
        if (f.is_open()) {
            f << bridge_cfg.dump() << "\n";
            f.close();
            chmod(path, 0600);
        }
    }

    system("echo > /tmp/timer_mqtt.cmd; chmod 666 /tmp/timer_mqtt.cmd");

    s.running = true;
    s.reader = new std::thread(event_loop);
    std::cout << "MQTT: bridge started" << std::endl;
    return true;
}

void MQTTClient::loop() {}
void MQTTClient::publish_state(GameState s) { py_cmd(topic_prefix + "/state", state_name(s), true); }
void MQTTClient::publish_time_remaining(int sec) { py_cmd(topic_prefix + "/time_remaining", std::to_string(sec), true); }
void MQTTClient::publish_speed(int mult) { py_cmd(topic_prefix + "/speed_multiplier", std::to_string(mult), true); }
void MQTTClient::publish_disarmed(bool a) { py_cmd(topic_prefix + "/disarmed", a ? "1" : "0", true); }
void MQTTClient::publish_volume(int vol) { py_cmd(topic_prefix + "/volume", std::to_string(vol), true); }
void MQTTClient::publish_trap(bool active) { py_cmd(topic_prefix + "/trap", active ? "ON" : "OFF", true); }
void MQTTClient::publish_game_over() { py_cmd(topic_prefix + "/state", "game_over", true); }
void MQTTClient::publish_duration(int sec) { py_cmd(topic_prefix + "/duration", std::to_string(sec), true); }
bool MQTTClient::is_connected() const { return true; }
void MQTTClient::set_command_callback(std::function<void(const std::string&)> cb) { cmd_cb = cb; s.cmd_cb = cb; }
void MQTTClient::set_volume_callback(std::function<void(int)> cb) { volume_cb = cb; s.vol_cb = cb; }
void MQTTClient::set_duration_callback(std::function<void(int)> cb) { duration_cb = cb; s.dur_cb = cb; }
void MQTTClient::set_trap_callback(std::function<void(bool)> cb) { trap_cb = cb; s.trap_cb = cb; }
