#include "Audio.h"
#include <iostream>
#include <algorithm>

Audio::Audio() = default;

Audio::~Audio() {
    stop_background_music();
    for (auto& [k, v] : sounds) {
        if (v) Mix_FreeChunk(v);
    }
    if (bg_music) Mix_FreeMusic(bg_music);
    Mix_CloseAudio();
}

Mix_Chunk* Audio::load_sound(const std::string& path) {
    if (path.empty()) return nullptr;
    Mix_Chunk* c = Mix_LoadWAV(path.c_str());
    if (!c) {
        SDL_RWops* rw = SDL_RWFromFile(path.c_str(), "rb");
        if (rw) {
            c = Mix_LoadWAV_RW(rw, 1);
        }
    }
    if (!c && !path.empty()) {
    }
    return c;
}

bool Audio::init(const Config& cfg) {
    sounds_enabled = cfg.sounds_enabled;
    if (!sounds_enabled) {
        initialized = true;
        return true;
    }

    if (Mix_OpenAudio(44100, MIX_DEFAULT_FORMAT, 2, 2048) < 0) {
        std::cerr << "Mix_OpenAudio: " << Mix_GetError() << std::endl;
        return false;
    }
    Mix_AllocateChannels(8);
    Mix_Volume(-1, cfg.sound_volume);
    Mix_VolumeMusic(cfg.sound_volume);

    if (cfg.custom_sounds_enabled) {
        sounds["tick"] = load_sound(cfg.sound_files.tick);
        sounds["alarm"] = load_sound(cfg.sound_files.alarm);
        sounds["victory"] = load_sound(cfg.sound_files.victory);
        sounds["button_press"] = load_sound(cfg.sound_files.button_press);
        sounds["button_release"] = load_sound(cfg.sound_files.button_release);
        sounds["penalty_alarm"] = load_sound(cfg.sound_files.penalty_alarm);
        if (cfg.background_music_enabled) {
            bg_music = Mix_LoadMUS(cfg.sound_files.background_music.c_str());
            if (bg_music) {
                std::cout << "BG music loaded OK" << std::endl;
            } else {
                std::cerr << "BG music FAILED: " << Mix_GetError() << std::endl;
            }
        }
    }

    initialized = true;
    return true;
}

void Audio::play_tick() { if (sounds_enabled && sounds["tick"]) Mix_PlayChannel(0, sounds["tick"], 0); }
void Audio::play_alarm() { if (sounds_enabled && sounds["alarm"]) Mix_PlayChannel(1, sounds["alarm"], 0); }
void Audio::play_victory() { if (sounds_enabled && sounds["victory"]) Mix_PlayChannel(2, sounds["victory"], 0); }
void Audio::play_button_press() { if (sounds_enabled && sounds["button_press"]) Mix_PlayChannel(3, sounds["button_press"], 0); }
void Audio::play_button_release() { if (sounds_enabled && sounds["button_release"]) Mix_PlayChannel(4, sounds["button_release"], 0); }
void Audio::play_penalty_alarm() { if (sounds_enabled && sounds["penalty_alarm"]) Mix_PlayChannel(5, sounds["penalty_alarm"], 0); }

void Audio::start_background_music() {
    if (!initialized || !sounds_enabled || !bg_music) return;
    if (bg_playing) return;
    Mix_RewindMusic();
    if (Mix_PlayMusic(bg_music, -1) == -1) {
        std::cerr << "Mix_PlayMusic: " << Mix_GetError() << std::endl;
        return;
    }
    bg_playing = true;
    std::cout << "Background music started" << std::endl;
}

void Audio::stop_background_music() {
    if (bg_playing) {
        Mix_HaltMusic();
        Mix_RewindMusic();
        bg_playing = false;
        std::cout << "Background music stopped" << std::endl;
    }
}

void Audio::stop_all_channels() {
    if (initialized && sounds_enabled) {
        Mix_HaltChannel(-1);
    }
}

void Audio::set_sounds_enabled(bool en) { sounds_enabled = en; }

bool Audio::is_penalty_alarm_playing() const {
    return initialized && sounds_enabled && Mix_Playing(5) != 0;
}

bool Audio::is_victory_playing() const {
    return initialized && sounds_enabled && Mix_Playing(2) != 0;
}

void Audio::set_volume(int vol) {
    current_volume = std::max(0, std::min(128, vol));
    Mix_Volume(-1, current_volume);
    Mix_VolumeMusic(current_volume);
}

int Audio::get_volume() const { return current_volume; }
