# zkbioapp/management/commands/start_scheduler.py
from django.core.management.base import BaseCommand
from zkbioapp.scheduler import sync_scheduler
import signal
import sys

class Command(BaseCommand):
    help = 'Start the sync scheduler daemon'

    def add_arguments(self, parser):
        parser.add_argument(
            '--no-setup',
            action='store_true',
            help='Skip initial schedule setup',
        )

    def handle(self, *args, **options):
        def signal_handler(sig, frame):
            self.stdout.write(self.style.WARNING('\nShutting down scheduler...'))
            sync_scheduler.stop()
            sys.exit(0)

        # Register signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        self.stdout.write(self.style.SUCCESS('Starting sync scheduler daemon...'))
        
        if not options['no_setup']:
            self.stdout.write('Setting up schedules...')
            sync_scheduler.setup_schedules()
            
        # Show next scheduled jobs
        try:
            next_jobs = sync_scheduler.get_next_jobs(5)
            self.stdout.write('\nNext scheduled jobs:')
            for job_info in next_jobs:
                self.stdout.write(f"  - {job_info['job']} at {job_info['next_run']}")
        except Exception as e:
            self.stdout.write(f'Could not display next jobs: {e}')
        
        self.stdout.write(f'\nScheduler is running. Press Ctrl+C to stop.')
        
        try:
            # This will run the scheduler loop
            sync_scheduler.run_scheduler()
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING('\nScheduler stopped by user'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Scheduler error: {str(e)}'))