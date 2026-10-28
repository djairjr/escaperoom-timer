#include "TimerEngine.h"

TimerEngine::TimerEngine(const Config& cfg)
    : total_duration_ms(cfg.timer_duration_sec * 1000)
    , elapsed_ms(0)
    , speed_mult(1)
    , running(false)
{}

void TimerEngine::start() {
    elapsed_ms = 0;
    speed_mult = 1;
    running = true;
}

void TimerEngine::stop() {
    running = false;
}

void TimerEngine::reset() {
    elapsed_ms = 0;
    speed_mult = 1;
    running = false;
}

void TimerEngine::set_speed_multiplier(int mult) {
    speed_mult = (mult < 1) ? 1 : mult;
}

int TimerEngine::get_speed_multiplier() const { return speed_mult; }
int TimerEngine::get_time_remaining_ms() const { return total_duration_ms - elapsed_ms; }
bool TimerEngine::is_running() const { return running; }
bool TimerEngine::is_expired() const { return elapsed_ms >= total_duration_ms; }
int TimerEngine::get_elapsed_ms() const { return elapsed_ms; }
int TimerEngine::get_total_duration_ms() const { return total_duration_ms; }

void TimerEngine::set_duration_seconds(int sec) {
    if (sec < 1) sec = 1;
    if (sec > 7200) sec = 7200;
    total_duration_ms = sec * 1000;
}

int TimerEngine::get_duration_seconds() const {
    return total_duration_ms / 1000;
}

void TimerEngine::update(int dt_ms) {
    if (!running) return;
    elapsed_ms += dt_ms * speed_mult;
    if (elapsed_ms >= total_duration_ms) {
        elapsed_ms = total_duration_ms;
        running = false;
    }
}
