#include "Config.h"
#include <nlohmann/json.hpp>
#include <fstream>
#include <iostream>

using json = nlohmann::json;

Config Config::defaults() {
    Config c;
    c.timer_duration_sec = 60;
    c.trap_pause_seconds = 3;
    c.accel_multiplier = 2;
    c.victory_timeout_sec = 600;
    c.brightness_pct = 80;
    c.room_name = "SALA A";
    c.victory_message = "ACESSO LIBERADO";
    c.sounds_enabled = true;
    c.custom_sounds_enabled = true;
    c.background_music_enabled = false;
    c.gpio_out_line = 21;
    c.gpio_out_active_high = true;
    c.mqtt_broker = "";
    c.mqtt_port = 1883;
    c.mqtt_topic_prefix = "nicolau/timer/";
    c.ha_discovery_prefix = "homeassistant";
    return c;
}

bool Config::load(const std::string& path) {
    std::ifstream f(path);
    if (!f.is_open()) return false;
    try {
        json j = json::parse(f);
        timer_duration_sec = j.value("timer_duration_sec", 120);
        trap_pause_seconds = j.value("trap_pause_seconds", 3);
        accel_multiplier = j.value("accel_multiplier", 2);
        victory_timeout_sec = j.value("victory_timeout_sec", 30);
        brightness_pct = j.value("brightness_pct", 80);
        room_name = j.value("room_name", "SALA A");
        victory_message = j.value("victory_message", "ACESSO LIBERADO");
        game_over_message = j.value("game_over_message", "BOMBA EXPLODIU");
        sounds_enabled = j.value("sounds_enabled", true);
        custom_sounds_enabled = j.value("custom_sounds_enabled", true);
        background_music_enabled = j.value("background_music_enabled", false);
        mqtt_broker = j.value("mqtt_broker", "");
        mqtt_port = j.value("mqtt_port", 1883);
        mqtt_username = j.value("mqtt_username", "");
        mqtt_password = j.value("mqtt_password", "");
        mqtt_topic_prefix = j.value("mqtt_topic_prefix", "nicolau/timer/");
        ha_discovery_prefix = j.value("ha_discovery_prefix", "homeassistant");

        auto sf = j.value("sound_files", json::object());
        sound_files.tick = sf.value("tick", "/var/lib/timer-nicolau/sfx/tick.mp3");
        sound_files.alarm = sf.value("alarm", "/var/lib/timer-nicolau/sfx/error.mp3");
        sound_files.victory = sf.value("victory", "/var/lib/timer-nicolau/sfx/sucess.mp3");
        sound_files.button_press = sf.value("button_press", "/var/lib/timer-nicolau/sfx/keypress.mp3");
        sound_files.button_release = sf.value("button_release", "/var/lib/timer-nicolau/sfx/keypress.mp3");
        sound_files.penalty_alarm = sf.value("penalty_alarm", "/var/lib/timer-nicolau/sfx/boom.mp3");
        sound_files.background_music = sf.value("background_music", "/var/lib/timer-nicolau/sfx/armed.mp3");

        sound_volume = j.value("sound_volume", 64);
        idle_message = j.value("idle_message", "AMBIENTE\nSEGURO");
        log_verbosity = j.value("log_verbosity", 1);

        auto gpio = j.value("gpio_out_desarmado", json::object());
        gpio_out_line = gpio.value("line", 21);
        gpio_out_active_high = gpio.value("active_high", true);

        return true;
    } catch (...) { return false; }
}

std::string Config::to_json_string() const {
    json j;
    j["timer_duration_sec"] = timer_duration_sec;
    j["trap_pause_seconds"] = trap_pause_seconds;
    j["accel_multiplier"] = accel_multiplier;
    j["victory_timeout_sec"] = victory_timeout_sec;
    j["brightness_pct"] = brightness_pct;
    j["room_name"] = room_name;
    j["victory_message"] = victory_message;
    j["sounds_enabled"] = sounds_enabled;
    j["custom_sounds_enabled"] = custom_sounds_enabled;
    j["background_music_enabled"] = background_music_enabled;
    j["mqtt_broker"] = mqtt_broker;
    j["mqtt_port"] = mqtt_port;
    j["mqtt_username"] = mqtt_username;
    j["mqtt_password"] = mqtt_password;
    j["mqtt_topic_prefix"] = mqtt_topic_prefix;
    j["ha_discovery_prefix"] = ha_discovery_prefix;
    j["sound_volume"] = sound_volume;
    j["idle_message"] = idle_message;
    j["game_over_message"] = game_over_message;
    j["log_verbosity"] = log_verbosity;

    json sf;
    sf["tick"] = sound_files.tick;
    sf["alarm"] = sound_files.alarm;
    sf["victory"] = sound_files.victory;
    sf["button_press"] = sound_files.button_press;
    sf["button_release"] = sound_files.button_release;
    sf["penalty_alarm"] = sound_files.penalty_alarm;
    sf["background_music"] = sound_files.background_music;
    j["sound_files"] = sf;

    json gpio;
    gpio["line"] = gpio_out_line;
    gpio["active_high"] = gpio_out_active_high;
    j["gpio_out_desarmado"] = gpio;

    return j.dump(2);
}

bool Config::save(const std::string& path) {
    std::ofstream f(path);
    if (!f.is_open()) return false;
    f << to_json_string() << std::endl;
    return true;
}
