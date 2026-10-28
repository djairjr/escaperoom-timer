#pragma once
#include <SDL2/SDL.h>
#include <SDL2/SDL_ttf.h>
#include <string>
#include "GameState.h"
#include "Config.h"

class Display {
public:
    Display();
    ~Display();
    bool init(const std::string& font_path, int brightness_pct);
    // Call from the main loop: when the HDMI sink appears or changes mode, the window is rebuilt
    // at the new resolution and the last static screen is drawn again. Cheap (one sysfs read per
    // second); returns true when the output was rebuilt.
    bool poll_hotplug();
    void render_time(int minutes, int seconds, int speed_mult, GameState state, int pct);
    void render_victory(const std::string& msg);
    void render_game_over(const std::string& msg);
    void render_ready(const std::string& room_name, const std::string& idle_msg);
    void render_message(const std::string& msg, int r, int g, int b);
    void set_brightness(int pct);
private:
    SDL_Window* window = nullptr;
    SDL_Renderer* renderer = nullptr;
    TTF_Font* font = nullptr;
    int width = 1280, height = 720, brightness = 80;
    std::string connector_sig;       // "<connector>:<preferred mode>" of the connected sink, "" if none
    Uint32 last_poll_ms = 0;
    enum class Static { None, Victory, GameOver } last_static = Static::None;
    std::string last_static_msg;
    std::string font_file;
    // Layout is designed for a 720-line screen; every size and offset goes through ui().
    int ui(int base) const { return base * height / 720; }
    struct Mode { int w = 0, h = 0, hz = 0; };
    static Mode best_mode();
    bool open_video();
    void close_video();
    static std::string read_connector();
    SDL_Color color_running(int pct);
    void draw_message(const std::string& msg, SDL_Color c, int base_size);
    void render_text(const std::string& text, int x, int y, SDL_Color c, int sz);
    void render_text_small(const std::string& text, int x, int y, SDL_Color c, int sz);
};
