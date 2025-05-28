# zkbioapp/management/commands/sync_to_erp.py
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from datetime import datetime
from zkbioapp.services.erp_service import ERPService

class Command(BaseCommand):
    help = 'Sync attendance records to ERP system'

    def add_arguments(self, parser):
        parser.add_argument(
            '--max-records',
            type=int,
            default=100,
            help='Maximum number of records to sync (default: 100)',
        )
        parser.add_argument(
            '--date',
            type=str,
            help='Sync records for specific date (YYYY-MM-DD format)',
        )
        parser.add_argument(
            '--employee',
            type=str,
            help='Sync records for specific employee code',
        )
        parser.add_argument(
            '--retry-failed',
            action='store_true',
            help='Retry previously failed sync attempts',
        )
        parser.add_argument(
            '--status',
            choices=['pending', 'failed', 'synced', 'duplicate'],
            action='append',
            help='Filter by status (can be used multiple times)',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Enable verbose output',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting ERP synchronization...'))
        
        try:
            service = ERPService()
            start_time = timezone.now()
            
            # Parse date argument
            attendance_date = None
            if options['date']:
                try:
                    attendance_date = datetime.strptime(options['date'], '%Y-%m-%d').date()
                except ValueError:
                    raise CommandError('Invalid date format. Use YYYY-MM-DD')
            
            # Sync to ERP
            result = service.sync_attendance(
                max_records=options['max_records'],
                attendance_date=attendance_date,
                employee_code=options['employee'],
                retry_failed=options['retry_failed'],
                status_filter=options['status']
            )
            
            end_time = timezone.now()
            duration = (end_time - start_time).total_seconds()
            
            # Display results
            self.stdout.write(
                self.style.SUCCESS(
                    f'ERP sync completed in {duration:.2f} seconds:'
                )
            )
            self.stdout.write(f'  Synced: {result["synced"]}')
            self.stdout.write(f'  Duplicates: {result["duplicates"]}')
            self.stdout.write(f'  Failed: {result["failed"]}')
            
            if options['verbose']:
                self.stdout.write(f'Started: {start_time}')
                self.stdout.write(f'Finished: {end_time}')
                
                # Show filter information
                filters = []
                if attendance_date:
                    filters.append(f'Date: {attendance_date}')
                if options['employee']:
                    filters.append(f'Employee: {options["employee"]}')
                if options['retry_failed']:
                    filters.append('Mode: Retry failed')
                if options['status']:
                    filters.append(f'Status: {", ".join(options["status"])}')
                
                if filters:
                    self.stdout.write('Filters applied:')
                    for filter_info in filters:
                        self.stdout.write(f'  {filter_info}')
                
        except Exception as e:
            raise CommandError(f'ERP sync failed: {str(e)}')