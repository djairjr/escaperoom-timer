#pragma once
#include <gpiod.hpp>
#include <memory>

class GPIOInput {
public:
    GPIOInput();
    ~GPIOInput();
    bool init();
    void poll();
    bool is_start_pressed() const;
    bool is_button_a_pressed() const;
    bool is_button_b_pressed() const;
    bool is_disarm_pressed() const;
    void set_disarmed(bool armed);

private:
    gpiod::chip chip;
    int sl, al, bl, dl, ol;
    bool prev_start, prev_a, prev_b, prev_disarm;
    bool start_pressed, a_pressed, b_pressed, disarm_pressed;
    std::unique_ptr<gpiod::line_request> request;
};
