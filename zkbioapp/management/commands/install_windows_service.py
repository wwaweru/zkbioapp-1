from django.core.management.base import BaseCommand, CommandError
import subprocess
import sys
from pathlib import Path

class Command(BaseCommand):
    help = 'Install ZKBio Sync as Windows Service'

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
        parser.add_argument(
            '--startup',
            choices=['auto', 'manual', 'disabled'],
            default='auto',
            help='Service startup type (default: auto)'
        )

    def handle(self, *args, **options):
        try:
            # Check if pywin32 is installed
            import win32serviceutil
        except ImportError:
            raise CommandError(
                'pywin32 is required for Windows service. Install with: pip install pywin32'
            )

        service_script = Path(__file__).parent.parent.parent / 'windows_service.py'
        
        if not service_script.exists():
            raise CommandError(f'Service script not found: {service_script}')

        python_path = options['python_path']
        service_name = options['service_name']
        startup_type = options['startup']

        self.stdout.write('Installing ZKBio Sync Windows Service...')

        try:
            # Install the service
            cmd = [
                python_path,
                str(service_script),
                '--startup', startup_type,
                'install'
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            self.stdout.write(
                self.style.SUCCESS(f'✓ Service "{service_name}" installed successfully')
            )
            
            if result.stdout:
                self.stdout.write(f'Output: {result.stdout}')

            # Additional setup instructions
            self.stdout.write('\nNext steps:')
            self.stdout.write('1. Start the service:')
            self.stdout.write(f'   net start {service_name}')
            self.stdout.write('\n2. Or use Services.msc to manage the service')
            self.stdout.write('\n3. Check service status:')
            self.stdout.write(f'   sc query {service_name}')

        except subprocess.CalledProcessError as e:
            raise CommandError(f'Failed to install service: {e.stderr}')
        except Exception as e:
            raise CommandError(f'Installation error: {str(e)}')