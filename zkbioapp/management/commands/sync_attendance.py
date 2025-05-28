# zkbioapp/management/commands/sync_attendance.py
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from datetime import datetime, date
from zkbioapp.services.zkbio_service import ZKBioService

class Command(BaseCommand):
    help = 'Sync attendance records from ZKBio to local database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=1,
            help='Number of days to sync (default: 1)',
        )
        parser.add_argument(
            '--start-date',
            type=str,
            help='Start date (YYYY-MM-DD format)',
        )
        parser.add_argument(
            '--end-date',
            type=str,
            help='End date (YYYY-MM-DD format)',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Enable verbose output',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting attendance synchronization...'))
        
        try:
            service = ZKBioService()
            start_time = timezone.now()
            
            # Parse date arguments
            start_date = None
            end_date = None
            
            if options['start_date']:
                try:
                    start_date = datetime.strptime(options['start_date'], '%Y-%m-%d').date()
                except ValueError:
                    raise CommandError('Invalid start date format. Use YYYY-MM-DD')
            
            if options['end_date']:
                try:
                    end_date = datetime.strptime(options['end_date'], '%Y-%m-%d').date()
                except ValueError:
                    raise CommandError('Invalid end date format. Use YYYY-MM-DD')
            
            if start_date and end_date and start_date > end_date:
                raise CommandError('Start date cannot be after end date')
            
            # Sync attendance
            if start_date and end_date:
                count = service.sync_attendance(start_date=start_date, end_date=end_date)
                date_info = f" from {start_date} to {end_date}"
            else:
                count = service.sync_attendance(days=options['days'])
                date_info = f" for last {options['days']} day(s)"
            
            end_time = timezone.now()
            duration = (end_time - start_time).total_seconds()
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully synced {count} attendance records{date_info} in {duration:.2f} seconds'
                )
            )
            
            if options['verbose']:
                self.stdout.write(f'Started: {start_time}')
                self.stdout.write(f'Finished: {end_time}')
                
        except Exception as e:
            raise CommandError(f'Attendance sync failed: {str(e)}')