#include "GameState.h"

std::string state_name(GameState s) {
    switch (s) {
        case GameState::IDLE: return "idle";
        case GameState::RUNNING_1x: return "running_1x";
        case GameState::RUNNING_2x: return "running_2x";
        case GameState::TRAP_HELD: return "trap_held";
        case GameState::SOLVED: return "solved";
        case GameState::GAME_OVER: return "game_over";
    }
    return "unknown";
}
