# zkbio_sync/management/commands/full_sync.py
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from datetime import datetime
from zkbioapp.services.zkbio_service import ZKBioService
from zkbioapp.services.erp_service import ERPService

class Command(BaseCommand):
    help = 'Perform full synchronization: employees, attendance, and ERP sync'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=1,
            help='Number of days to sync attendance (default: 1)',
        )
        parser.add_argument(
            '--start-date',
            type=str,
            help='Start date for attendance sync (YYYY-MM-DD format)',
        )
        parser.add_argument(
            '--end-date',
            type=str,
            help='End date for attendance sync (YYYY-MM-DD format)',
        )
        parser.add_argument(
            '--max-erp-records',
            type=int,
            default=100,
            help='Maximum number of records to sync to ERP (default: 100)',
        )
        parser.add_argument(
            '--skip-employees',
            action='store_true',
            help='Skip employee synchronization',
        )
        parser.add_argument(
            '--skip-attendance',
            action='store_true',
            help='Skip attendance synchronization',
        )
        parser.add_argument(
            '--skip-erp',
            action='store_true',
            help='Skip ERP synchronization',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Enable verbose output',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting full synchronization...'))
        overall_start = timezone.now()
        
        try:
            zkbio_service = ZKBioService()
            erp_service = ERPService()
            
            results = {
                'employees': 0,
                'attendance': 0,
                'erp_synced': 0,
                'erp_duplicates': 0,
                'erp_failed': 0
            }
            
            # Step 1: Sync employees
            if not options['skip_employees']:
                self.stdout.write('Step 1: Syncing employees...')
                step_start = timezone.now()
                
                results['employees'] = zkbio_service.sync_employees()
                
                step_duration = (timezone.now() - step_start).total_seconds()
                self.stdout.write(
                    self.style.SUCCESS(
                        f'  ✓ Synced {results["employees"]} employees in {step_duration:.2f}s'
                    )
                )
            else:
                self.stdout.write('Step 1: Skipping employee sync')
            
            # Step 2: Sync attendance
            if not options['skip_attendance']:
                self.stdout.write('Step 2: Syncing attendance...')
                step_start = timezone.now()
                
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
                
                if start_date and end_date:
                    results['attendance'] = zkbio_service.sync_attendance(
                        start_date=start_date, end_date=end_date
                    )
                else:
                    results['attendance'] = zkbio_service.sync_attendance(days=options['days'])
                
                step_duration = (timezone.now() - step_start).total_seconds()
                self.stdout.write(
                    self.style.SUCCESS(
                        f'  ✓ Synced {results["attendance"]} attendance records in {step_duration:.2f}s'
                    )
                )
            else:
                self.stdout.write('Step 2: Skipping attendance sync')
            
            # Step 3: Sync to ERP
            if not options['skip_erp']:
                self.stdout.write('Step 3: Syncing to ERP...')
                step_start = timezone.now()
                
                erp_result = erp_service.sync_attendance(max_records=options['max_erp_records'])
                results['erp_synced'] = erp_result['synced']
                results['erp_duplicates'] = erp_result['duplicates']
                results['erp_failed'] = erp_result['failed']
                
                step_duration = (timezone.now() - step_start).total_seconds()
                self.stdout.write(
                    self.style.SUCCESS(
                        f'  ✓ ERP sync completed in {step_duration:.2f}s'
                    )
                )
                self.stdout.write(f'    - Synced: {results["erp_synced"]}')
                self.stdout.write(f'    - Duplicates: {results["erp_duplicates"]}')
                self.stdout.write(f'    - Failed: {results["erp_failed"]}')
            else:
                self.stdout.write('Step 3: Skipping ERP sync')
            
            # Summary
            overall_duration = (timezone.now() - overall_start).total_seconds()
            self.stdout.write(
                self.style.SUCCESS(
                    f'\nFull synchronization completed in {overall_duration:.2f} seconds!'
                )
            )
            
            if options['verbose']:
                self.stdout.write('\nDetailed Results:')
                self.stdout.write(f'  Employees synced: {results["employees"]}')
                self.stdout.write(f'  Attendance records synced: {results["attendance"]}')
                self.stdout.write(f'  Records sent to ERP: {results["erp_synced"]}')
                self.stdout.write(f'  Duplicate records: {results["erp_duplicates"]}')
                self.stdout.write(f'  Failed ERP syncs: {results["erp_failed"]}')
                
        except Exception as e:
            raise CommandError(f'Full sync failed: {str(e)}')