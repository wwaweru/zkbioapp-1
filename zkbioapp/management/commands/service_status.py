from django.core.management.base import BaseCommand
import subprocess

class Command(BaseCommand):
    help = 'Check Windows service status'

    def add_arguments(self, parser):
        parser.add_argument(
            '--service-name',
            type=str,
            default='ZKBioSyncService',
            help='Windows service name (default: ZKBioSyncService)'
        )

    def handle(self, *args, **options):
        service_name = options['service_name']
        
        self.stdout.write(f'Checking status of service: {service_name}')
        
        try:
            # Query service status
            cmd = ['sc', 'query', service_name]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            # Parse the output to get status
            lines = result.stdout.strip().split('\n')
            for line in lines:
                if 'STATE' in line:
                    if 'RUNNING' in line:
                        self.stdout.write(
                            self.style.SUCCESS(f'✓ Service is RUNNING')
                        )
                    elif 'STOPPED' in line:
                        self.stdout.write(
                            self.style.WARNING(f'⚠ Service is STOPPED')
                        )
                    else:
                        self.stdout.write(f'Status: {line.strip()}')
                elif 'SERVICE_NAME' in line or 'DISPLAY_NAME' in line or 'TYPE' in line:
                    self.stdout.write(line.strip())
            
            # Show additional service info
            self.stdout.write('\nService management commands:')
            self.stdout.write(f'Start:   net start {service_name}')
            self.stdout.write(f'Stop:    net stop {service_name}')
            self.stdout.write(f'Restart: net stop {service_name} && net start {service_name}')
            
        except subprocess.CalledProcessError as e:
            if 'does not exist' in e.stderr:
                self.stdout.write(
                    self.style.ERROR(f'✗ Service "{service_name}" is not installed')
                )
                self.stdout.write('\nTo install the service, run:')
                self.stdout.write('python manage.py install_windows_service')
            else:
                self.stdout.write(
                    self.style.ERROR(f'Error checking service: {e.stderr}')
                )
