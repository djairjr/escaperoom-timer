#pragma once
#include "Config.h"
#include <SDL2/SDL_mixer.h>
#include <map>
#include <string>

class Audio {
public:
    Audio();
    ~Audio();
    bool init(const Config& cfg);
    void set_volume(int vol);  // 0-128
    int get_volume() const;
    void play_tick();
    void play_alarm();
    void play_victory();
    void play_button_press();
    void play_button_release();
    void play_penalty_alarm();
    void start_background_music();
    void stop_background_music();
    void stop_all_channels();           // Mix_HaltChannel(-1)
    void set_sounds_enabled(bool en);
    bool is_penalty_alarm_playing() const;
    bool is_victory_playing() const;     // canal 2 (victory) ainda tocando

private:
    Mix_Chunk* load_sound(const std::string& path);
    std::map<std::string, Mix_Chunk*> sounds;
    Mix_Music* bg_music = nullptr;
    bool sounds_enabled = true;
    bool bg_playing = false;
    bool initialized = false;
    int current_volume = 64;
};
