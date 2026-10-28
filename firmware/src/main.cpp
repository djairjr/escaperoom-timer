#include "Config.h"
#include "GameState.h"
#include "TimerEngine.h"
#include "GPIOInput.h"
#include "Display.h"
#include "Audio.h"
#include "MQTTClient.h"
#include <SDL2/SDL.h>
#include <iostream>
#include <chrono>
#include <algorithm>

static int g_log = 1;
#define LOG(lvl, msg) do { if (g_log >= lvl) { std::cout << msg << std::endl; } } while(0)

int main() {
    Config cfg = Config::defaults();
    cfg.load("/etc/timer-sdl/config.json");

    g_log = cfg.log_verbosity;

    // Robbery speed (RUNNING_2x is the state name; the factor comes from config.json).
    const int accel = std::max(1, std::min(10, cfg.accel_multiplier));
    // Freeze after the first of A/B is pressed, before the robbery speed starts.
    const int pause_ms = std::max(0, std::min(30, cfg.trap_pause_seconds)) * 1000;

    GPIOInput gpio(cfg.gpio_out_line);
    if (!gpio.init()) { std::cerr << "GPIO init failed.\n"; return 1; }
    gpio.output_active_high = cfg.gpio_out_active_high;

    Display display;
    if (!display.init("/usr/share/fonts/truetype/DSEG14Classic-Regular.ttf", cfg.brightness_pct)) {
        std::cerr << "Display init failed.\n"; return 1;
    }

    // Sounds take tens of seconds to load on some boots; show the idle screen meanwhile so a
    // connected TV never sits black and looks broken.
    Uint32 t_ready = SDL_GetTicks();
    display.render_ready(cfg.room_name, cfg.idle_message);
    LOG(1, "First idle screen drawn in " << (SDL_GetTicks() - t_ready) << " ms");

    Uint32 t_audio = SDL_GetTicks();
    Audio audio;
    audio.init(cfg);
    LOG(1, "Audio ready after " << (SDL_GetTicks() - t_audio) << " ms");
    audio.start_background_music();

    TimerEngine timer(cfg);

    GameState state = GameState::IDLE;
    bool first_button_assigned = false;
    int trap_btn = -1, roubo_btn = -1;
    bool trap_held = false;
    int pause_remaining_ms = 0;
    bool display_update = true;
    int freeze_mins = 0, freeze_secs = 0;
    int trap_debounce = 0;
    Uint32 solved_start = 0;
    bool published_solved = false;
    int last_second = -1;

    MQTTClient mqtt;

    // go_solved: APENAS muda estado e marca flags. Sem audio, sem display, sem publish.
    auto go_solved = [&](Uint32 now_ms, const char* source) {
        state = GameState::SOLVED;
        timer.stop();
        solved_start = now_ms;
        published_solved = false;
        last_second = -1;
        LOG(1, "State: SOLVED (" << source << ")");
    };

    // MQTT callbacks — APENAS acumulam comandos. Sem audio, display, publish.
    std::string pending_cmd;
    mqtt.set_command_callback([&](const std::string& cmd) {
        pending_cmd = cmd;
        LOG(2, "MQTT cmd: " << cmd);
    });

    mqtt.set_volume_callback([&](int vol) {
        audio.set_volume(vol);
        LOG(1, "Volume set to " << vol << " via MQTT");
    });

    mqtt.set_duration_callback([&](int sec) {
        cfg.timer_duration_sec = sec;
        cfg.save("/etc/timer-sdl/config.json");
        timer.set_duration_seconds(sec);
        LOG(1, "Duration set to " << sec << " s via MQTT");
    });

    mqtt.set_trap_callback([&](bool on) {
        pending_cmd = on ? "trap_on" : "trap_off";
        LOG(2, "MQTT trap: " << (on ? "ON" : "OFF"));
    });

    mqtt.init(cfg);

    display.render_ready(cfg.room_name, cfg.idle_message);
    mqtt.publish_state(GameState::IDLE);
    mqtt.publish_disarmed(false);
    mqtt.publish_volume(cfg.sound_volume);
    mqtt.publish_duration(cfg.timer_duration_sec);
    mqtt.publish_trap(false);
    LOG(1, "Timer-SDL running. Room: " << cfg.room_name);
    LOG(1, "State: IDLE.");

    bool quit = false;
    SDL_Event ev;
    Uint32 last_tick_ms = SDL_GetTicks(), last_mqtt_ms = SDL_GetTicks();

    while (!quit) {
        Uint32 now = SDL_GetTicks();
        int dt_ms = now - last_tick_ms;
        last_tick_ms = now;

        while (SDL_PollEvent(&ev)) {
            if (ev.type == SDL_QUIT) quit = true;
            if (ev.type == SDL_KEYDOWN && ev.key.keysym.sym == SDLK_ESCAPE) quit = true;
        }

        gpio.poll();
        bool sp = gpio.is_start_pressed();
        bool ba = gpio.is_button_a_pressed();
        bool bb = gpio.is_button_b_pressed();
        bool disarm = gpio.is_disarm_pressed();

        // Timer update (só em estados ativos)
        if (state == GameState::RUNNING_1x || state == GameState::RUNNING_2x || state == GameState::TRAP_HELD)
            timer.update(dt_ms);

        // PAUSE_INITIAL countdown
        if (state == GameState::PAUSE_INITIAL)
            pause_remaining_ms -= dt_ms;

        // Consumir comando MQTT pendente
        std::string cmd = pending_cmd;
        pending_cmd.clear();

        // ========================================================
        // FSM ÚNICA — transições centralizadas
        // ========================================================
        GameState prev = state;

        switch (state) {
            case GameState::IDLE:
                if (cmd == "start" || sp) {
                    state = GameState::RUNNING_1x;
                    display_update = true;
                    timer.start();
                    first_button_assigned = false;
                    trap_btn = -1; roubo_btn = -1; last_second = -1;
                    LOG(1, "State: RUNNING_1x");
                }
                break;

            case GameState::RUNNING_1x:
                if (cmd == "stop" || cmd == "disarm" || disarm) {
                    go_solved(now, disarm ? "stop" : cmd.c_str());
                    break;
                }
                if (!first_button_assigned && (ba || bb)) {
                    first_button_assigned = true;
                    if (ba) { roubo_btn = 65; trap_btn = 66; }
                    else    { roubo_btn = 66; trap_btn = 65; }
                    {
                        int r = timer.get_time_remaining_ms() / 1000;
                        freeze_mins = r / 60;
                        freeze_secs = r % 60;
                    }
                    state = GameState::PAUSE_INITIAL;
                    pause_remaining_ms = pause_ms;
                    display_update = false;
                    timer.set_speed_multiplier(0);
                    LOG(1, "State: PAUSE_INITIAL (" << pause_ms / 1000 << "s)");
                }
                break;

            case GameState::PAUSE_INITIAL:
                if (cmd == "stop" || cmd == "disarm" || disarm) {
                    go_solved(now, disarm ? "stop" : cmd.c_str());
                    break;
                }
                if (pause_remaining_ms <= 0) {
                    display_update = true;
                    state = GameState::RUNNING_2x;
                    timer.set_speed_multiplier(accel);
                    LOG(1, "State: RUNNING_2x");
                }
                break;

            case GameState::RUNNING_2x: {
                if (cmd == "stop" || cmd == "disarm" || disarm) {
                    go_solved(now, disarm ? "stop" : cmd.c_str());
                    break;
                }
                if (cmd == "trap_on") {
                    state = GameState::TRAP_HELD;
                    trap_held = true;
                    timer.set_speed_multiplier(1);
                    LOG(1, "State: TRAP_HELD (via MQTT)");
                    break;
                }
                bool trap_now = (trap_btn == 65) ? gpio.is_button_a_low() : gpio.is_button_b_low();
                if (trap_now) {
                    trap_debounce = std::min(3, trap_debounce + 1);
                } else {
                    trap_debounce = std::max(0, trap_debounce - 1);
                }
                if (trap_debounce >= 3) {
                    trap_debounce = 3;
                    state = GameState::TRAP_HELD;
                    trap_held = true;
                    timer.set_speed_multiplier(1);
                    LOG(1, "State: TRAP_HELD");
                }
                break;
            }

            case GameState::TRAP_HELD: {
                if (cmd == "stop" || cmd == "disarm" || disarm) {
                    go_solved(now, disarm ? "stop" : cmd.c_str());
                    break;
                }
                if (cmd == "trap_off") {
                    state = GameState::RUNNING_2x;
                    timer.set_speed_multiplier(accel);
                    trap_held = false;
                    LOG(1, "State: RUNNING_2x (trap released via MQTT)");
                    break;
                }
                bool trap_now = (trap_btn == 65) ? gpio.is_button_a_low() : gpio.is_button_b_low();
                if (trap_now) {
                    trap_debounce = std::min(3, trap_debounce + 1);
                } else {
                    trap_debounce = std::max(0, trap_debounce - 1);
                }
                if (trap_debounce <= 0) {
                    trap_debounce = 0;
                    state = GameState::RUNNING_2x;
                    timer.set_speed_multiplier(accel);
                    trap_held = false;
                    LOG(1, "State: RUNNING_2x (trap released)");
                } else {
                    timer.set_speed_multiplier(1);
                }
                break;
            }

            case GameState::SOLVED:
            case GameState::GAME_OVER:
                break;
        }

        // ========================================================
        // Transições automáticas (timer expirou, timeout, reset)
        // ========================================================
        if (timer.is_expired() && state != GameState::GAME_OVER && state != GameState::SOLVED && state != GameState::IDLE) {
            state = GameState::GAME_OVER;
            solved_start = now;
            published_solved = false;
            LOG(1, "State: GAME_OVER (timer expired)");
        }

        if (state == GameState::SOLVED || state == GameState::GAME_OVER) {
            // Timeout automático
            if (now - solved_start > (Uint32)(cfg.victory_timeout_sec * 1000)) {
                state = GameState::IDLE;
                LOG(1, "State: IDLE (timeout)");
            }
            // START/reset só após som do estado terminal terminar
            bool terminal_sound_playing = (state == GameState::SOLVED && audio.is_victory_playing())
                                       || (state == GameState::GAME_OVER && audio.is_penalty_alarm_playing());
            if (!terminal_sound_playing && (now - solved_start > 500)) {
                if (cmd == "reset" || cmd == "start" || sp) {
                    state = GameState::IDLE;
                    LOG(1, "State: IDLE (start/reset after terminal sound)");
                }
            }
        }

        if (cmd == "reset" && state != GameState::IDLE && state != GameState::SOLVED && state != GameState::GAME_OVER) {
            state = GameState::IDLE;
            LOG(1, "State: IDLE (reset via HA)");
        }

        // ========================================================
        // FRAME DE EFEITOS — derivado do estado atual
        // Audio, display, MQTT publish centralizados aqui.
        // ========================================================
        if (state != prev) {
            audio.stop_all_channels();
        }

        // Parar trilha ao entrar em SOLVED ou GAME_OVER
        if (state == GameState::SOLVED || state == GameState::GAME_OVER) {
            audio.stop_background_music();
        }

        switch (state) {
            case GameState::IDLE:
                if (state != prev) {
                    timer.reset();
                    gpio.set_disarmed(false);
                    first_button_assigned = false;
                    trap_btn = -1; roubo_btn = -1; trap_held = false;
                    last_second = -1;
                    audio.start_background_music();
                    mqtt.publish_state(GameState::IDLE);
                    mqtt.publish_disarmed(false);
                }
                display.render_ready(cfg.room_name, cfg.idle_message);
                break;

            case GameState::RUNNING_1x:
                if (state != prev) {
                    audio.play_button_press();
                    mqtt.publish_state(GameState::RUNNING_1x);
                    mqtt.publish_speed(1);
                }
                {
                    int r = timer.get_time_remaining_ms() / 1000;
                    int mins = r / 60, secs = r % 60;
                    int total = timer.get_total_duration_ms() / 1000;
                    int pct = total > 0 ? (r * 100 / total) : 100;
                    display.render_time(mins, secs, 1, state, pct);
                    if (r != last_second) { audio.play_tick(); last_second = r; }
                }
                break;

            case GameState::PAUSE_INITIAL:
                if (state != prev) {
                    audio.play_alarm();
                }
                display.render_time(freeze_mins, freeze_secs, 1, GameState::RUNNING_1x, 50);
                break;

            case GameState::RUNNING_2x:
                if (state != prev) {
                    mqtt.publish_state(GameState::RUNNING_2x);
                    mqtt.publish_speed(accel);
                    mqtt.publish_trap(false);
                }
                {
                    int r = timer.get_time_remaining_ms() / 1000;
                    int mins = r / 60, secs = r % 60;
                    int total = timer.get_total_duration_ms() / 1000;
                    int pct = total > 0 ? (r * 100 / total) : 100;
                    display.render_time(mins, secs, accel, state, pct);
                    if (r != last_second) { audio.play_tick(); last_second = r; }
                }
                break;

            case GameState::TRAP_HELD:
                if (state != prev) {
                    audio.play_button_press();
                    mqtt.publish_state(GameState::TRAP_HELD);
                    mqtt.publish_speed(1);
                    mqtt.publish_trap(true);
                }
                {
                    int r = timer.get_time_remaining_ms() / 1000;
                    int mins = r / 60, secs = r % 60;
                    int total = timer.get_total_duration_ms() / 1000;
                    int pct = total > 0 ? (r * 100 / total) : 100;
                    display.render_time(mins, secs, 1, state, pct);
                    if (r != last_second) { audio.play_tick(); last_second = r; }
                }
                break;

            case GameState::SOLVED:
                if (!published_solved) {
                    audio.play_victory();
                    gpio.set_disarmed(true);
                    display.render_victory(cfg.victory_message);
                    mqtt.publish_state(GameState::SOLVED);
                    mqtt.publish_disarmed(true);
                    published_solved = true;
                }
                break;

            case GameState::GAME_OVER:
                if (!published_solved) {
                    audio.play_penalty_alarm();
                    gpio.set_disarmed(false);
                    display.render_game_over(cfg.game_over_message);
                    mqtt.publish_game_over();
                    mqtt.publish_disarmed(false);
                    published_solved = true;
                }
                break;
        }

        if (now - last_mqtt_ms > 1000) {
            last_mqtt_ms = now;
            mqtt.loop();
            if (state != GameState::IDLE && state != GameState::SOLVED && state != GameState::GAME_OVER)
                mqtt.publish_time_remaining(timer.get_time_remaining_ms() / 1000);
        }

        display.poll_hotplug();

        SDL_Delay(10);
    }

    gpio.set_disarmed(false);
    display.render_ready(cfg.room_name, "DESLIGADO");
    SDL_Delay(500);
    return 0;
}
