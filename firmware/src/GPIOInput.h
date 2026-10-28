#pragma once
#include <gpiod.hpp>
#include <memory>
#include <chrono>

class GPIOInput {
public:
    explicit GPIOInput(int out_line = 21);
    ~GPIOInput();
    bool init();
    void poll();
    bool is_start_pressed() const;
    bool is_button_a_pressed() const;
    bool is_button_b_pressed() const;
    bool is_disarm_pressed() const;
    bool is_button_a_low() const;   // continuous: true if A is currently pressed (LOW)
    bool is_button_b_low() const;   // continuous: true if B is currently pressed (LOW)
    bool is_disarm_low() const;     // continuous: true if STOP is currently pressed (LOW)
    void set_disarmed(bool armed);

private:
    gpiod::chip chip;
    int sl, al, bl, dl, ol;
    bool prev_raw_s, prev_raw_a, prev_raw_b, prev_raw_d;
    bool start_pressed, a_pressed, b_pressed, disarm_pressed;
    std::unique_ptr<gpiod::line_request> request;
    std::chrono::steady_clock::time_point last_press;

public:
    bool output_active_high = true;  // true=ACTIVE(HIGH) em SOLVED, false=INACTIVE(HIGH) em SOLVED
};
