/* Display.cpp */
#include "Display.h"
#include <iostream>
#include <cmath>
#include <cstdlib>
#include <fstream>
#include <glob.h>
#include <fcntl.h>
#include <unistd.h>
#include <xf86drm.h>
#include <xf86drmMode.h>

Display::Display() = default;

Display::~Display() {
    if (font) TTF_CloseFont(font);
    if (renderer) SDL_DestroyRenderer(renderer);
    if (window) SDL_DestroyWindow(window);
    TTF_Quit();
    SDL_Quit();
}

// "<connector>:<preferred mode>" of the first connected DRM connector, "" when no sink is plugged
// in (or powered on) yet. The kernel lists the preferred mode of the sink first in "modes".
std::string Display::read_connector() {
    glob_t g;
    std::string sig;
    if (glob("/sys/class/drm/card*-*/status", 0, nullptr, &g) == 0) {
        for (size_t i = 0; i < g.gl_pathc && sig.empty(); i++) {
            std::string dir(g.gl_pathv[i]);
            dir.erase(dir.rfind('/'));
            std::string status, mode;
            std::ifstream(dir + "/status") >> status;
            if (status != "connected") continue;
            std::ifstream(dir + "/modes") >> mode;
            sig = dir.substr(dir.rfind('/') + 1) + ":" + mode;
        }
        globfree(&g);
    }
    return sig;
}

void Display::close_video() {
    if (renderer) { SDL_DestroyRenderer(renderer); renderer = nullptr; }
    if (window) { SDL_DestroyWindow(window); window = nullptr; }
    SDL_QuitSubSystem(SDL_INIT_VIDEO);
}

// The best mode of the first connected connector: the largest progressive mode (then the highest
// refresh rate up to 60 Hz). Interlaced and double-scan modes are skipped, and the size is capped at
// 1920x1080: the Mali400 on the H3 cannot drive more, and a 4K sink would only get a slideshow.
// SDL's own "desktop mode" is just the first entry of the sink's list, which is often not the best.
Display::Mode Display::best_mode() {
    const int max_w = 1920, max_h = 1080, max_hz = 60;
    Mode best;
    for (const char* node : {"/dev/dri/card0", "/dev/dri/card1"}) {
        int fd = open(node, O_RDWR | O_CLOEXEC);
        if (fd < 0) continue;
        if (drmModeRes* res = drmModeGetResources(fd)) {
            for (int i = 0; i < res->count_connectors; i++) {
                drmModeConnector* conn = drmModeGetConnector(fd, res->connectors[i]);
                if (!conn) continue;
                if (conn->connection == DRM_MODE_CONNECTED) {
                    for (int m = 0; m < conn->count_modes; m++) {
                        const drmModeModeInfo& mi = conn->modes[m];
                        if (mi.flags & (DRM_MODE_FLAG_INTERLACE | DRM_MODE_FLAG_DBLSCAN)) continue;
                        if (mi.hdisplay > max_w || mi.vdisplay > max_h || (int)mi.vrefresh > max_hz) continue;
                        long area = (long)mi.hdisplay * mi.vdisplay, barea = (long)best.w * best.h;
                        if (area > barea || (area == barea && (int)mi.vrefresh > best.hz))
                            best = {mi.hdisplay, mi.vdisplay, (int)mi.vrefresh};
                    }
                }
                drmModeFreeConnector(conn);
            }
            drmModeFreeResources(res);
        }
        close(fd);
        if (best.w) break;
    }
    return best;
}

