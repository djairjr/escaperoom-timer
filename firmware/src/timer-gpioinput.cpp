#include "GPIOInput.h"
#include <iostream>

GPIOInput::GPIOInput()
    : chip("/dev/gpiochip0"), sl(7), al(8), bl(9), dl(10), ol(20)
    , prev_start(false), prev_a(false), prev_b(false), prev_disarm(false)
    , start_pressed(false), a_pressed(false), b_pressed(false), disarm_pressed(false) {}
    
GPIOInput::~GPIOInput() { try{ if(request) request->release(); } catch(...) {} }

bool GPIOInput::init() {
    try {
        gpiod::line_settings inp;
        inp.set_direction(gpiod::line::direction::INPUT);
        inp.set_bias(gpiod::line::bias::PULL_UP);
        inp.set_edge_detection(gpiod::line::edge::NONE);

        gpiod::line_settings out;
        out.set_direction(gpiod::line::direction::OUTPUT);
        out.set_output_value(gpiod::line::value::INACTIVE);

        gpiod::line_config cfg;
        gpiod::line::offsets inputs = {sl, al, bl, dl};
        cfg.add_line_settings(inputs, inp);
        cfg.add_line_settings({ol}, out);

        gpiod::request_builder b = chip.prepare_request();
        b.set_consumer("timer-sdl");
        b.set_line_config(cfg);
        request = std::make_unique<gpiod::line_request>(b.do_request());

        // Read initial state to arm edge detection
        prev_start = request->get_value(sl) == gpiod::line::value::INACTIVE;
        prev_a = request->get_value(al) == gpiod::line::value::INACTIVE;
        prev_b = request->get_value(bl) == gpiod::line::value::INACTIVE;
        prev_disarm = request->get_value(dl) == gpiod::line::value::INACTIVE;
        
        return true;
    } catch(const std::exception& e) {
        std::cerr << "GPIO init: " << e.what() << std::endl;
        return false;
    }
}

void GPIOInput::poll() {
    try {
        // active LOW buttons: INACTIVE=HIGH means NOT pressed, ACTIVE=LOW means PRESSED
        bool s = request->get_value(sl) == gpiod::line::value::INACTIVE;
        bool a = request->get_value(al) == gpiod::line::value::INACTIVE;
        bool b = request->get_value(bl) == gpiod::line::value::INACTIVE;
        bool d = request->get_value(dl) == gpiod::line::value::INACTIVE;
        
        // Edge detection: true only on HIGH->LOW transition (button press)
        start_pressed = prev_start && !s;
        a_pressed = prev_a && !a;
        b_pressed = prev_b && !b;
        disarm_pressed = prev_disarm && !d;
        
        prev_start = s;
        prev_a = a;
        prev_b = b;
        prev_disarm = d;
    } catch(const std::exception& e) {
        std::cerr << "GPIO poll: " << e.what() << std::endl;
    }
}

bool GPIOInput::is_start_pressed() const { return start_pressed; }
bool GPIOInput::is_button_a_pressed() const { return a_pressed; }
bool GPIOInput::is_button_b_pressed() const { return b_pressed; }
bool GPIOInput::is_disarm_pressed() const { return disarm_pressed; }

void GPIOInput::set_disarmed(bool armed) {
    try {
        request->set_value(ol, armed ? gpiod::line::value::ACTIVE : gpiod::line::value::INACTIVE);
    } catch(...) {}
}
