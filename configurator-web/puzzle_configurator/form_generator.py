#!/usr/bin/env python3
"""
puzzle_configurator/form_generator.py — Renderizador de Formulário HTML Dinâmico

Gera HTML puro (sem framework JS) a partir do schema parseado pelo JsonParser.
Renderiza inputs, checkboxes, file uploads, selects, sections com accordion.
"""

import html as html_mod
import os
from .json_parser import JsonParser


class FormGenerator:
    """Gera HTML de formulário a partir do schema de campos."""
    
    def generate(self, config_data, logo_path='/static/logoNicolaudosBrinquedos.svg'):
        """
        Gera página HTML completa com formulário dinâmico.
        
        Args:
            config_data: dict completo do config.json
            logo_path: path para o logo SVG
        
        Returns:
            string HTML
        """
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
        
        return f'''<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Configurador de Puzzle</title>
    <link rel="stylesheet" href="/static/style.css">
    <link rel="icon" type="image/svg+xml" href="{logo_path}">
    <meta http-equiv="refresh" content="300">
</head>
<body>
    <div class="container">
        <header>
            <img src="{logo_path}" alt="Nicolau dos Brinquedos" class="logo" id="logo-anim">
            <h1>Configurações</h1>
            <p class="subtitle">Nicolau dos Brinquedos &nbsp; @nicolaudosbrinquedos</p>
        </header>
        
        <nav class="tabs">
            <button class="tab active" data-tab="config">Configuração</button>
            <button class="tab" data-tab="sounds">Sons</button>
            <button class="tab" data-tab="wifi">WiFi / HA</button>
            <button class="tab" data-tab="status">Status</button>
        </nav>
        
        <div id="tab-config" class="tab-content active">
            <form id="config-form" onsubmit="return saveConfig(event)">
                {config_html}
            </form>
        </div>
        
        <div id="tab-sounds" class="tab-content">
            <h2>Upload de Sons</h2>
            <p class="hint">Selecione o canal e faça upload do arquivo.</p>
            <div id="sound-uploads">
                {sounds_html}
            </div>
        </div>
        
        <div id="tab-wifi" class="tab-content">
            {wifi_html}
        </div>
        
        <div id="tab-status" class="tab-content">
            <h2>Status do Sistema</h2>
            <div id="system-status">
                <div class="loading">Carregando...</div>
            </div>
        </div>
        
        <div class="form-actions-global">
            <button type="button" class="btn btn-primary" onclick="saveActiveTab()">Salvar Configuração</button>
            <button type="button" class="btn btn-secondary" onclick="reloadPuzzle()">Recarregar Puzzle</button>
        </div>
        
        <div id="toast" class="toast hidden"></div>
    </div>
    
    <script>
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
        xhr.onerror = function() {{ toast('Erro de conexao', 'error'); }};
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
            if (status === 200) toast('Configuracao salva!', 'success');
            else toast('Erro: ' + JSON.stringify(resp), 'error');
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
            if (status === 200) toast('Configuracao salva!', 'success');
            else toast('Erro: ' + JSON.stringify(resp), 'error');
        }});
        return false;
    }}
    
    function reloadPuzzle() {{
        api('POST', '/api/reload', {{}}, function(resp, status) {{
            if (status === 200) toast('Puzzle recarregado!', 'success');
            else toast('Erro: ' + JSON.stringify(resp), 'error');
        }});
    }}
    
    document.querySelectorAll('.sound-upload-btn').forEach(function(btn) {{
        btn.addEventListener('click', function() {{
            var field = this.dataset.field;
            var input = document.getElementById('file-' + field.replace(/\\./g, '-'));
            var file = input.files[0];
            if (!file) {{ toast('Selecione um arquivo', 'warning'); return; }}
            
            var formData = new FormData();
            formData.append('file', file);
            
            var xhr = new XMLHttpRequest();
            xhr.open('POST', '/api/upload/' + field, true);
            xhr.onload = function() {{
                try {{
                    var resp = JSON.parse(xhr.responseText);
                    if (xhr.status === 200) toast(resp.message || 'Upload OK!', 'success');
                    else toast('Erro: ' + (resp.error || xhr.responseText), 'error');
                }} catch(e) {{
                    toast('Upload concluido', 'success');
                }}
                var label = document.getElementById('label-' + field.replace(/\\./g, '-'));
                if (label) label.textContent = file.name;
            }};
            xhr.send(formData);
        }});
    }});
    
    function scanWiFi() {{
        var el = document.getElementById('wifi-scan-result');
        el.innerHTML = '<div class="loading">Escaneando...</div>';
        api('GET', '/api/wifi/scan', null, function(nets, status) {{
            if (status !== 200 || !nets || nets.length === 0) {{
                el.innerHTML = '<p class="error">Nenhuma rede encontrada.</p>';
                return;
            }}
            var html = '<table><tr><th>SSID</th><th>Sinal</th><th></th></tr>';
            nets.forEach(function(n) {{
                var sigClass = n.signal > -50 ? 'good' : (n.signal > -70 ? 'ok' : 'weak');
                html += '<tr onclick="document.getElementById(\\'wifi-ssid\\').value=\\'' + n.ssid.replace(/'/g, "\\\\'") + '\\'">' +
                    '<td>' + n.ssid + '</td>' +
                    '<td><span class="signal-' + sigClass + '">' + n.signal + ' dBm</span></td>' +
                    '<td><button class="btn-small">Usar</button></td></tr>';
            }});
            html += '</table>';
            el.innerHTML = html;
        }});
    }}
    
    function connectWiFi() {{
        var ssid = document.getElementById('wifi-ssid').value;
        var pass = document.getElementById('wifi-password').value;
        if (!ssid) {{ toast('Digite o SSID', 'warning'); return; }}
        if (!pass) {{ toast('Digite a senha', 'warning'); return; }}
        
        api('POST', '/api/wifi/connect', {{ssid: ssid, password: pass}}, function(resp, status) {{
            if (status === 200 && resp.success) {{
                toast('Conectado a ' + ssid + (resp.ip ? ' (' + resp.ip + ')' : ''), 'success');
            }} else {{
                toast('Erro: ' + (resp.error || 'falha na conexao'), 'error');
            }}
        }});
    }}
    
    function toggleAP() {{
        api('POST', '/api/wifi/ap', {{}}, function(resp, status) {{
            if (status === 200 && resp.success) {{
                toast('AP: ' + (resp.ssid || 'ativado'), 'success');
                if (resp.ssid) document.getElementById('ap-ssid').textContent = resp.ssid;
            }} else {{
                toast('Erro AP: ' + (resp.error || 'falha'), 'error');
            }}
        }});
    }}
    
    function loadStatus() {{
        api('GET', '/api/status', null, function(data, code) {{
            var el = document.getElementById('system-status');
            if (code !== 200) {{
                el.innerHTML = '<p class="error">Erro carregando status</p>';
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
    </script>
</body>
</html>'''
    
    def _render_fields(self, fields, config_data, open_first=False):
        """Renderiza lista de campos como seção única."""
        if not fields:
            return '<p class="hint">Nenhum campo configurável.</p>'
        
        html = ''
        open_attr = ' open' if open_first else ''
        html += f'<details{open_attr}>\n<summary class="section-title">Geral</summary>\n<div class="section-body">\n'
        for fd in fields:
            html += self._render_field(fd, config_data)
        html += '</div>\n</details>\n'
        return html
    
    def _render_wifi_tab(self, mqtt_fields, config_data):
        """Renderiza a aba WiFi / HA com MQTT config e controles de rede."""
        mqtt_html = ''
        for fd in mqtt_fields:
            mqtt_html += self._render_field(fd, config_data)
        
        return f'''<h2>Conexao WiFi</h2>
<div class="wifi-client">
    <h3>Conectar a Rede WiFi</h3>
    <div id="wifi-scan-result"></div>
    <button type="button" class="btn btn-primary" onclick="scanWiFi()">Escanear Redes</button>
    <div class="form-group">
        <label for="wifi-ssid">SSID</label>
        <input type="text" id="wifi-ssid" placeholder="Digite o SSID" class="form-input">
    </div>
    <div class="form-group">
        <label for="wifi-password">Senha</label>
        <input type="password" id="wifi-password" placeholder="Senha da rede WiFi" class="form-input">
    </div>
    <button type="button" class="btn btn-primary" onclick="connectWiFi()">Conectar</button>
</div>
<div class="wifi-ap">
    <h3>Modo Access Point</h3>
    <p class="hint">Ative o AP para configurar sem rede WiFi. SSID: <span id="ap-ssid">Nicolau-XXXX</span></p>
    <button type="button" class="btn btn-warning" onclick="toggleAP()">Ativar/Desativar AP</button>
</div>
<h2 style="margin-top:24px">Conexao MQTT / Home Assistant</h2>
<div class="ha-fields">
    {mqtt_html}
</div>'''
    
    def _render_field(self, field, config_data):
        """Renderiza um campo individual."""
        path = field['path']
        label = html_mod.escape(field['label'])
        
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
        <button type="button" class="btn btn-small btn-upload sound-upload-btn" data-field="{html_mod.escape(path)}" data-path="{current_path}">Upload</button>
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
    <span class="hint">Deixe em branco para manter a senha atual</span>
