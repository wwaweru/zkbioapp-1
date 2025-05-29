# zkbio_sync/management/commands/setup_schedules.py
from django.core.management.base import BaseCommand
from zkbioapp.scheduler import sync_scheduler
import schedule

class Command(BaseCommand):
    help = 'Setup/reset scheduler jobs without starting the daemon'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear all existing schedules first',
        )

    def handle(self, *args, **options):
        if options['clear']:
            schedule.clear()
            self.stdout.write(self.style.WARNING('Cleared all existing schedules'))
        
        self.stdout.write('Setting up sync schedules...')
        sync_scheduler.setup_schedules()
        
        total_jobs = len(schedule.jobs)
        self.stdout.write(
            self.style.SUCCESS(f'Successfully configured {total_jobs} scheduled jobs')
        )
        
        # Show the schedules with correct attribute access
        self.stdout.write('\nConfigured schedules:')
        try:
            for i, job in enumerate(schedule.jobs, 1):
                # Fix: Use job.job_func instead of job.job
                job_func_name = getattr(job.job_func, '__name__', str(job.job_func))
                next_run = getattr(job, 'next_run', 'Not scheduled')
                self.stdout.write(f'{i}. {job_func_name} - Next run: {next_run}')
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'Could not display job details: {e}'))
            # Alternative display method
            self.stdout.write('\nScheduled jobs summary:')
            for i, job in enumerate(schedule.jobs, 1):
                self.stdout.write(f'{i}. Job scheduled successfully')
        
        self.stdout.write(f'\n✓ All {total_jobs} jobs are ready to run!')
        self.stdout.write('\nTo start the scheduler daemon:')
        self.stdout.write('  python manage.py start_scheduler')
        self.stdout.write('\nTo check scheduler status:')
        self.stdout.write('  python manage.py scheduler_status')