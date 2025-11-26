"""
Friday AI - Homelab Monitoring Agent
Monitors system resources and sends alerts via Telegram
"""
import os
import time
import subprocess
import psutil
import requests
import json
import urllib3
from datetime import datetime
from notify import FridayNotifier
from dotenv import load_dotenv

# Disable SSL warnings for self-signed certificates
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

load_dotenv()

class HomelabMonitor:
    def __init__(self):
        self.notifier = FridayNotifier()
        self.friday_api = os.getenv("FRIDAY_API_URL", "http://localhost:8080")
        self.api_key = os.getenv("FRIDAY_API_KEY")
        
        # Alert thresholds
        self.gpu_temp_threshold = 85  # °C
        self.gpu_util_threshold = 95  # %
        self.disk_usage_threshold = 90  # %
        self.memory_threshold = 90  # %
        
        # Track alert states to avoid spam
        self.alert_states = {}
        self.alert_cooldown = 300  # 5 minutes between same alerts
        
        # Load external services configuration
        self.external_services = self.load_external_services()
    
    def load_external_services(self):
        """Load external services from config file"""
        config_path = "/home/artur/friday/config/external_services.json"
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
                return config.get('services', [])
        except Exception as e:
            print(f"Warning: Could not load external services config: {e}")
            return []
    
    def should_alert(self, alert_key: str) -> bool:
        """Check if we should send an alert (cooldown logic)"""
        now = time.time()
        last_alert = self.alert_states.get(alert_key, 0)
        
        if now - last_alert > self.alert_cooldown:
            self.alert_states[alert_key] = now
            return True
        return False
    
    def check_external_service(self, service: dict) -> bool:
        """Check if an external service is accessible"""
        try:
            response = requests.get(
                service['url'],
                timeout=service.get('timeout', 10),
                verify=service.get('verify_ssl', True),
                allow_redirects=True
            )
            # Consider any response as "up" (including auth errors)
            return response.status_code < 500
        except requests.exceptions.Timeout:
            return False
        except requests.exceptions.ConnectionError:
            return False
        except Exception as e:
            print(f"Error checking {service['name']}: {e}")
            return False
    
    def check_all_external_services(self) -> dict:
        """Check all external services and send alerts if down"""
        results = {}
        
        for service in self.external_services:
            name = service['name']
            is_up = self.check_external_service(service)
            results[name] = is_up
            
            # Alert if service is down
            if not is_up and self.should_alert(f"external_{name.lower()}_down"):
                self.notifier.send_alert(
                    f"{name} Unreachable",
                    f"{name} at {service['url']} is not responding!",
                    "error"
                )
            
            # Alert when service comes back up (if we had alerted before)
            if is_up and f"external_{name.lower()}_down" in self.alert_states:
                # Service recovered
                if self.should_alert(f"external_{name.lower()}_up"):
                    self.notifier.send_alert(
                        f"{name} Recovered",
                        f"{name} at {service['url']} is back online!",
                        "success"
                    )
        
        return results
    
    def check_services(self) -> dict:
        """Check if critical services are running"""
        services = {
            "vllm": "vllm.service",
            "friday": "friday.service",
            "telegram-bot": "telegram-bot.service"
        }
        
        results = {}
        for name, service in services.items():
            try:
                result = subprocess.run(
                    ["systemctl", "is-active", service],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                is_running = result.stdout.strip() == "active"
                results[name] = is_running
                
                # Alert if service is down
                if not is_running and self.should_alert(f"service_{name}_down"):
                    self.notifier.send_alert(
                        f"Service Down: {name}",
                        f"The {name} service is not running!",
                        "error"
                    )
            except Exception as e:
                results[name] = False
                print(f"Error checking {name}: {e}")
        
        return results
    
    def check_gpu(self) -> dict:
        """Monitor GPU temperature and utilization"""
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=temperature.gpu,utilization.gpu,memory.used,memory.total",
                 "--format=csv,noheader,nounits"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                temp, util, mem_used, mem_total = result.stdout.strip().split(", ")
                temp = int(temp)
                util = int(util)
                
                # Check temperature
                if temp > self.gpu_temp_threshold and self.should_alert("gpu_temp_high"):
                    self.notifier.send_alert(
                        "GPU Temperature High",
                        f"GPU temperature is {temp}°C (threshold: {self.gpu_temp_threshold}°C)",
                        "warning"
                    )
                
                # Check utilization
                if util > self.gpu_util_threshold and self.should_alert("gpu_util_high"):
                    self.notifier.send_alert(
                        "GPU Utilization High",
                        f"GPU utilization is {util}% (threshold: {self.gpu_util_threshold}%)",
                        "warning"
                    )
                
                return {
                    "temperature": temp,
                    "utilization": util,
                    "memory_used": int(mem_used),
                    "memory_total": int(mem_total)
                }
        except Exception as e:
            print(f"Error checking GPU: {e}")
        
        return {}
    
    def check_disk_usage(self) -> dict:
        """Monitor disk usage"""
        results = {}
        
        # Check main disk
        disk = psutil.disk_usage('/')
        disk_percent = disk.percent
        results['root'] = disk_percent
        
        if disk_percent > self.disk_usage_threshold and self.should_alert("disk_root_full"):
            self.notifier.send_alert(
                "Disk Space Low",
                f"Root partition is {disk_percent}% full ({disk.free // (1024**3)}GB free)",
                "warning"
            )
        
        # Check TrueNAS mount
        if os.path.ismount('/mnt/friday-pool'):
            vault_disk = psutil.disk_usage('/mnt/friday-pool')
            vault_percent = vault_disk.percent
            results['truenas'] = vault_percent
            
            if vault_percent > self.disk_usage_threshold and self.should_alert("disk_truenas_full"):
                self.notifier.send_alert(
                    "TrueNAS Disk Space Low",
                    f"TrueNAS mount is {vault_percent}% full ({vault_disk.free // (1024**3)}GB free)",
                    "warning"
                )
        else:
            results['truenas'] = None
            if self.should_alert("truenas_unmounted"):
                self.notifier.send_alert(
                    "TrueNAS Mount Missing",
                    "The TrueNAS share is not mounted!",
                    "error"
                )
        
        return results
    
    def check_memory(self) -> dict:
        """Monitor system memory"""
        memory = psutil.virtual_memory()
        mem_percent = memory.percent
        
        if mem_percent > self.memory_threshold and self.should_alert("memory_high"):
            self.notifier.send_alert(
                "Memory Usage High",
                f"System memory is {mem_percent}% used ({memory.available // (1024**3)}GB free)",
                "warning"
            )
        
        return {
            "percent": mem_percent,
            "available_gb": memory.available // (1024**3),
            "total_gb": memory.total // (1024**3)
        }
    
    def check_friday_api(self) -> dict:
        """Check Friday API health"""
        try:
            headers = {}
            if self.api_key:
                headers['X-API-Key'] = self.api_key
            
            response = requests.get(
                f"{self.friday_api}/health",
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                if self.should_alert("friday_api_down"):
                    self.notifier.send_alert(
                        "Friday API Error",
                        f"API returned status code {response.status_code}",
                        "error"
                    )
                return {}
        except Exception as e:
            if self.should_alert("friday_api_error"):
                self.notifier.send_alert(
                    "Friday API Unreachable",
                    f"Cannot connect to Friday API: {str(e)}",
                    "error"
                )
            return {}
    
    def send_status_report(self):
        """Send a comprehensive status report"""
        services = self.check_services()
        gpu = self.check_gpu()
        disk = self.check_disk_usage()
        memory = self.check_memory()
        friday = self.check_friday_api()
        external = self.check_all_external_services()
        
        status = {
            "🖥️ Local Services": "",
            "vLLM": "✅" if services.get("vllm") else "❌",
            "Friday API": "✅" if services.get("friday") else "❌",
            "Telegram Bot": "✅" if services.get("telegram-bot") else "❌",
            "": "",
            "🌐 External Services": "",
        }
        
        # Add external services
        for name, is_up in external.items():
            status[name] = "✅" if is_up else "❌"
        
        # Add system stats
        status.update({
            " ": "",
            "💻 System Stats": "",
            "GPU Temp": f"{gpu.get('temperature', 'N/A')}°C" if gpu else "N/A",
            "GPU Util": f"{gpu.get('utilization', 'N/A')}%" if gpu else "N/A",
            "Memory": f"{memory['percent']}%",
            "Disk (root)": f"{disk.get('root', 'N/A')}%",
            "Disk (TrueNAS)": f"{disk.get('truenas', 'N/A')}%" if disk.get('truenas') else "Not mounted",
            "  ": "",
            "📊 Friday Stats": "",
            "Vault Chunks": friday.get('obsidian_chunks', 'N/A'),
            "Memories": friday.get('memory_entries', 'N/A')
        })
        
        self.notifier.send_system_status(status)
    
    def run_monitoring_cycle(self):
        """Run one complete monitoring cycle"""
        print(f"[{datetime.now()}] Running monitoring cycle...")
        
        self.check_services()
        self.check_gpu()
        self.check_disk_usage()
        self.check_memory()
        self.check_friday_api()
        self.check_all_external_services()
        
        print("Monitoring cycle complete")
    
    def start(self, interval: int = 60):
        """Start continuous monitoring"""
        print("Starting Homelab Monitor...")
        self.notifier.send_alert(
            "Monitoring Started",
            f"Homelab monitoring is now active (check interval: {interval}s)\n"
            f"Monitoring {len(self.external_services)} external services",
            "success"
        )
        
        try:
            while True:
                self.run_monitoring_cycle()
                time.sleep(interval)
        except KeyboardInterrupt:
            print("\nStopping monitor...")
            self.notifier.send_alert(
                "Monitoring Stopped",
                "Homelab monitoring has been stopped",
                "info"
            )

if __name__ == "__main__":
    import sys
    
    monitor = HomelabMonitor()
    
    if len(sys.argv) > 1 and sys.argv[1] == "report":
        # Send a one-time status report
        monitor.send_status_report()
    else:
        # Start continuous monitoring
        interval = int(sys.argv[1]) if len(sys.argv) > 1 else 60
        monitor.start(interval)
