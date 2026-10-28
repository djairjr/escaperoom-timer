#pragma once
#include <string>

enum class GameState {
    IDLE,
    RUNNING_1x,
    PAUSE_INITIAL,  // 3s pause after first button press
    RUNNING_2x,
    TRAP_HELD,
    SOLVED,
    GAME_OVER
};

std::string state_name(GameState s);
