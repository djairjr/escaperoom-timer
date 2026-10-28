#pragma once
#include "Config.h"
#include <chrono>

class TimerEngine {
public:
    TimerEngine(const Config& cfg);
    void start();
    void stop();
    void reset();
    void set_speed_multiplier(int mult);
    int get_time_remaining_ms() const;
    int get_speed_multiplier() const;
    void update(int dt_ms);
    bool is_running() const;
    bool is_expired() const;
    int get_elapsed_ms() const;
    int get_total_duration_ms() const;
    void set_duration_seconds(int min);
    int get_duration_seconds() const;

private:
    int total_duration_ms;
    int elapsed_ms;
    int speed_mult;
    bool running;
};

