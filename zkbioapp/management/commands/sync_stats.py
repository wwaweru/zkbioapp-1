# zkbioapp/management/commands/sync_stats.py
from django.core.management.base import BaseCommand
from zkbioapp.models import SyncStats
from zkbioapp.services.erp_service import ERPService

class Command(BaseCommand):
    help = 'Display synchronization statistics'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=7,
            help='Number of days for statistics (default: 7)',
        )
        parser.add_argument(
            '--update',
            action='store_true',
            help='Update statistics before displaying',
        )

    def handle(self, *args, **options):
        if options['update']:
            self.stdout.write('Updating statistics...')
            SyncStats.update_stats()
        
        # Get overall stats
        stats = SyncStats.objects.first()
        if not stats:
            self.stdout.write(self.style.WARNING('No statistics available'))
            return
        
        # Get recent stats
        erp_service = ERPService()
        recent_stats = erp_service.get_sync_stats(days=options['days'])
        
        self.stdout.write(self.style.SUCCESS('\n=== SYNCHRONIZATION STATISTICS ==='))
        
        # Overall statistics
        self.stdout.write('\nOverall Statistics:')
        self.stdout.write(f'  Total Employees: {stats.total_employees}')
        self.stdout.write(f'  Active Employees: {stats.active_employees}')
        self.stdout.write(f'  Total Attendance Records: {stats.total_records}')
        self.stdout.write(f'  Pending Records: {stats.pending_records}')
        self.stdout.write(f'  Synced Records: {stats.synced_records}')
        self.stdout.write(f'  Failed Records: {stats.failed_records}')        
        self.stdout.write(f'  Overall Success Rate: {stats.sync_success_rate}%')
        
        # Recent statistics
        self.stdout.write(f'\nLast {options["days"]} Days Statistics:')
        self.stdout.write(f'  Total Records: {recent_stats["total_records"]}')
        self.stdout.write(f'  Pending: {recent_stats["pending"]}')
        self.stdout.write(f'  Synced: {recent_stats["synced"]}')
        self.stdout.write(f'  Failed: {recent_stats["failed"]}')
        self.stdout.write(f'  Success Rate: {recent_stats["success_rate"]}%')
        
        # Last sync times
        self.stdout.write('\nLast Sync Times:')
        if stats.last_employee_sync:
            self.stdout.write(f'  Employees: {stats.last_employee_sync}')
        else:
            self.stdout.write('  Employees: Never')
            
        if stats.last_zkbio_sync:
            self.stdout.write(f'  ZKBio Attendance: {stats.last_zkbio_sync}')
        else:
            self.stdout.write('  ZKBio Attendance: Never')
            
        if stats.last_erp_sync:
            self.stdout.write(f'  ERP Sync: {stats.last_erp_sync}')
        else:
            self.stdout.write('  ERP Sync: Never')
        
        self.stdout.write(f'\nStatistics last updated: {stats.updated_at}')