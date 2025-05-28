# zkbio_sync/windows_service.py
import win32serviceutil
import win32service
import win32event
import servicemanager
import socket
import sys
import os
import logging
from pathlib import Path

# Add Django project to Python path
project_path = Path(__file__).parent.parent
sys.path.insert(0, str(project_path))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'zkbio_sync.settings')
import django
django.setup()

from zkbio_sync.scheduler import sync_scheduler

class ZKBioSyncService(win32serviceutil.ServiceFramework):
    """Windows Service for ZKBio Sync Scheduler"""
    
    _svc_name_ = "ZKBioSyncService"
    _svc_display_name_ = "ZKBio ERP Sync Scheduler"
    _svc_description_ = "Automated synchronization service between ZKBio and ERP systems"
    
    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        socket.setdefaulttimeout(60)
        
        # Setup logging for Windows service
        self.setup_logging()
        
    def setup_logging(self):
        """Setup logging for Windows service"""
        log_path = Path(__file__).parent.parent / 'logs'
        log_path.mkdir(exist_ok=True)
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_path / 'zkbio_service.log'),
                logging.StreamHandler()
            ]
        )
        
        self.logger = logging.getLogger('ZKBioSyncService')

    def SvcStop(self):
        """Stop the service"""
        self.logger.info('Stopping ZKBio Sync Service...')
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        
        # Stop the scheduler
        sync_scheduler.stop()
        
        win32event.SetEvent(self.hWaitStop)
        self.logger.info('ZKBio Sync Service stopped')

    def SvcDoRun(self):
        """Run the service"""
        self.logger.info('Starting ZKBio Sync Service...')
        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STARTED,
            (self._svc_name_, '')
        )
        
        try:
            # Start the scheduler
            sync_scheduler.setup_schedules()
            self.logger.info('Scheduler configured, starting background thread...')
            sync_scheduler.start()
            
            # Wait for stop signal
            win32event.WaitForSingleObject(self.hWaitStop, win32event.INFINITE)
            
        except Exception as e:
            self.logger.error(f'Service error: {str(e)}')
            servicemanager.LogErrorMsg(f'ZKBio Sync Service error: {str(e)}')

if __name__ == '__main__':
    win32serviceutil.HandleCommandLine(ZKBioSyncService)