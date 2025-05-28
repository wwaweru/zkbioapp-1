from django.core.management.base import BaseCommand, CommandError
import subprocess
import sys
from pathlib import Path

class Command(BaseCommand):
    help = 'Uninstall ZKBio Sync Windows Service'

    def add_arguments(self, parser):
        parser.add_argument(
            '--python-path',
            type=str,
            help='Path to Python executable (default: current Python)',
            default=sys.executable
        )
        parser.add_argument(
            '--service-name',
            type=str,
            default='ZKBioSyncService',
            help='Windows service name (default: ZKBioSyncService)'
        )

    def handle(self, *args, **options):
        try:
            import win32serviceutil
        except ImportError:
            raise CommandError(
                'pywin32 is required for Windows service management. Install with: pip install pywin32'
            )

        service_script = Path(__file__).parent.parent.parent / 'windows_service.py'
        python_path = options['python_path']
        service_name = options['service_name']

        self.stdout.write('Uninstalling ZKBio Sync Windows Service...')

        try:
            # Stop the service first
            stop_cmd = ['net', 'stop', service_name]
            subprocess.run(stop_cmd, capture_output=True, text=True)
            
            # Uninstall the service
            cmd = [python_path, str(service_script), 'remove']
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            self.stdout.write(
                self.style.SUCCESS(f'✓ Service "{service_name}" uninstalled successfully')
            )
            
            if result.stdout:
                self.stdout.write(f'Output: {result.stdout}')

        except subprocess.CalledProcessError as e:
            if 'does not exist' in e.stderr:
                self.stdout.write(
                    self.style.WARNING(f'Service "{service_name}" was not installed')
                )
            else:
                raise CommandError(f'Failed to uninstall service: {e.stderr}')
        except Exception as e:
            raise CommandError(f'Uninstallation error: {str(e)}')