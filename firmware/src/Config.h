#pragma once
#include <string>
#include <map>

struct SoundFiles {
    std::string tick = "/var/lib/timer-nicolau/sfx/tick.mp3";
    std::string alarm = "";
    std::string victory = "/var/lib/timer-nicolau/sfx/sucess.mp3";
    std::string button_press = "/var/lib/timer-nicolau/sfx/keypress.mp3";
    std::string button_release = "/var/lib/timer-nicolau/sfx/keypress.mp3";
    std::string penalty_alarm = "";
    std::string background_music = "/var/lib/timer-nicolau/sfx/armed.mp3";
};

struct Config {
    int timer_duration_sec = 120;
    int trap_pause_seconds = 3;
    int accel_multiplier = 2;
    int victory_timeout_sec = 600;
    int brightness_pct = 80;
    std::string idle_message = "AMBIENTE\nSEGURO";
    std::string victory_message = "ACESSO LIBERADO";
    std::string game_over_message = "BOMBA EXPLODIU";
    std::string room_name = "SALA A";
    bool sounds_enabled = true;
    bool custom_sounds_enabled = true;
    bool background_music_enabled = false;
    int sound_volume = 64;
    int log_verbosity = 1;
    SoundFiles sound_files;
    int gpio_out_line = 21;
    bool gpio_out_active_high = true;
    std::string mqtt_broker = "";
    int mqtt_port = 1883;
    std::string mqtt_username = "";
    std::string mqtt_password = "";
    std::string mqtt_topic_prefix = "nicolau/timer/";
    std::string ha_discovery_prefix = "homeassistant";

    bool load(const std::string& path);
    bool save(const std::string& path);
    std::string to_json_string() const;
    static Config defaults();
};
