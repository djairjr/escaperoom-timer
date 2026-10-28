"""Interface languages of the web configurator.

One JSON file per language in locales/ (pt-BR.json, en.json, ...): copy en.json, translate the
values and the language shows up in the page's selector. Keys missing from a language fall back to
English, then to the key itself, so a partial translation never breaks the page.

The language of a request is, in order: ?lang=xx (also remembered in a cookie), the "lang" cookie,
"language" in setup.json, the browser's Accept-Language, then DEFAULT_LANG.
"""

import json
import os

LOCALES_DIR = os.path.join(os.path.dirname(__file__), 'locales')
DEFAULT_LANG = 'en'
FALLBACK_LANG = 'en'

_cache = {}


def available():
    """Language codes with a file in locales/, e.g. ['en', 'pt-BR']."""
    try:
        return sorted(f[:-5] for f in os.listdir(LOCALES_DIR) if f.endswith('.json'))
    except OSError:
        return [FALLBACK_LANG]


def _load(lang):
    if lang not in _cache:
        try:
            with open(os.path.join(LOCALES_DIR, lang + '.json'), encoding='utf-8') as f:
                _cache[lang] = json.load(f)
        except (OSError, ValueError):
            _cache[lang] = {}
    return _cache[lang]


def match_language(wanted, codes=None):
    """Best available code for a language tag ('pt', 'pt-br', 'en-GB' ...), or None."""
    codes = codes or available()
    if not wanted:
        return None
    low = {c.lower(): c for c in codes}
    w = wanted.strip().lower().replace('_', '-')
    if w in low:
        return low[w]
    base = w.split('-')[0]
    for c in codes:
        if c.lower().split('-')[0] == base:
            return c
    return None


def detect_language(request, setup=None):
    codes = available()
    for candidate in (request.args.get('lang'), request.cookies.get('lang'), (setup or {}).get('language')):
        m = match_language(candidate, codes)
        if m:
            return m
    # Accept-Language: "pt-BR,pt;q=0.9,en;q=0.8"
    for part in request.headers.get('Accept-Language', '').split(','):
        m = match_language(part.split(';')[0], codes)
        if m:
            return m
    return match_language(DEFAULT_LANG, codes) or FALLBACK_LANG


class Translator:
    def __init__(self, lang=DEFAULT_LANG):
        self.lang = lang

    def t(self, key, *args):
        text = _load(self.lang).get(key)
        if text is None:
            text = _load(FALLBACK_LANG).get(key, key)
        for i, a in enumerate(args):
            text = text.replace('{%d}' % i, str(a))
        return text

    def has(self, key):
        return key in _load(self.lang) or key in _load(FALLBACK_LANG)

    def js(self):
        """Every 'js.*' string, for the page's script."""
        merged = {k: v for k, v in _load(FALLBACK_LANG).items() if k.startswith('js.')}
        merged.update({k: v for k, v in _load(self.lang).items() if k.startswith('js.')})
        return merged

    def languages(self):
        """[(code, native name)] for the selector."""
        return [(c, _load(c).get('_name', c)) for c in available()]
