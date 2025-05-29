from django.apps import AppConfig
import threading
import time

class ZkbioSyncConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'zkbioapp'
    verbose_name = 'ZKBio ERP Synchronization'

    def ready(self):
        """Initialize the scheduler when Django starts"""
        # Only start scheduler in production/runserver, not during migrations
        import sys
        if 'runserver' in sys.argv or 'gunicorn' in sys.argv[0]:
            def delayed_start():
                # Wait a bit for Django to fully initialize
                time.sleep(5)
                try:
                    from .scheduler import sync_scheduler
                    sync_scheduler.start()
                    print("✓ Sync scheduler auto-started")
                except Exception as e:
                    print(f"Failed to auto-start scheduler: {e}")
            
            # Start in background thread to avoid blocking Django startup
            threading.Thread(target=delayed_start, daemon=True).start()