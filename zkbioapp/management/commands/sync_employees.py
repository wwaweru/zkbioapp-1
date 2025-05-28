# zkbioapp/management/commands/sync_employees.py
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from zkbioapp.services.zkbio_service import ZKBioService

class Command(BaseCommand):
    help = 'Sync employees from ZKBio to local database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Enable verbose output',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting employee synchronization...'))
        
        try:
            service = ZKBioService()
            start_time = timezone.now()
            
            count = service.sync_employees()
            
            end_time = timezone.now()
            duration = (end_time - start_time).total_seconds()
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully synced {count} employees in {duration:.2f} seconds'
                )
            )
            
            if options['verbose']:
                self.stdout.write(f'Started: {start_time}')
                self.stdout.write(f'Finished: {end_time}')
                
        except Exception as e:
            raise CommandError(f'Employee sync failed: {str(e)}')
