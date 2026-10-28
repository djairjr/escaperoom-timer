#!/usr/bin/env python3
"""
puzzle_configurator/form_generator.py — Renderizador de Formulário HTML Dinâmico

Gera HTML puro (sem framework JS) a partir do schema parseado pelo JsonParser.
Renderiza inputs, checkboxes, file uploads, selects, sections com accordion.
"""

import html as html_mod
import json
import os
import re
from .json_parser import JsonParser
from .i18n import Translator, detect_language


def N_(text):
    """Marks a text for translation without translating it yet (gettext convention)."""
    return text


FIELD_LABELS = {
    'timer_duration_sec': N_('Game length'), 'accel_multiplier': N_('Robbery speed (multiplier)'),
    'trap_pause_seconds': N_('Freeze when the robbery starts'),
    'victory_timeout_sec': N_('Time on the end screen before returning to ready'),
    'room_name': N_('Room name'), 'idle_message': N_('Ready screen text'), 'victory_message': N_('Victory text'),
    'game_over_message': N_('Game over text'), 'brightness_pct': N_('Brightness (%)'),
    'sounds_enabled': N_('Sounds on'), 'sound_volume': N_('Sound volume'),
    'background_music_enabled': N_('Background music on'), 'custom_sounds_enabled': N_('Use custom sounds'),
    'mqtt_broker': N_('MQTT broker'), 'mqtt_port': N_('MQTT port'), 'mqtt_username': N_('MQTT user'),
    'mqtt_password': N_('MQTT password'), 'mqtt_topic_prefix': N_('MQTT topic prefix'),
    'ha_discovery_prefix': N_('Home Assistant discovery prefix'), 'log_verbosity': N_('Log detail (0-3)'),
}

SOUND_LABELS = {
    'tick': N_('Tick (each second)'), 'alarm': N_('Alarm (start of the robbery)'), 'victory': N_('Victory'),
    'button_press': N_('Button press'), 'button_release': N_('Button release'),
    'penalty_alarm': N_('Game over (explosion)'), 'background_music': N_('Background music'),
}


