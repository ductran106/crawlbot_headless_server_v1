# Giám sát hệ thống
# src/monitoring/system_monitor.py
import threading
import time
import psutil

from ..utils.logger import log, logging
from ..notification.telegram import send_alert

class SystemMonitor:
    """Giám sát tài nguyên hệ thống"""
    
    def __init__(self, check_interval=60):
        """Khởi tạo SystemMonitor"""
        self.check_interval = check_interval
        self.running = False
        self.monitor_thread = None
    
    def start_monitoring(self):
        """Bắt đầu giám sát hệ thống"""
        if not self.running:
            self.running = True
            self.monitor_thread = threading.Thread(target=self.monitor_resources, daemon=True)
            self.monitor_thread.start()
            log("Hệ thống giám sát đã khởi động")
            return True
        return False
    
    def stop_monitoring(self):
        """Dừng giám sát hệ thống"""
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=1)
        log("Hệ thống giám sát đã dừng")
        return True
    
    def monitor_resources(self):
        """Theo dõi tài nguyên hệ thống"""
        while self.running:
            try:
                # Kiểm tra CPU
                cpu_percent = psutil.cpu_percent(interval=1)
                if cpu_percent > 90:
                    alert_msg = f"⚠️ Cảnh báo: CPU sử dụng cao ({cpu_percent}%)"
                    log(alert_msg, level=logging.WARNING)
                    send_alert(alert_msg)
                
                # Kiểm tra RAM
                memory = psutil.virtual_memory()
                if memory.percent > 90:
                    alert_msg = f"⚠️ Cảnh báo: RAM sử dụng cao ({memory.percent}%)"
                    log(alert_msg, level=logging.WARNING)
                    send_alert(alert_msg)
                
                # Kiểm tra ổ đĩa
                disk = psutil.disk_usage('/')
                if disk.percent > 90:
                    alert_msg = f"⚠️ Cảnh báo: Ổ đĩa sắp đầy ({disk.percent}%)"
                    log(alert_msg, level=logging.WARNING)
                    send_alert(alert_msg)
                
                # Kiểm tra Chrome
                chrome_processes = []
                for proc in psutil.process_iter(['pid', 'name', 'memory_info']):
                    if 'chrome' in proc.info['name'].lower():
                        chrome_processes.append(proc)
                
                if chrome_processes:
                    total_chrome_memory = sum(proc.info['memory_info'].rss for proc in chrome_processes) / (1024 * 1024)
                    if total_chrome_memory > 2000:  # 2GB
                        alert_msg = f"⚠️ Cảnh báo: Chrome sử dụng nhiều RAM ({total_chrome_memory:.2f} MB)"
                        log(alert_msg, level=logging.WARNING)
                        send_alert(alert_msg)
                
                time.sleep(self.check_interval)
            except Exception as e:
                log(f"Lỗi khi giám sát tài nguyên: {str(e)}", level=logging.ERROR)
                time.sleep(60)  # Nếu lỗi, đợi 1 phút trước khi thử lại