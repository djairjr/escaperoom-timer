"""Interface languages of the web configurator, the gettext way.

Texts in the code are the English source strings: _('Game control'). Each language is a standard
gettext catalog, a plain-text .po file you can edit with any editor or Poedit:

    <localedir>/<locale>/LC_MESSAGES/timer-nicolau.po        e.g. pt_BR/LC_MESSAGES/timer-nicolau.po

Catalogs are looked up in /etc/timer-nicolau/locale (yours, survives upgrades and wins) and then in
/usr/share/timer-nicolau/locale (shipped). A string with no translation shows in English. To add a
language: copy timer-nicolau.pot to <locale>/LC_MESSAGES/timer-nicolau.po, translate the msgstr lines
and fill in the "X-Native-Name" header (the name in the page's language selector). No compiling: the
.po is read directly.

Which language: the board's own locale, set with the usual Linux tools (`sudo dpkg-reconfigure locales`
or `localectl set-locale LANG=pt_BR.UTF-8`): LANGUAGE, LC_ALL, LC_MESSAGES, LANG, then
/etc/default/locale and /etc/locale.conf, then English. There is no language setting in the web page.
Restart puzzle-configurator after changing the locale.
"""

import os
import re

DOMAIN = 'timer-nicolau'
LOCALE_DIRS = [
    os.environ.get('TIMER_LOCALE_DIR', '/etc/timer-nicolau/locale'),
    os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'locale'),   # source checkout
    '/usr/share/timer-nicolau/locale',
]
SOURCE_LANG = 'en'
_ESCAPES = {'n': '\n', 't': '\t', 'r': '\r', '"': '"', '\\': '\\'}
_cache = {}


def parse_po(path):
    """Catalog of a .po file: ({msgid: msgstr}, header dict). Fuzzy and empty entries are skipped."""
    messages, header = {}, {}
    fuzzy = False
    state, msgid, msgstr = None, '', ''

    def flush():
        nonlocal state, msgid, msgstr, fuzzy
        if state == 'str':
            if msgid == '':
                for line in msgstr.split('\n'):
                    if ':' in line:
                        k, v = line.split(':', 1)
                        header[k.strip()] = v.strip()
            elif msgstr and not fuzzy:
                messages[msgid] = msgstr
        state, msgid, msgstr, fuzzy = None, '', '', False

    def unquote(s):
        s = s.strip()[1:-1]
        return re.sub(r'\\(.)', lambda m: _ESCAPES.get(m.group(1), m.group(1)), s)

    with open(path, encoding='utf-8') as f:
        for raw in f:
            line = raw.strip()
            if line.startswith('#,') and 'fuzzy' in line:
                flush_pending = state == 'str'
                if flush_pending:
                    flush()
                fuzzy = True
            elif line.startswith('#') or not line:
                if not line and state == 'str':
                    flush()
            elif line.startswith('msgid '):
                if state == 'str':
                    flush()
                state, msgid = 'id', unquote(line[6:])
            elif line.startswith('msgstr '):
                state, msgstr = 'str', unquote(line[7:])
            elif line.startswith('"'):
                if state == 'id':
                    msgid += unquote(line)
                elif state == 'str':
                    msgstr += unquote(line)
    flush()
    return messages, header


def _normalize(tag):
    """'pt-br', 'pt_BR.UTF-8', 'pt_BR@euro' -> 'pt_BR'; '' for C/POSIX."""
    if not tag:
        return ''
    tag = re.split(r'[.@]', tag.strip(), maxsplit=1)[0].replace('-', '_')
    if tag in ('C', 'POSIX', ''):
        return ''
    parts = tag.split('_')
    return parts[0].lower() + ('_' + parts[1].upper() if len(parts) > 1 else '')


def available():
    """Locales with a catalog, e.g. ['pt_BR'], plus the source language 'en'."""
    found = {SOURCE_LANG}
    for base in LOCALE_DIRS:
        try:
            for d in os.listdir(base):
                if os.path.isfile(os.path.join(base, d, 'LC_MESSAGES', DOMAIN + '.po')):
                    found.add(_normalize(d))
        except OSError:
            pass
    return sorted(found)


def match_language(wanted, codes=None):
    """Best available locale for a tag ('pt', 'pt-BR', 'pt_PT.UTF-8'...), or None."""
    codes = codes or available()
    w = _normalize(wanted)
    if not w:
        return None
    if w in codes:
        return w
    base = w.split('_')[0]
    if base in codes:
        return base
    for c in codes:                      # pt-PT asked, only pt_BR installed: same language
        if c.split('_')[0] == base:
            return c
    return None


def system_locales():
    """The board's locale preference as gettext reads it: LANGUAGE (a list, ignored when the locale is
    C/POSIX), else the first of LC_ALL, LC_MESSAGES, LANG that is set. /etc/default/locale and
    /etc/locale.conf only count when the environment sets none of them."""
    names = ('LANGUAGE', 'LC_ALL', 'LC_MESSAGES', 'LANG')
    env = {v: os.environ.get(v, '') for v in names}
    if not any(env[v] for v in names[1:]):
        for path in ('/etc/default/locale', '/etc/locale.conf'):
            try:
                with open(path) as f:
                    for line in f:
                        m = re.match(r'\s*(LANGUAGE|LC_ALL|LC_MESSAGES|LANG)\s*=\s*"?([^"\s]+)', line)
                        if m and not env[m.group(1)]:
                            env[m.group(1)] = m.group(2)
            except OSError:
                pass
    effective = next((env[v] for v in names[1:] if env[v]), '')
    if not _normalize(effective):          # unset, C or POSIX: no translation
        return []
    return [t for t in env['LANGUAGE'].split(':') if t] + [effective]


def detect_language():
    codes = available()
    for tag in system_locales():
        m = match_language(tag, codes)
        if m:
            return m
    return SOURCE_LANG


def _catalog(lang):
    if lang not in _cache:
        messages, header = {}, {}
        # shipped first, then yours on top
        for base in reversed(LOCALE_DIRS):
            for d in {lang, lang.split('_')[0]}:
                path = os.path.join(base, d, 'LC_MESSAGES', DOMAIN + '.po')
                if os.path.isfile(path):
                    try:
                        m, h = parse_po(path)
                        messages.update(m)
                        header.update(h)
                    except (OSError, UnicodeDecodeError):
                        pass
        _cache[lang] = (messages, header)
    return _cache[lang]


class Translator:
    def __init__(self, lang=SOURCE_LANG):
        self.lang = lang

    def gettext(self, msgid, *args):
        text = _catalog(self.lang)[0].get(msgid, msgid)
        for i, a in enumerate(args):
            text = text.replace('{%d}' % i, str(a))
        return text

    __call__ = gettext

    def translations(self, msgids):
        """{msgid: translation} for the page's script."""
        return {m: self.gettext(m) for m in msgids}
