#!/usr/bin/env python3
"""Keeps the translation catalogs in step with the code (the xgettext + msgmerge of this project).

    scripts/gettext-update.py            list texts missing from the catalogs / no longer used
    scripts/gettext-update.py --write    rewrite timer-nicolau.pot and every <locale>/LC_MESSAGES/*.po:
                                         new texts are added with an empty msgstr, translations kept

Texts are the English strings in _('...'), h('...'), L('...'), N_('...'), gettext('...') and _h('...')
in configurator-web/puzzle_configurator/*.py.
"""
import glob
import os
import re
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'configurator-web')
PKG = os.path.join(ROOT, 'puzzle_configurator')
LOCALE = os.path.join(ROOT, 'locale')
CALL = re.compile(r"(?<!\w)(?:_|h|L|N_|_h|gettext)\(\s*'((?:[^'\\]|\\.)*)'")


def source_texts():
    found = {}
    for path in sorted(glob.glob(os.path.join(PKG, '*.py'))):
        with open(path, encoding='utf-8') as f:
            for m in CALL.finditer(f.read()):
                text = re.sub(r'\\(.)', lambda x: {'n': '\n'}.get(x.group(1), x.group(1)), m.group(1))
                if path.endswith('form_generator.py'):
                    text = text.replace('{{', '{').replace('}}', '}')   # f-string escaping
                found.setdefault(text, os.path.basename(path))
    return found


def quote(t):
    return '"' + t.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n') + '"'


def read_catalog(path):
    sys.path.insert(0, ROOT)
    from puzzle_configurator.i18n import parse_po
    return parse_po(path)


def header_text(path):
    out, seen = [], 0
    with open(path, encoding='utf-8') as f:
        for line in f:
            if line.startswith('msgid') and seen:
                break
            if line.startswith('msgid'):
                seen = 1
            out.append(line)
    return ''.join(out[:-1] if out and out[-1].strip() == '' else out).rstrip() + '\n'


def main():
    write = '--write' in sys.argv
    texts = source_texts()
    catalogs = [os.path.join(LOCALE, 'timer-nicolau.pot')] + sorted(glob.glob(os.path.join(LOCALE, '*', 'LC_MESSAGES', '*.po')))
    status = 0
    for path in catalogs:
        messages, _ = read_catalog(path)
        missing = [t for t in texts if t not in messages and not path.endswith('.pot')]
        known = set(messages) | set(texts)
        unused = [t for t in messages if t not in texts]
        rel = os.path.relpath(path, LOCALE)
        if path.endswith('.pot'):
            with open(path, encoding='utf-8') as f:
                have = set(re.findall(r'^msgid "(.+)"$', f.read(), re.M))
            missing = [t for t in texts if quote(t)[1:-1] not in have]
            unused = []
        print('%-40s %3d texts, %d missing, %d unused' % (rel, len(texts), len(missing), len(unused)))
        status |= bool(missing or unused)
        if write:
            body = [header_text(path)]
            for t in texts:
                msgstr = '' if path.endswith('.pot') else messages.get(t, '')
                body.append('msgid %s\nmsgstr %s\n' % (quote(t), quote(msgstr)))
            with open(path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(body))
    return 0 if write else status


if __name__ == '__main__':
    sys.exit(main())
