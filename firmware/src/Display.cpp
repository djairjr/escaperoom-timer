/* Display.cpp */
#include "Display.h"
#include <iostream>
#include <cmath>
#include <cstdlib>
#include <algorithm>
#include <vector>
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

/* Lines of a screen message. "\\n" (backslash, n) typed in the web page and real newlines are the
 * line breaks the user asked for; without any, the text is wrapped at spaces only when it does not fit. */
static std::vector<std::string> split_message(const std::string& msg, TTF_Font* font, int max_w) {
    std::string text;
    for (size_t i = 0; i < msg.size(); i++) {
        if (msg[i] == '\\') {
            // one or more backslashes followed by n (an escaped "\\n" survives some editors): a break
            size_t j = i;
            while (j < msg.size() && msg[j] == '\\') j++;
            if (j < msg.size() && msg[j] == 'n') { text += '\n'; i = j; }
            else text += msg[i];
        }
        else if (msg[i] != '\r') text += msg[i];
    }
    std::vector<std::string> lines;
    size_t pos = 0;
    while (pos <= text.size()) {
        size_t nl = text.find('\n', pos);
        std::string para = text.substr(pos, nl == std::string::npos ? std::string::npos : nl - pos);
        std::string cur;
        size_t p = 0;
        while (p <= para.size()) {
            size_t sp = para.find(' ', p);
            std::string word = para.substr(p, sp == std::string::npos ? std::string::npos : sp - p);
            std::string trial = cur.empty() ? word : cur + " " + word;
            int w = 0;
            if (!cur.empty() && font) TTF_SizeUTF8(font, trial.c_str(), &w, nullptr);
            if (!cur.empty() && w > max_w) { lines.push_back(cur); cur = word; }
            else cur = trial;
            if (sp == std::string::npos) break;
            p = sp + 1;
        }
        lines.push_back(cur);
        if (nl == std::string::npos) break;
        pos = nl + 1;
    }
    return lines;
}

/* Draws msg centred on the screen. The font shrinks (down to 40% of base_size) until every line fits
 * the width and all lines fit the height. */
void Display::draw_message(const std::string& msg, SDL_Color c, int base_size) {
    const char* font_path = "/usr/share/fonts/truetype/DSEG14Classic-Regular.ttf";
    int max_w = width * 92 / 100, max_h = height * 90 / 100;
    for (int sz = base_size; ; sz = sz * 9 / 10) {
        TTF_Font* f = TTF_OpenFont(font_path, sz);
        if (!f) return;
        std::vector<std::string> lines = split_message(msg, f, max_w);
        int line_h = sz + sz / 6, widest = 0;
        for (const std::string& l : lines) {
            int w = 0;
            if (!l.empty()) TTF_SizeUTF8(f, l.c_str(), &w, nullptr);
            widest = std::max(widest, w);
        }
        int total_h = line_h * (int)lines.size() - (line_h - sz);
        if ((widest <= max_w && total_h <= max_h) || sz <= base_size * 4 / 10) {
            int y = (height - total_h) / 2;
            for (const std::string& l : lines) {
                if (!l.empty()) {
                    int w = 0;
                    TTF_SizeUTF8(f, l.c_str(), &w, nullptr);
                    SDL_Surface* surf = TTF_RenderUTF8_Blended(f, l.c_str(), c);
                    if (surf) {
                        SDL_Texture* tex = SDL_CreateTextureFromSurface(renderer, surf);
                        if (tex) {
                            SDL_Rect dst = {(width - w) / 2, y, surf->w, surf->h};
                            SDL_RenderCopy(renderer, tex, nullptr, &dst);
                            SDL_DestroyTexture(tex);
                        }
                        SDL_FreeSurface(surf);
                    }
                }
                y += line_h;
            }
            TTF_CloseFont(f);
            return;
        }
        TTF_CloseFont(f);
    }
}

void Display::render_victory(const std::string& msg) {
    last_static = Static::Victory; last_static_msg = msg;
    if (!renderer) return;
    SDL_SetRenderDrawColor(renderer, 0, 0, 0, 255);
    SDL_RenderClear(renderer);
    draw_message(msg, SDL_Color{255, 255, 0, 255}, ui(100));  // same yellow as the running clock
    SDL_RenderPresent(renderer);
}

void Display::render_game_over(const std::string& msg) {
    last_static = Static::GameOver; last_static_msg = msg;
    if (!renderer) return;
    SDL_SetRenderDrawColor(renderer, 0, 0, 0, 255);
    SDL_RenderClear(renderer);
    int flash = (SDL_GetTicks() / 200) % 2;
    draw_message(msg, flash ? SDL_Color{255, 0, 0, 255} : SDL_Color{180, 0, 0, 255}, ui(100));
    SDL_RenderPresent(renderer);
}

void Display::render_ready(const std::string& room_name, const std::string& idle_msg) {
    last_static = Static::None;
    if (!renderer) return;
    SDL_SetRenderDrawColor(renderer, 0, 0, 0, 255);
    SDL_RenderClear(renderer);
    draw_message(idle_msg, SDL_Color{0, 200, 0, 255}, ui(120));
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