class FormGenerator:
    """Gera HTML de formulário a partir do schema de campos."""
    
    def generate(self, config_data, logo_path='/static/logoNicolaudosBrinquedos.svg', tr=None):
        """
        Gera página HTML completa com formulário dinâmico.
        
        Args:
            config_data: dict completo do config.json
            logo_path: path para o logo SVG
            tr: i18n.Translator of the request's language (English when omitted)
        
        Returns:
            string HTML
        """
        self.tr = tr or Translator(detect_language())
        h = lambda text, *a: html_mod.escape(self.tr.gettext(text, *a))
        parser = JsonParser()
        all_fields = parser.parse_to_dicts(config_data)
        
        # Classificar campos por aba
        config_fields = [f for f in all_fields 
                        if f['type'] != 'section' 
                        and not f['path'].startswith('sound_files')
                        and not f['path'].startswith('gpio_out')
                        and not f['path'].startswith('mqtt')
                        and f['path'] != 'ha_discovery_prefix']
        
        mqtt_fields = [f for f in all_fields 
                      if f['type'] != 'section'
                      and (f['path'].startswith('mqtt') or f['path'] == 'ha_discovery_prefix')]
        
        # Sons: campos de sound_files (sem exibir path)
        sound_fields = [f for f in all_fields 
                       if f['path'].startswith('sound_files.')
                       and f['type'] != 'section']
        
        # Renderizar cada aba
        config_html = self._render_fields(config_fields, config_data, open_first=True)
        sounds_html = self._render_sound_uploads(config_data)
        wifi_html = self._render_wifi_tab(mqtt_fields, config_data)
        
        page = f'''<!DOCTYPE html>
<html lang="{self.tr.lang.replace('_', '-')}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{h('Timer configurator')}</title>
    <link rel="stylesheet" href="/static/style.css">
    <link rel="icon" type="image/svg+xml" href="{logo_path}">
    <meta http-equiv="refresh" content="300">
</head>
<body>
    <div class="container">
        <header>
            <img src="{logo_path}" alt="Nicolau dos Brinquedos" class="logo" id="logo-anim">
            <h1>{h('Settings')}</h1>
            <p class="subtitle">Nicolau dos Brinquedos &nbsp; @nicolaudosbrinquedos</p>
        </header>
        
        <nav class="tabs">
            <button class="tab active" data-tab="game">{h('Game')}</button>
            <button class="tab" data-tab="config">{h('Settings')}</button>
            <button class="tab" data-tab="sounds">{h('Sounds')}</button>
            <button class="tab" data-tab="wifi">{h('Wi-Fi / HA')}</button>
            <button class="tab" data-tab="status">{h('Status')}</button>
        </nav>
        
        <div id="tab-game" class="tab-content active">
            <h2>{h('Game control')}</h2>
            <p id="game-state" class="hint">{h('Loading...')}</p>
            <div class="form-actions">
                <button type="button" id="play-btn" class="btn btn-primary" onclick="control('play')" disabled>{h('Play')}</button>
                <label class="switch-row">
                    <span class="switch">
                        <input type="checkbox" id="accel-sw" onchange="control('accel')" disabled>
                        <span class="slider"></span>
                    </span>
                    <span id="accel-label">{h('Acceleration')}</span>
                </label>
                <button type="button" id="stop-btn" class="btn btn-secondary" onclick="control('stop')" disabled>{h('Stop')}</button>
                <button type="button" id="reset-btn" class="btn btn-secondary" onclick="control('reset')" disabled>{h('Reset')}</button>
            </div>
            <p class="hint">{h('Play is the green button (START). The acceleration switch is the yellow and blue buttons: on, the time runs fast; off, at 1x (TIME TRAP). Stop is the red button (grants access). Reset puts the timer back in its initial condition.')}</p>
        </div>

        <div id="tab-config" class="tab-content">
            <form id="config-form" onsubmit="return saveConfig(event)">
                {config_html}
            </form>
        </div>
        
        <div id="tab-sounds" class="tab-content">
            <h2>{h('Upload sounds')}</h2>
            <p class="hint">{h('Pick the channel and upload the file.')}</p>
            <div id="sound-uploads">
                {sounds_html}
            </div>
        </div>
        
        <div id="tab-wifi" class="tab-content">
            {wifi_html}
        </div>
        
        <div id="tab-status" class="tab-content">
            <h2>{h('System status')}</h2>
            <div id="system-status">
                <div class="loading">{h('Loading...')}</div>
            </div>
        </div>
        
        <div class="form-actions-global">
            <button type="button" class="btn btn-primary" onclick="saveActiveTab()">{h('Save settings')}</button>
            <button type="button" class="btn btn-secondary" onclick="reloadPuzzle()">{h('Restart the game')}</button>
        </div>
        
        <div id="toast" class="toast hidden"></div>
    </div>
    
    <script>
    var I18N = __I18N__;
    function L(k) {{
        var s = I18N[k] || k;
        for (var i = 1; i < arguments.length; i++) s = s.replace('{{' + (i - 1) + '}}', arguments[i]);
        return s;
    }}

    function toast(msg, type) {{
        var t = document.getElementById('toast');
        t.textContent = msg;
        t.className = 'toast ' + (type || 'info') + ' show';
        setTimeout(function() {{ t.className = 'toast hidden'; }}, 3000);
    }}
    
    function api(method, path, body, callback) {{
        var xhr = new XMLHttpRequest();
        xhr.open(method, path, true);
        xhr.setRequestHeader('Content-Type', 'application/json');
        xhr.onload = function() {{
            var data = null;
            try {{ data = JSON.parse(xhr.responseText); }} catch(e) {{ data = xhr.responseText; }}
            callback(data, xhr.status);
        }};
        xhr.onerror = function() {{ toast(L('Connection error'), 'error'); }};
        if (body) xhr.send(JSON.stringify(body));
        else xhr.send();
    }}
    
    function saveActiveTab() {{
        // Coleta TODOS os campos com name da pagina inteira
        var data = {{}};
        document.querySelectorAll('[name]').forEach(function(input) {{
            var path = input.name;
            var keys = path.split('.');
            var value = null;
            
            if (input.type === 'checkbox') {{
                value = input.checked;
            }} else if (input.type === 'number') {{
                value = parseFloat(input.value) || 0;
            }} else if (input.type === 'password') {{
                value = input.value || input.dataset.original;
            }} else {{
                value = input.value;
            }}
            
            var d = data;
            for (var i = 0; i < keys.length - 1; i++) {{
                if (!d[keys[i]]) d[keys[i]] = {{}};
                d = d[keys[i]];
            }}
            d[keys[keys.length - 1]] = value;
        }});
        
        api('POST', '/api/config', data, function(resp, status) {{
            if (status === 200) toast(L('Settings saved!'), 'success');
            else toast(L('Error: {{0}}', JSON.stringify(resp)), 'error');
        }});
    }}
    
    document.querySelectorAll('.tab').forEach(function(tab) {{
        tab.addEventListener('click', function() {{
            document.querySelectorAll('.tab').forEach(function(t) {{ t.classList.remove('active'); }});
            document.querySelectorAll('.tab-content').forEach(function(c) {{ c.classList.remove('active'); }});
            tab.classList.add('active');
            document.getElementById('tab-' + tab.dataset.tab).classList.add('active');
        }});
    }});
    
    function saveConfig(event) {{
        event.preventDefault();
        var form = event.target;
        var data = {{}};
        
        form.querySelectorAll('[name]').forEach(function(input) {{
            var path = input.name;
            var keys = path.split('.');
            var value = null;
            
            if (input.type === 'checkbox') {{
                value = input.checked;
            }} else if (input.type === 'number') {{
                value = parseFloat(input.value) || 0;
            }} else if (input.type === 'password') {{
                value = input.value || input.dataset.original;
            }} else {{
                value = input.value;
            }}
            
            var d = data;
            for (var i = 0; i < keys.length - 1; i++) {{
                if (!d[keys[i]]) d[keys[i]] = {{}};
                d = d[keys[i]];
            }}
            d[keys[keys.length - 1]] = value;
        }});
        
        api('POST', '/api/config', data, function(resp, status) {{
            if (status === 200) toast(L('Settings saved!'), 'success');
            else toast(L('Error: {{0}}', JSON.stringify(resp)), 'error');
        }});
        return false;
    }}
    
    function reloadPuzzle() {{
        api('POST', '/api/reload', {{}}, function(resp, status) {{
            if (status === 200) toast(L('Game restarted!'), 'success');
            else toast(L('Error: {{0}}', JSON.stringify(resp)), 'error');
        }});
    }}
    
    document.querySelectorAll('.sound-upload-btn').forEach(function(btn) {{
        btn.addEventListener('click', function() {{
            var field = this.dataset.field;
            var input = document.getElementById('file-' + field.replace(/\\./g, '-'));
            var file = input.files[0];
            if (!file) {{ toast(L('Choose a file'), 'warning'); return; }}
            
            var formData = new FormData();
            formData.append('file', file);
            
            var xhr = new XMLHttpRequest();
            xhr.open('POST', '/api/upload/' + field, true);
            xhr.onload = function() {{
                try {{
                    var resp = JSON.parse(xhr.responseText);
                    if (xhr.status === 200) toast(resp.message || L('Upload OK!'), 'success');
                    else toast(L('Error: {{0}}', resp.error || xhr.responseText), 'error');
                }} catch(e) {{
                    toast(L('Upload finished'), 'success');
                }}
                var label = document.getElementById('label-' + field.replace(/\\./g, '-'));
                if (label) label.textContent = file.name;
            }};
            xhr.send(formData);
        }});
    }});
    
    function scanWiFi() {{
        var el = document.getElementById('wifi-scan-result');
        el.innerHTML = '<div class="loading">' + L('Scanning...') + '</div>';
        api('GET', '/api/wifi/scan', null, function(nets, status) {{
            if (status !== 200 || !nets || nets.length === 0) {{
                el.innerHTML = '<p class="error">' + L('No network found.') + '</p>';
                return;
            }}
            var html = '<table><tr><th>SSID</th><th>' + L('Signal') + '</th><th></th></tr>';
            nets.forEach(function(n) {{
                var sigClass = n.signal > -50 ? 'good' : (n.signal > -70 ? 'ok' : 'weak');
                html += '<tr onclick="document.getElementById(\\'wifi-ssid\\').value=\\'' + n.ssid.replace(/'/g, "\\\\'") + '\\'">' +
                    '<td>' + n.ssid + '</td>' +
                    '<td><span class="signal-' + sigClass + '">' + n.signal + ' dBm</span></td>' +
                    '<td><button class="btn-small">' + L('Use') + '</button></td></tr>';
            }});
            html += '</table>';
            el.innerHTML = html;
        }});
    }}
    
    function connectWiFi() {{
        var ssid = document.getElementById('wifi-ssid').value;
        var pass = document.getElementById('wifi-password').value;
        if (!ssid) {{ toast(L('Type the network name'), 'warning'); return; }}
        if (!pass) {{ toast(L('Type the password'), 'warning'); return; }}
        
        api('POST', '/api/wifi/connect', {{ssid: ssid, password: pass}}, function(resp, status) {{
            if (status === 200 && resp.success) {{
                toast(L('Connected to {{0}}', ssid + (resp.ip ? ' (' + resp.ip + ')' : '')), 'success');
            }} else {{
                toast(L('Error: {{0}}', resp.error || L('connection failed')), 'error');
            }}
        }});
    }}
    
    function toggleAP() {{
        api('POST', '/api/wifi/ap', {{}}, function(resp, status) {{
            if (status === 200 && resp.success) {{
                toast(L('Access point: {{0}}', resp.ssid || L('on')), 'success');
                if (resp.ssid) document.getElementById('ap-ssid').textContent = resp.ssid;
            }} else {{
                toast(L('Access point error: {{0}}', resp.error || L('connection failed')), 'error');
            }}
        }});
    }}
    
    function loadStatus() {{
        api('GET', '/api/status', null, function(data, code) {{
            var el = document.getElementById('system-status');
            if (code !== 200) {{
                el.innerHTML = '<p class="error">' + L('Could not load the status') + '</p>';
                return;
            }}
            var html = '';
            for (var k in data) {{
                var v = data[k];
                if (v === null || v === undefined) v = '-';
                else if (typeof v === 'object') v = JSON.stringify(v);
                html += '<div class=\\"status-item\\"><span class=\\"status-key\\">' + k + '</span><span class=\\"status-val\\">' + v + '</span></div>';
            }}
            el.innerHTML = '<div class=\\"status-grid\\">' + html + '</div>';
        }});
    }}
    
    loadStatus();

    var STATE_NAMES = {{
        idle: L('Waiting for the game to start'), running_1x: L('Running at 1x, waiting for the first button'),
        pause_initial: L('Acceleration starting'), running_2x: L('Acceleration ON'),
        trap_held: L('Acceleration OFF (TIME TRAP active)'), solved: L('Access granted'), game_over: L('Time is up')
    }};

    function loadGame() {{
        api('GET', '/api/game', null, function(g, code) {{
            var play = document.getElementById('play-btn');
            var accel = document.getElementById('accel-sw');
            var accelLabel = document.getElementById('accel-label');
            var stop = document.getElementById('stop-btn');
            var reset = document.getElementById('reset-btn');
            var info = document.getElementById('game-state');
            play.disabled = accel.disabled = stop.disabled = reset.disabled = true;
            accel.checked = false;
            if (code !== 200 || !g.available) {{
                info.textContent = L('Game unavailable');
                return;
            }}
            var t = (g.remaining_s !== undefined) ? ' - ' + L('{{0}} left', Math.floor(g.remaining_s / 60) + ':' + ('0' + (g.remaining_s % 60)).slice(-2)) : '';
            var name = STATE_NAMES[g.state] || g.state;
            info.textContent = name + t;
            play.disabled = !(g.state === 'idle' || g.state === 'solved' || g.state === 'game_over');
            accel.disabled = !(g.state === 'running_1x' || g.state === 'running_2x' || g.state === 'trap_held');
            accel.checked = (g.state === 'running_2x' || g.state === 'pause_initial');
            accelLabel.textContent = accel.checked ? L('Acceleration on') : L('Acceleration off');
            reset.disabled = (g.state === 'idle');
            stop.disabled = !(g.state === 'running_1x' || g.state === 'pause_initial' || g.state === 'running_2x' || g.state === 'trap_held');
        }});
    }}

    function control(action) {{
        if (action === 'stop' && !confirm(L('Grant access and end the game?'))) return;
        if (action === 'reset' && !confirm(L('Reset the timer to its initial condition?'))) return;
        api('POST', '/api/control', {{action: action}}, function(resp, code) {{
            if (code !== 200) toast(L('Could not send the command'), 'error');
            setTimeout(loadGame, 300);
        }});
    }}

    loadGame();
    setInterval(loadGame, 1000);
    </script>
</body>
</html>'''
        used = sorted(set(re.findall(r"\bL\('([^']*)'", page)))
        i18n = json.dumps({m: self.tr.gettext(m) for m in used}, ensure_ascii=False).replace('</', '<\\/')
        return page.replace('__I18N__', i18n)
    
    def _h(self, key, *args):
        return html_mod.escape(self.tr.gettext(key, *args))

    def _label(self, field):
        """Field label in the system language; the label derived from the key when there is no translation."""
        text = FIELD_LABELS.get(field.get('key', ''))
        return self.tr.gettext(text) if text else field['label']

    def _render_fields(self, fields, config_data, open_first=False):
        """Renderiza lista de campos como seção única."""
        if not fields:
            return '<p class="hint">' + html_mod.escape(self.tr.gettext('No configurable fields.')) + '</p>'
        
        html = ''
        open_attr = ' open' if open_first else ''
        html += f'<details{open_attr}>\n<summary class="section-title">{html_mod.escape(self.tr.gettext('General'))}</summary>\n<div class="section-body">\n'
        for fd in fields:
            html += self._render_field(fd, config_data)
        html += '</div>\n</details>\n'
        return html
    
    def _render_wifi_tab(self, mqtt_fields, config_data):
        """Renderiza a aba WiFi / HA com MQTT config e controles de rede."""
        mqtt_html = ''
        for fd in mqtt_fields:
            mqtt_html += self._render_field(fd, config_data)
        
        return f'''<h2>{self._h('Wi-Fi connection')}</h2>
<div class="wifi-client">
    <h3>{self._h('Join a Wi-Fi network')}</h3>
    <div id="wifi-scan-result"></div>
    <button type="button" class="btn btn-primary" onclick="scanWiFi()">{self._h('Scan networks')}</button>
    <div class="form-group">
        <label for="wifi-ssid">{self._h('Network name (SSID)')}</label>
        <input type="text" id="wifi-ssid" placeholder="{self._h('Type the network name')}" class="form-input">
    </div>
    <div class="form-group">
        <label for="wifi-password">{self._h('Password')}</label>
        <input type="password" id="wifi-password" placeholder="{self._h('Wi-Fi password')}" class="form-input">
    </div>
    <button type="button" class="btn btn-primary" onclick="connectWiFi()">{self._h('Connect')}</button>
</div>
<div class="wifi-ap">
    <h3>{self._h('Access point mode')}</h3>
    <p class="hint">{self._h('Turn on the access point to configure without a Wi-Fi network. Name:')} <span id="ap-ssid">Nicolau-XXXX</span></p>
    <button type="button" class="btn btn-warning" onclick="toggleAP()">{self._h('Turn the access point on/off')}</button>
</div>
<h2 style="margin-top:24px">{self._h('MQTT / Home Assistant')}</h2>
<div class="ha-fields">
    {mqtt_html}
</div>'''
    
    def _render_field(self, field, config_data):
        """Renderiza um campo individual."""
        path = field['path']
        label = html_mod.escape(self._label(field))
        
        value = self._get_value(path, config_data)
        placeholder = html_mod.escape(str(value) if value is not None else '')
        ft = field['type']
        
        if ft == 'bool':
            checked = ' checked' if value else ''
            return f'''<div class="form-group switch-group">
    <label class="switch-label">
        <span class="switch-text">{label}</span>
        <div class="switch">
            <input type="checkbox" name="{html_mod.escape(path)}" role="switch"{checked}>
            <span class="slider"></span>
        </div>
    </label>
</div>'''
        
        if ft in ('file_audio', 'file_image', 'file_path'):
            name = html_mod.escape(path).replace('.', '-')
            current_path = html_mod.escape(str(value) if value else '')
            return f'''<div class="form-group file-group">
    <label>{label}</label>
    <div class="file-input-row">
        <input type="file" id="file-{name}" accept="audio/*" class="file-input">
        <button type="button" class="btn btn-small btn-upload sound-upload-btn" data-field="{html_mod.escape(path)}" data-path="{current_path}">{self._h('Upload')}</button>
    </div>
    <input type="hidden" name="{html_mod.escape(path)}" value="{current_path}">
</div>'''
        
        if ft == 'password':
            orig = html_mod.escape(str(value) if value else '')
            return f'''<div class="form-group">
    <label for="field-{html_mod.escape(path).replace('.', '-')}">{label}</label>
    <input type="password" id="field-{html_mod.escape(path).replace('.', '-')}" 
           name="{html_mod.escape(path)}" 
           placeholder="********" 
           data-original="{orig}"
           class="form-input">
    <span class="hint">{self._h('Leave blank to keep the current password')}</span>
</div>'''
        
        if ft == 'text':
            text_hint = self._h('Use \\n or Enter to start a new line on the TV')
            return f'''<div class="form-group">
    <label for="field-{html_mod.escape(path).replace('.', '-')}">{label}</label>
    <textarea id="field-{html_mod.escape(path).replace('.', '-')}" 
              name="{html_mod.escape(path)}" 
              placeholder="{placeholder}"
              rows="2"
              class="form-input">{html_mod.escape(str(value) if value else '')}</textarea>
    <span class="hint">{text_hint}</span>
</div>'''
        
        if ft == 'number':
            min_v = field.get('min', 0)
            max_v = field.get('max', 999999)
            step_v = field.get('step', 1)
            unit = ''
            if field.get('unit'):
                unit = ' ' + (self.tr.gettext('(s)') if field.get('unit') == 'segundos' else field['unit'])
            return f'''<div class="form-group">
    <label for="field-{html_mod.escape(path).replace('.', '-')}">{label}{unit}</label>
    <input type="number" id="field-{html_mod.escape(path).replace('.', '-')}" 
           name="{html_mod.escape(path)}" 
           value="{html_mod.escape(str(value) if value is not None else '0')}"
           min="{min_v}" max="{max_v}" step="{step_v}"
           class="form-input">
</div>'''
        
        return f'''<div class="form-group">
    <label for="field-{html_mod.escape(path).replace('.', '-')}">{label}</label>
    <input type="text" id="field-{html_mod.escape(path).replace('.', '-')}" 
           name="{html_mod.escape(path)}" 
           value="{html_mod.escape(str(value) if value is not None else '')}"
           placeholder="{placeholder}"
           maxlength="{field.get('max_length', 256)}"
           class="form-input">
</div>'''
    
    def _render_sound_uploads(self, config_data):
        """Renderiza upload de sons sem exibir paths."""
        sounds = config_data.get('sound_files', {})
        if not sounds:
            return '<p>' + html_mod.escape(self.tr.gettext('No sound configured.')) + '</p>'
        
        html = ''
        for key, path in sounds.items():
            name = html_mod.escape(self.tr.gettext(SOUND_LABELS[key]) if key in SOUND_LABELS else key)
            field = f'sound_files.{key}'
            fid = field.replace('.', '-')
            display_name = os.path.basename(str(path)) if path and '/' in str(path) else self.tr.gettext('none')
            html += f'''<div class="sound-upload-row">
    <div class="sound-info">
        <strong>{name}</strong>
        <span class="file-path" id="label-{fid}">{html_mod.escape(display_name)}</span>
    </div>
    <div class="sound-actions">
        <input type="file" id="file-{fid}" accept="audio/*" class="file-input">
        <button type="button" class="btn btn-small btn-upload sound-upload-btn" data-field="{html_mod.escape(field)}">{self._h('Upload')}</button>
    </div>
</div>'''
        return html
    
    def _get_value(self, path, data):
        """Navega no dict aninhado pelo path notado."""
        keys = path.split('.')
        d = data
        for k in keys:
            if isinstance(d, dict) and k in d:
                d = d[k]
            else:
                return None
        return d