</div>'''
        
        if ft == 'text':
            return f'''<div class="form-group">
    <label for="field-{html_mod.escape(path).replace('.', '-')}">{label}</label>
    <textarea id="field-{html_mod.escape(path).replace('.', '-')}" 
              name="{html_mod.escape(path)}" 
              placeholder="{placeholder}"
              rows="2"
              class="form-input">{html_mod.escape(str(value) if value else '')}</textarea>
    <span class="hint">Use \\n para pular linha no display</span>
</div>'''
        
        if ft == 'number':
            min_v = field.get('min', 0)
            max_v = field.get('max', 999999)
            step_v = field.get('step', 1)
            unit = ' ' + field.get('unit', '') if field.get('unit') else ''
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
            return '<p>Nenhum som configurado.</p>'
        
        html = ''
        for key, path in sounds.items():
            name = html_mod.escape(key)
            field = f'sound_files.{key}'
            fid = field.replace('.', '-')
            display_name = os.path.basename(str(path)) if path and '/' in str(path) else 'nenhum'
            html += f'''<div class="sound-upload-row">
    <div class="sound-info">
        <strong>{name}</strong>
        <span class="file-path" id="label-{fid}">{html_mod.escape(display_name)}</span>
    </div>
    <div class="sound-actions">
        <input type="file" id="file-{fid}" accept="audio/*" class="file-input">
        <button type="button" class="btn btn-small btn-upload sound-upload-btn" data-field="{html_mod.escape(field)}">Upload</button>
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