// Opens the output at the best resolution the sink reports. Without a sink the process keeps
// running headless (renderer == nullptr): the game must not depend on the TV being on at boot.
bool Display::open_video() {
    Uint32 t0 = SDL_GetTicks();
    auto step = [&](const char* what) { std::cerr << "Display step " << what << " +" << (SDL_GetTicks() - t0) << " ms" << std::endl; };
    connector_sig = read_connector();
    Mode want = best_mode();
    step("best_mode");
    if (SDL_InitSubSystem(SDL_INIT_VIDEO) < 0) {
        std::cerr << "SDL video: " << SDL_GetError() << std::endl;
        return false;
    }

    // Pick the SDL mode that matches the best one; fall back to SDL's default when none does.
    SDL_DisplayMode dm{};
    bool have = false;
    if (want.w) {
        int n = SDL_GetNumDisplayModes(0);
        for (int i = 0; i < n; i++) {
            SDL_DisplayMode m;
            if (SDL_GetDisplayMode(0, i, &m) != 0 || m.w != want.w || m.h != want.h) continue;
            if (!have || std::abs(m.refresh_rate - want.hz) < std::abs(dm.refresh_rate - want.hz)) {
                dm = m;
                have = true;
            }
        }
    }
    if (!have && SDL_GetDesktopDisplayMode(0, &dm) != 0) dm = SDL_DisplayMode{};
    step("sdl_init+modes");
    if (dm.w > 0) { width = dm.w; height = dm.h; }

    window = SDL_CreateWindow("Timer", SDL_WINDOWPOS_UNDEFINED, SDL_WINDOWPOS_UNDEFINED,
                              width, height, SDL_WINDOW_FULLSCREEN);
    if (!window) { std::cerr << "Window: " << SDL_GetError() << std::endl; close_video(); return false; }
    if (have) {
        SDL_SetWindowDisplayMode(window, &dm);
        SDL_SetWindowFullscreen(window, SDL_WINDOW_FULLSCREEN);
    }
    step("window");
    renderer = SDL_CreateRenderer(window, -1, SDL_RENDERER_ACCELERATED);
    if (!renderer) { std::cerr << "Renderer: " << SDL_GetError() << std::endl; close_video(); return false; }
    step("renderer");
    SDL_GetRendererOutputSize(renderer, &width, &height);

    if (font) TTF_CloseFont(font);
    font = TTF_OpenFont(font_file.c_str(), ui(180));
    if (!font) { std::cerr << "Font: " << TTF_GetError() << std::endl; close_video(); return false; }

    SDL_RenderClear(renderer);
    SDL_RenderPresent(renderer);
    step("first_present");
    std::cerr << "Display " << width << "x" << height << " (best " << want.w << "x" << want.h << "@"
              << want.hz << ", sink " << connector_sig << ")" << std::endl;
    return true;
}

bool Display::init(const std::string& font_path, int brightness_pct) {
    brightness = brightness_pct;
    setenv("SDL_VIDEO_DRIVER", "kmsdrm", 1);
    setenv("SDL_RENDER_DRIVER", "opengles2", 1);

    if (TTF_Init() < 0) {
        std::cerr << "TTF_Init: " << TTF_GetError() << std::endl;
        return false;
    }
    font_file = font_path;

    if (!open_video()) std::cerr << "No display yet; waiting for the sink." << std::endl;
    return true;
}

bool Display::poll_hotplug() {
    Uint32 now = SDL_GetTicks();
    if (now - last_poll_ms < 1000) return false;
    last_poll_ms = now;

    std::string sig = read_connector();
    // A sink going away keeps the current output: tearing it down would only blank a TV that is
    // switched off and on again, and the same mode comes back.
    if (sig.empty() || (sig == connector_sig && renderer)) return false;

    std::cerr << "Display change: " << connector_sig << " -> " << sig << std::endl;
    close_video();
    if (!open_video()) return false;
    if (last_static == Static::Victory) render_victory(last_static_msg);
    else if (last_static == Static::GameOver) render_game_over(last_static_msg);
    return true;
}

SDL_Color Display::color_running(int pct) {
    if (pct > 50) return {0, 255, 0, 255};
    if (pct > 25) return {255, 255, 0, 255};
    if (pct > 10) return {255, 165, 0, 255};
    int flash = (SDL_GetTicks() / 500) % 2;
    return flash ? SDL_Color{255, 0, 0, 255} : SDL_Color{80, 0, 0, 255};
}

