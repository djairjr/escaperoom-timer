#!/usr/bin/env python3
"""
puzzle_configurator/wifi_manager.py — Gerenciamento de WiFi via Sandbox

NÃO executa comandos diretamente. Escreve instruções em /sandbox/wifi/
O timer-watcher (root) pega e executa.

Comandos:
  /sandbox/wifi/connect       -> conteudo: "SSID|PASSWORD"
  /sandbox/wifi/ap_on          -> arquivo vazio (trigger)
  /sandbox/wifi/ap_off         -> arquivo vazio (trigger)

The access point itself (hostapd + dnsmasq) is owned by timer-ap.service from the
timer-nicolau-system package; this module only asks the watcher to start or stop it.

Respostas:
  /sandbox/wifi/connect_result -> "SSID|OK <ip>" or "SSID|FAIL <reason>" (escrito pelo watcher)
  /sandbox/wifi/scan_result    -> JSON com lista de SSIDs (escrito pelo watcher)
"""

import subprocess
import json
import os
import re
import logging
import time

logger = logging.getLogger(__name__)

SANDBOX_WIFI = '/sandbox/wifi/'
WPA_CONF = '/etc/wpa_supplicant/wpa_supplicant.conf'


class WiFiManager:
    """Gerencia WiFi escrevendo comandos no sandbox para o watcher processar."""
    
    def __init__(self, iface_ap='wlan1', iface_client='wlan0', ap_prefix='Nicolau'):
        self.iface_ap = iface_ap
        self.iface_client = iface_client
        self.ap_prefix = ap_prefix
    
    def scan_ssids(self):
        """
        Escaneia redes WiFi via sandbox (watcher faz scan como root).
        Escreve scan_request, watcher responde em scan_cache.json.
        """
        try:
            SANDBOX_WIFI = '/sandbox/wifi/'
            os.makedirs(SANDBOX_WIFI, exist_ok=True)
            
            # Trigger scan
            with open(os.path.join(SANDBOX_WIFI, 'scan_request'), 'w') as f:
                f.write('scan')
            
            # Aguardar cache ate 10s
            cache_path = os.path.join(SANDBOX_WIFI, 'scan_cache.json')
            for _ in range(20):
                time.sleep(0.5)
                if os.path.exists(cache_path):
                    with open(cache_path) as f:
                        try:
                            networks = json.load(f)
                        except:
                            networks = []
                    os.unlink(cache_path)
                    return networks
            
            return []
        except Exception as e:
            logger.error(f"Erro scan WiFi: {e}")
            return []
    
    def connect_client(self, ssid, password):
        """Escreve comando de conexão no sandbox."""
        try:
            os.makedirs(SANDBOX_WIFI, exist_ok=True)
            with open(os.path.join(SANDBOX_WIFI, 'connect'), 'w') as f:
                f.write(f"{ssid}|{password}")
            logger.info(f"WiFi connect escrito no sandbox: {ssid}")
            
            # Aguardar resultado (watcher responde em connect_result).
            # timer-wifi-connect waits up to 40 s for a DHCP address.
            for _ in range(55):
                time.sleep(1)
                result_path = os.path.join(SANDBOX_WIFI, 'connect_result')
                if os.path.exists(result_path):
                    with open(result_path) as f:
                        content = f.read().strip()
                    os.unlink(result_path)
                    outcome = content.split('|', 1)[1] if '|' in content else ''
                    if outcome.startswith('OK '):
                        return {'success': True, 'ip': outcome[3:], 'ssid': ssid, 'error': None}
                    return {'success': False, 'ip': None, 'ssid': ssid,
                            'error': outcome[5:] if outcome.startswith('FAIL ') else outcome}

            return {'success': False, 'ip': None, 'ssid': ssid, 'error': 'Timeout aguardando resultado'}
        except Exception as e:
            return {'success': False, 'ip': None, 'error': str(e)}
    
    def start_ap(self):
        """Pede ao watcher para ligar o AP (timer-ap.service). A senha do AP e a do login web."""
        try:
            ssid = f"{self.ap_prefix}-{self._get_mac_suffix()}"
            os.makedirs(SANDBOX_WIFI, exist_ok=True)
            with open(os.path.join(SANDBOX_WIFI, 'ap_on'), 'w') as f:
                f.write('')

            logger.info(f"AP solicitado: {ssid}")
            return {'success': True, 'ssid': ssid, 'error': None}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def stop_ap(self):
        """Solicita desativação do AP via sandbox."""
        try:
            os.makedirs(SANDBOX_WIFI, exist_ok=True)
            with open(os.path.join(SANDBOX_WIFI, 'ap_off'), 'w') as f:
                f.write('')
            return True
        except Exception as e:
            return False
    
    def get_status(self):
        """Status WiFi — só comandos de leitura seguros (the web user may run them)."""
        status = {
            'ap_active': False,
            'client_ip': None,
            'client_ssid': None,
        }
        # systemctl is-active (allowed to the web user)
        r = subprocess.run(['systemctl', 'is-active', 'timer-ap.service'],
                         capture_output=True, text=True, timeout=5)
        status['ap_active'] = r.stdout.strip() == 'active'
        
        # IP (seguro)
        r = subprocess.run(['ip', '-4', 'addr', 'show', self.iface_client],
                         capture_output=True, text=True, timeout=5)
        m = re.search(r'inet\s+(\d+\.\d+\.\d+\.\d+)', r.stdout)
        if m:
            status['client_ip'] = m.group(1)
        
        # SSID (iw link é leitura, seguro)
        r = subprocess.run(['iw', 'dev', self.iface_client, 'link'],
                         capture_output=True, text=True, timeout=5)
        m = re.search(r'SSID:\s*(.+)', r.stdout)
        if m:
            status['client_ssid'] = m.group(1).strip()
        
        return status
    
    def _get_mac_suffix(self):
        try:
            with open(f'/sys/class/net/{self.iface_ap}/address') as f:
                return f.read().strip().replace(':', '')[-4:].upper()
        except:
            return "XXXX"
