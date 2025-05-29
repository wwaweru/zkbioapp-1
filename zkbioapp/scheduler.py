# zkbioapp/scheduler.py
import schedule
import time
import threading
import logging
from django.utils import timezone
from .services.zkbio_service import ZKBioService
from .services.erp_service import ERPService

logger = logging.getLogger(__name__)

class SyncScheduler:
    """Scheduler for automated sync tasks using the schedule library"""
    
    def __init__(self):
        self.running = False
        self.thread = None
        
    def sync_employees_job(self):
        """Scheduled job to sync employees from ZKBio"""
        try:
            logger.info("Starting scheduled employee sync...")
            service = ZKBioService()
            count = service.sync_employees()
            logger.info(f"Scheduled task: Synced {count} employees")
        except Exception as e:
            logger.error(f"Scheduled employee sync failed: {str(e)}")

    def sync_attendance_job(self, days=1):
        """Scheduled job to sync attendance from ZKBio"""
        try:
            logger.info(f"Starting scheduled attendance sync for {days} day(s)...")
            service = ZKBioService()
            count = service.sync_attendance(days=days)
            logger.info(f"Scheduled task: Synced {count} attendance records")
        except Exception as e:
            logger.error(f"Scheduled attendance sync failed: {str(e)}")

    def sync_to_erp_job(self, max_records=100):
        """Scheduled job to sync attendance to ERP"""
        try:
            logger.info(f"Starting scheduled ERP sync for {max_records} records...")
            service = ERPService()
            result = service.sync_attendance(max_records=max_records)
            logger.info(f"Scheduled task: ERP sync completed - {result}")
        except Exception as e:
            logger.error(f"Scheduled ERP sync failed: {str(e)}")

    def full_sync_job(self, days=1, max_erp_records=100):
        """Scheduled job for full synchronization"""
        try:
            logger.info("Starting scheduled full sync...")
            zkbio_service = ZKBioService()
            erp_service = ERPService()
            
            # Sync employees
            emp_count = zkbio_service.sync_employees()
            logger.info(f"Full sync: Synced {emp_count} employees")
            
            # Sync attendance
            att_count = zkbio_service.sync_attendance(days=days)
            logger.info(f"Full sync: Synced {att_count} attendance records")
            
            # Sync to ERP
            erp_result = erp_service.sync_attendance(max_records=max_erp_records)
            logger.info(f"Full sync: ERP result - {erp_result}")
            
            logger.info("Scheduled full sync completed successfully")
            
        except Exception as e:
            logger.error(f"Scheduled full sync failed: {str(e)}")

    def retry_failed_job(self, max_records=50):
        """Scheduled job to retry failed ERP syncs"""
        try:
            logger.info("Starting scheduled retry of failed records...")
            service = ERPService()
            result = service.sync_attendance(
                max_records=max_records, 
                retry_failed=True
            )
            logger.info(f"Scheduled retry: {result}")
        except Exception as e:
            logger.error(f"Scheduled retry failed: {str(e)}")

    def setup_schedules(self):
        """Set up all scheduled jobs"""
        # Clear any existing schedules
        schedule.clear()
        
        # Daily employee sync at 6:00 AM (start of day)
        schedule.every().day.at("06:00").do(self.sync_employees_job)
        
        # Attendance sync during business hours (8 AM to 6 PM) - hourly to collect data
        for hour in range(8, 19):  # 8 AM to 6 PM
            schedule.every().day.at(f"{hour:02d}:00").do(
                self.sync_attendance_job, days=1
            )
        
        # END-OF-DAY ERP SYNC - Push complete attendance data to ERP
        # After business hours when attendance is complete
        schedule.every().day.at("19:30").do(  # 7:30 PM - after work hours
            self.end_of_day_erp_sync, for_date='today'
        )
        
        # PREVIOUS DAY ERP SYNC - Catch any missed records from yesterday
        schedule.every().day.at("07:30").do(  # 7:30 AM - start of next day
            self.end_of_day_erp_sync, for_date='yesterday'
        )
        
        # Full sync once daily at 7:00 AM (employees + fresh attendance data)
        schedule.every().day.at("07:00").do(
            self.full_sync_job, days=1, max_erp_records=0  # Skip ERP sync in full_sync
        )
        
        # Retry failed records twice daily
        schedule.every().day.at("12:00").do(self.retry_failed_job, max_records=50)  # Midday
        schedule.every().day.at("20:00").do(self.retry_failed_job, max_records=100) # Evening
        
        # Weekend maintenance sync (Saturdays at 10:00 AM)
        schedule.every().saturday.at("10:00").do(
            self.weekend_maintenance_sync
        )
        
        logger.info("Scheduled jobs configured:")
        for job in schedule.jobs:
            logger.info(f"  - {job}")

    def end_of_day_erp_sync(self, for_date='today'):
        """End-of-day ERP sync - push complete attendance data for a specific date"""
        try:
            from datetime import datetime, timedelta
            from django.utils import timezone
            
            # Determine the target date
            if for_date == 'today':
                target_date = timezone.now().date()
                logger.info("Starting END-OF-DAY ERP sync for today's attendance...")
            elif for_date == 'yesterday':
                target_date = timezone.now().date() - timedelta(days=1)
                logger.info("Starting PREVIOUS DAY ERP sync for yesterday's attendance...")
            else:
                target_date = datetime.strptime(for_date, '%Y-%m-%d').date()
                logger.info(f"Starting ERP sync for date: {target_date}")
            
            service = ERPService()
            
            # Sync all pending/failed records for the specific date
            result = service.sync_attendance(
                max_records=500,  # Higher limit for end-of-day sync
                attendance_date=target_date,
                status_filter=['pending', 'failed']
            )
            
            logger.info(f"End-of-day ERP sync completed for {target_date}: {result}")
            
            # Log summary for monitoring
            if result['synced'] > 0 or result['failed'] > 0:
                logger.info(f"ERP Sync Summary for {target_date}:")
                logger.info(f"  - Successfully synced: {result['synced']} records")
                logger.info(f"  - Failed to sync: {result['failed']} records")
                if result['failed'] > 0:
                    logger.warning(f"  - {result['failed']} records need attention!")
            else:
                logger.info(f"No attendance records to sync for {target_date}")
                
        except Exception as e:
            logger.error(f"End-of-day ERP sync failed for {for_date}: {str(e)}")

    def weekend_maintenance_sync(self):
        """Weekend maintenance - comprehensive sync and cleanup"""
        try:
            logger.info("Starting weekend maintenance sync...")
            zkbio_service = ZKBioService()
            erp_service = ERPService()
            
            # Sync employees (weekly refresh)
            emp_count = zkbio_service.sync_employees()
            logger.info(f"Weekend maintenance: Synced {emp_count} employees")
            
            # Sync last 7 days of attendance (catch any missed data)
            att_count = zkbio_service.sync_attendance(days=7)
            logger.info(f"Weekend maintenance: Synced {att_count} attendance records")
            
            # Push any remaining pending records to ERP
            erp_result = erp_service.sync_attendance(
                max_records=1000,  # Higher limit for weekend cleanup
                status_filter=['pending', 'failed']
            )
            logger.info(f"Weekend maintenance: ERP result - {erp_result}")
            
            logger.info("Weekend maintenance sync completed successfully")
            
        except Exception as e:
            logger.error(f"Weekend maintenance sync failed: {str(e)}")

    def full_sync_job(self, days=1, max_erp_records=100):
        """Scheduled job for full synchronization"""
        try:
            logger.info("Starting scheduled full sync...")
            zkbio_service = ZKBioService()
            
            # Sync employees
            emp_count = zkbio_service.sync_employees()
            logger.info(f"Full sync: Synced {emp_count} employees")
            
            # Sync attendance
            att_count = zkbio_service.sync_attendance(days=days)
            logger.info(f"Full sync: Synced {att_count} attendance records")
            
            # Only sync to ERP if max_erp_records > 0
            if max_erp_records > 0:
                erp_service = ERPService()
                erp_result = erp_service.sync_attendance(max_records=max_erp_records)
                logger.info(f"Full sync: ERP result - {erp_result}")
            else:
                logger.info("Full sync: Skipping ERP sync (handled by end-of-day job)")
            
            logger.info("Scheduled full sync completed successfully")
            
        except Exception as e:
            logger.error(f"Scheduled full sync failed: {str(e)}")

    def run_scheduler(self):
        """Run the scheduler in a loop"""
        logger.info("Starting sync scheduler...")
        self.running = True
        
        while self.running:
            try:
                schedule.run_pending()
                time.sleep(30)  # Check every 30 seconds
            except Exception as e:
                logger.error(f"Scheduler error: {str(e)}")
                time.sleep(60)  # Wait a minute before retrying

    def start(self):
        """Start the scheduler in a background thread"""
        if self.thread is None or not self.thread.is_alive():
            self.setup_schedules()
            self.thread = threading.Thread(target=self.run_scheduler, daemon=True)
            self.thread.start()
            logger.info("Sync scheduler started in background thread")
        else:
            logger.warning("Scheduler is already running")

    def stop(self):
        """Stop the scheduler"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
            logger.info("Sync scheduler stopped")

    def get_next_jobs(self, count=10):
        """Get information about next scheduled jobs"""
        jobs_info = []
        try:
            # Sort jobs by next run time
            sorted_jobs = sorted(schedule.jobs, key=lambda x: x.next_run)[:count]
            
            for job in sorted_jobs:
                # Get job function name safely
                job_func_name = getattr(job.job_func, '__name__', 'Unknown Job')
                
                jobs_info.append({
                    'job': job_func_name,
                    'next_run': job.next_run,  
                    'interval': getattr(job, 'interval', None),
                    'unit': getattr(job, 'unit', None)
                })
        except Exception as e:
            logger.error(f"Error getting next jobs: {e}")
            # Return basic info if detailed info fails
            for i, job in enumerate(schedule.jobs[:count]):
                jobs_info.append({
                    'job': f'Scheduled Job {i+1}',
                    'next_run': getattr(job, 'next_run', 'Unknown'),
                    'interval': 'N/A',
                    'unit': 'N/A'
                })
                
        return jobs_info

# Global scheduler instance
sync_scheduler = SyncScheduler()