void Display::render_text(const std::string& text, int x, int y, SDL_Color c, int sz) {
    TTF_Font* f = TTF_OpenFont("/usr/share/fonts/truetype/DSEG14Classic-Regular.ttf", sz);
    if (!f) return;
    SDL_Surface* surf = TTF_RenderUTF8_Blended(f, text.c_str(), c);
    if (surf) {
        SDL_Texture* tex = SDL_CreateTextureFromSurface(renderer, surf);
        if (tex) {
            SDL_Rect dst = {x, y, surf->w, surf->h};
            SDL_RenderCopy(renderer, tex, nullptr, &dst);
            SDL_DestroyTexture(tex);
        }
        SDL_FreeSurface(surf);
    }
    TTF_CloseFont(f);
}

void Display::render_text_small(const std::string& text, int x, int y, SDL_Color c, int sz) {
    render_text(text, x, y, c, sz);
}

void Display::render_time(int minutes, int seconds, int speed_mult, GameState state, int pct) {
    last_static = Static::None;
    if (!renderer) return;
    SDL_SetRenderDrawColor(renderer, 0, 0, 0, 255);
    SDL_RenderClear(renderer);

    char buf[16];
    snprintf(buf, sizeof(buf), "%02d:%02d", minutes, seconds);
    SDL_Color c = color_running(pct);

    int tw = 0;
    TTF_SizeUTF8(font, buf, &tw, nullptr);
    int x = (width - tw) / 2;
    int y = (height - ui(180)) / 2;
    render_text(buf, x, y, c, ui(180));

    if (speed_mult > 1) {
        char badge[16];
        snprintf(badge, sizeof(badge), "%dx", speed_mult);
        render_text_small(badge, width - ui(100), ui(20), SDL_Color{255, 0, 0, 255}, ui(50));
    } else if (state == GameState::TRAP_HELD) {
        render_text_small("1x", width - ui(100), ui(20), SDL_Color{0, 255, 0, 255}, ui(50));
    }

    SDL_RenderPresent(renderer);
}

/* break_words: turn spaces AND literal backslash-n into real newlines */
static std::string break_words(const std::string& msg) {
    /* Handle "\\n" two-char sequence from JSON */
    std::string out;
    for (size_t i = 0; i < msg.size(); i++) {
        if (msg[i] == '\\' && i + 1 < msg.size() && msg[i + 1] == 'n') {
            out += '\n';
            i++;
        } else if (msg[i] == ' ') {
            out += '\n';
        } else {
            out += msg[i];
        }
    }
    return out;
}

void Display::render_victory(const std::string& msg) {
    last_static = Static::Victory; last_static_msg = msg;
    if (!renderer) return;
    SDL_SetRenderDrawColor(renderer, 0, 0, 0, 255);
    SDL_RenderClear(renderer);

    SDL_Color c = {255, 255, 0, 255};  // same yellow as the running clock and the speed-up message

    std::string broken = break_words(msg);
    size_t nl = broken.find('\n');
    std::string line1, line2;
    if (nl != std::string::npos) {
        line1 = broken.substr(0, nl);
        line2 = broken.substr(nl + 1);
    } else {
        line1 = broken;
    }

    int tw1 = 0, tw2 = 0, th1 = 0, th2 = 0;
    int font_sz = ui(100);
    TTF_Font* f1 = TTF_OpenFont("/usr/share/fonts/truetype/DSEG14Classic-Regular.ttf", font_sz);
    if (f1) {
        TTF_SizeUTF8(f1, line1.c_str(), &tw1, &th1);
        TTF_CloseFont(f1);
    }
    if (!line2.empty()) {
        TTF_Font* f2 = TTF_OpenFont("/usr/share/fonts/truetype/DSEG14Classic-Regular.ttf", font_sz);
        if (f2) {
            TTF_SizeUTF8(f2, line2.c_str(), &tw2, &th2);
            TTF_CloseFont(f2);
        }
    }

    int line_h = font_sz + ui(20);
    int total_h = line2.empty() ? font_sz : font_sz + line_h;
    int start_y = (height - total_h) / 2;

    int x1 = (width - tw1) / 2;
    render_text(line1, x1, start_y, c, font_sz);

    if (!line2.empty()) {
        int x2 = (width - tw2) / 2;
        render_text(line2, x2, start_y + line_h, c, font_sz);
    }

    SDL_RenderPresent(renderer);
}

