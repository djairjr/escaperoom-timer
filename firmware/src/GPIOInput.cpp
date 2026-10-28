#include "GPIOInput.h"
#include <iostream>
GPIOInput::GPIOInput(int out_line)
    : chip("/dev/gpiochip0"), sl(64), al(65), bl(66), dl(67),
      ol((out_line < 0 || out_line > 223 || (out_line >= 64 && out_line <= 67)) ? 21 : out_line) 
	// sl=MOSI(p19/VERDE), al=MISO(p21/AMARELO), bl=SCLK(p23/AZUL), dl=CE0(p24/VERMELHO), ol=PA21(p26/OUTPUT)
    , last_press()
    , prev_raw_s(true), prev_raw_a(true), prev_raw_b(true), prev_raw_d(true)
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
        gpiod::line::offsets inputs_arr = {sl, al, bl, dl};
        cfg.add_line_settings(inputs_arr, inp);
        gpiod::line::offsets output_arr = {ol};
        cfg.add_line_settings(output_arr, out);

        gpiod::request_builder b = chip.prepare_request();
        b.set_consumer("timer-sdl");
        b.set_line_config(cfg);
        request = std::make_unique<gpiod::line_request>(b.do_request());

        // Read initial raw state (ACTIVE=HIGH=1, INACTIVE=LOW=0)
        // Pull-up not pressed = ACTIVE(1), pressed = INACTIVE(0)
        prev_raw_s = request->get_value(sl) == gpiod::line::value::ACTIVE;
        prev_raw_a = request->get_value(al) == gpiod::line::value::ACTIVE;
        prev_raw_b = request->get_value(bl) == gpiod::line::value::ACTIVE;
        prev_raw_d = request->get_value(dl) == gpiod::line::value::ACTIVE;

        return true;
    } catch(const std::exception& e) {
        std::cerr << "GPIO init: " << e.what() << std::endl;
        return false;
    }
}

void GPIOInput::poll() {
    try {
        // raw: true=HIGH(ACTIVE, not pressed), false=LOW(INACTIVE, pressed)
        bool raw_s = request->get_value(sl) == gpiod::line::value::ACTIVE;
        bool raw_a = request->get_value(al) == gpiod::line::value::ACTIVE;
        bool raw_b = request->get_value(bl) == gpiod::line::value::ACTIVE;
        bool raw_d = request->get_value(dl) == gpiod::line::value::ACTIVE;
        
        // Falling edge detection: was HIGH (not pressed), now LOW (pressed)
        auto now = std::chrono::steady_clock::now();
        auto since_last = std::chrono::duration_cast<std::chrono::milliseconds>(now - last_press).count();
        
        if (since_last > 50) {
            start_pressed   = prev_raw_s && !raw_s;
            a_pressed       = prev_raw_a && !raw_a;
            b_pressed       = prev_raw_b && !raw_b;
            disarm_pressed  = prev_raw_d && !raw_d;
            if (start_pressed || a_pressed || b_pressed || disarm_pressed)
                last_press = now;
        } else {
            start_pressed = a_pressed = b_pressed = disarm_pressed = false;
        }
        
        prev_raw_s = raw_s;
        prev_raw_a = raw_a;
        prev_raw_b = raw_b;
        prev_raw_d = raw_d;
    } catch(const std::exception& e) {
        std::cerr << "GPIO poll: " << e.what() << std::endl;
    }
}

bool GPIOInput::is_start_pressed() const { return start_pressed; }
bool GPIOInput::is_button_a_pressed() const { return a_pressed; }
bool GPIOInput::is_button_b_pressed() const { return b_pressed; }
bool GPIOInput::is_disarm_pressed() const { return disarm_pressed; }

bool GPIOInput::is_button_a_low() const {
    try { return request->get_value(al) == gpiod::line::value::INACTIVE; }
    catch(...) { return false; }
}
bool GPIOInput::is_button_b_low() const {
    try { return request->get_value(bl) == gpiod::line::value::INACTIVE; }
    catch(...) { return false; }
}
bool GPIOInput::is_disarm_low() const {
    try { return request->get_value(dl) == gpiod::line::value::INACTIVE; }
    catch(...) { return false; }
}

void GPIOInput::set_disarmed(bool armed) {
    try {
        if (armed) {
            // SOLVED: se active_high, vai ACTIVE; se active_low, vai INACTIVE (oposto)
            request->set_value(ol, output_active_high ? gpiod::line::value::ACTIVE : gpiod::line::value::INACTIVE);
        } else {
            // IDLE/GAME_OVER: se active_high, vai INACTIVE; se active_low, vai ACTIVE
            request->set_value(ol, output_active_high ? gpiod::line::value::INACTIVE : gpiod::line::value::ACTIVE);
        }
    } catch(...) {}
}
