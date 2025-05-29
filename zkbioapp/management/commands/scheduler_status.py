# zkbio_sync/management/commands/scheduler_status.py
from django.core.management.base import BaseCommand
from zkbioapp.scheduler import sync_scheduler
import schedule

class Command(BaseCommand):
    help = 'Show scheduler status and upcoming jobs'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=== SYNC SCHEDULER STATUS ===\n'))
        
        # Check if scheduler is running
        if sync_scheduler.running:
            self.stdout.write(self.style.SUCCESS('Status: RUNNING'))
        else:
            self.stdout.write(self.style.WARNING('Status: STOPPED'))
        
        # Show total jobs
        total_jobs = len(schedule.jobs)
        self.stdout.write(f'Total scheduled jobs: {total_jobs}')
        
        if total_jobs == 0:
            self.stdout.write(self.style.WARNING('No jobs scheduled. Run setup_schedules command first.'))
            return
        
        # Show all scheduled jobs
        self.stdout.write('\n=== ALL SCHEDULED JOBS ===')
        try:
            for i, job in enumerate(schedule.jobs, 1):
                # Get job function name
                job_func_name = getattr(job.job_func, '__name__', 'Unknown Job')
                
                # Get next run time
                next_run = getattr(job, 'next_run', 'Not scheduled')
                
                # Get schedule info
                interval = getattr(job, 'interval', 'N/A')
                unit = getattr(job, 'unit', 'N/A')
                
                self.stdout.write(f'{i}. {job_func_name}')
                self.stdout.write(f'   Next run: {next_run}')
                self.stdout.write(f'   Interval: {interval} {unit}')
                self.stdout.write('')
                
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'Error displaying job details: {e}'))
            # Simplified display
            for i, job in enumerate(schedule.jobs, 1):
                self.stdout.write(f'{i}. Scheduled job #{i}')
        
        # Show next 10 jobs chronologically
        self.stdout.write('\n=== NEXT 10 JOBS (CHRONOLOGICAL) ===')
        try:
            next_jobs = sync_scheduler.get_next_jobs(10)
            for i, job_info in enumerate(next_jobs, 1):
                self.stdout.write(f'{i}. {job_info["job"]} - {job_info["next_run"]}')
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'Could not get next jobs: {e}'))
            # Try alternative method
            try:
                sorted_jobs = sorted(schedule.jobs, key=lambda x: x.next_run)[:10]
                for i, job in enumerate(sorted_jobs, 1):
                    job_name = getattr(job.job_func, '__name__', f'Job {i}')
                    next_run = getattr(job, 'next_run', 'Unknown')
                    self.stdout.write(f'{i}. {job_name} - {next_run}')
            except Exception as e2:
                self.stdout.write(self.style.ERROR(f'Could not display upcoming jobs: {e2}'))
        
        # Show scheduler commands
        self.stdout.write('\n=== SCHEDULER COMMANDS ===')
        self.stdout.write('Start scheduler: python manage.py start_scheduler')
        self.stdout.write('Setup schedules: python manage.py setup_schedules')
        self.stdout.write('Run single job:  python manage.py run_job <job_type>')
        
        if sync_scheduler.running:
            self.stdout.write('\n✓ Scheduler is running and processing jobs automatically')
        else:
            self.stdout.write('\n⚠ Scheduler is not running. Start it with: python manage.py start_scheduler')