void Display::render_game_over(const std::string& msg) {
    last_static = Static::GameOver; last_static_msg = msg;
    if (!renderer) return;
    SDL_SetRenderDrawColor(renderer, 0, 0, 0, 255);
    SDL_RenderClear(renderer);

    int flash = (SDL_GetTicks() / 200) % 2;
    SDL_Color c = flash ? SDL_Color{255, 0, 0, 255} : SDL_Color{180, 0, 0, 255};

    std::string broken = break_words(msg);
    size_t nl = broken.find('\n');
    std::string line1, line2;
    if (nl != std::string::npos) {
        line1 = broken.substr(0, nl);
        line2 = broken.substr(nl + 1);
    } else {
        line1 = broken;
    }
    int tw1 = 0, th1 = 0, tw2 = 0, th2 = 0;
    int font_sz = ui(100);
    TTF_Font* f = TTF_OpenFont("/usr/share/fonts/truetype/DSEG14Classic-Regular.ttf", font_sz);
    if (f) {
        TTF_SizeUTF8(f, line1.c_str(), &tw1, &th1);
        TTF_CloseFont(f);
    }
    if (!line2.empty()) {
        f = TTF_OpenFont("/usr/share/fonts/truetype/DSEG14Classic-Regular.ttf", font_sz);
        if (f) {
            TTF_SizeUTF8(f, line2.c_str(), &tw2, &th2);
            TTF_CloseFont(f);
        }
    }
    int line_h = font_sz + ui(20);
    int total_h = line2.empty() ? font_sz : font_sz + line_h;
    int start_y = (height - total_h) / 2;
    int x1 = (width - tw1) / 2;
    render_text(line1, x1, start_y, c, font_sz);
    if (!line2.empty()) {
        int x2 = (width - tw2) / 2;
        render_text(line2, x2, start_y + line_h, c, font_sz);
    }
    SDL_RenderPresent(renderer);
}

void Display::render_ready(const std::string& room_name, const std::string& idle_msg) {
    last_static = Static::None;
    if (!renderer) return;
    SDL_SetRenderDrawColor(renderer, 0, 0, 0, 255);
    SDL_RenderClear(renderer);

    std::string broken = break_words(idle_msg);
    size_t nl = broken.find('\n');
    std::string line1, line2;
    if (nl != std::string::npos) {
        line1 = broken.substr(0, nl);
        line2 = broken.substr(nl + 1);
    } else {
        line1 = broken;
    }

    SDL_Color green = {0, 200, 0, 255};

    int tw1 = 0, th1 = 0, tw2 = 0, th2 = 0;
    int font_sz = ui(120);
    TTF_Font* f1 = TTF_OpenFont("/usr/share/fonts/truetype/DSEG14Classic-Regular.ttf", font_sz);
    if (f1) {
        TTF_SizeUTF8(f1, line1.c_str(), &tw1, &th1);
        TTF_CloseFont(f1);
    }
    if (!line2.empty()) {
        TTF_Font* f2 = TTF_OpenFont("/usr/share/fonts/truetype/DSEG14Classic-Regular.ttf", font_sz);
        if (f2) {
            TTF_SizeUTF8(f2, line2.c_str(), &tw2, &th2);
            TTF_CloseFont(f2);
        }
    }

    int line_h = font_sz + ui(20);
    int total_h = line2.empty() ? font_sz : font_sz + line_h;
    int start_y = (height - total_h) / 2;

    int x1 = (width - tw1) / 2;
    render_text(line1, x1, start_y, green, font_sz);

    if (!line2.empty()) {
        int x2 = (width - tw2) / 2;
        render_text(line2, x2, start_y + line_h, green, font_sz);
    }

    SDL_RenderPresent(renderer);
}

void Display::render_message(const std::string& msg, int r, int g, int b) {
    if (!renderer) return;
    SDL_SetRenderDrawColor(renderer, 0, 0, 0, 255);
    SDL_RenderClear(renderer);
    render_text(msg, (width - ui(400)) / 2, (height - ui(180)) / 2, SDL_Color{(Uint8)r, (Uint8)g, (Uint8)b, 255}, ui(120));
    SDL_RenderPresent(renderer);
}

void Display::set_brightness(int pct) { brightness = pct; }
