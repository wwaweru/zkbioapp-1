from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError

class Employee(models.Model):
    emp_code = models.CharField(max_length=50, unique=True, db_index=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100, blank=True, null=True)
    full_name = models.CharField(max_length=200, blank=True)
    department = models.CharField(max_length=100, blank=True)
    area_name = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'zkbio_employees'
        ordering = ['emp_code']

    def __str__(self):
        return f"{self.full_name or f'{self.first_name} {self.last_name}'} ({self.emp_code})"

    def clean(self):
        if not self.emp_code:
            raise ValidationError('Employee code is required')

class AttendanceRecord(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('synced', 'Synced'),
        ('failed', 'Failed'),
    ]
    
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='attendance_records')
    attendance_date = models.DateField(db_index=True)
    punch_time = models.DateTimeField()
    in_time = models.TimeField(null=True, blank=True)
    out_time = models.TimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True)
    zkbio_transaction_id = models.CharField(max_length=100, unique=True, db_index=True)
    erp_attendance_id = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    sync_attempts = models.PositiveIntegerField(default=0)
    last_sync_attempt = models.DateTimeField(null=True, blank=True)
    department = models.CharField(max_length=100, blank=True, null=True)
    area_alias = models.CharField(max_length=100, blank=True, null=True)
    details = models.JSONField(null=True, blank=True)
    error_message = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'zkbio_attendance_records'
        unique_together = ('employee', 'attendance_date')
        ordering = ['-attendance_date', 'employee__emp_code']
        indexes = [
            models.Index(fields=['status', 'sync_attempts']),
            models.Index(fields=['attendance_date', 'status']),
        ]
    
    def __str__(self):
        return f"{self.employee} - {self.attendance_date} ({self.status})"

    @property
    def total_hours(self):
        """Calculate total hours worked"""
        if self.in_time and self.out_time:
            from datetime import datetime, timedelta
            in_dt = datetime.combine(self.attendance_date, self.in_time)
            out_dt = datetime.combine(self.attendance_date, self.out_time)
            
            # Handle overnight shifts
            if out_dt < in_dt:
                out_dt += timedelta(days=1)
            
            delta = out_dt - in_dt
            return round(delta.total_seconds() / 3600, 2)
        return 0

class SyncLog(models.Model):
    LOG_TYPE_CHOICES = [
        ('zkbio_fetch', 'ZKBio Fetch'),
        ('zkbio_employees', 'ZKBio Employees'),
        ('erp_sync', 'ERP Sync'),
        ('system', 'System'),
    ]
    
    STATUS_CHOICES = [
        ('success', 'Success'),
        ('error', 'Error'),
        ('warning', 'Warning'),
        ('info', 'Info'),
    ]
    
    log_type = models.CharField(max_length=20, choices=LOG_TYPE_CHOICES, db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, db_index=True)
    message = models.TextField()
    details = models.JSONField(default=dict, blank=True)
    related_employee = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, blank=True)
    execution_time = models.FloatField(null=True, blank=True)  # in seconds
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'zkbio_sync_logs'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_log_type_display()} - {self.get_status_display()} ({self.created_at})"

class SyncStats(models.Model):
    total_employees = models.PositiveIntegerField(default=0)
    active_employees = models.PositiveIntegerField(default=0)
    total_records = models.PositiveIntegerField(default=0)
    pending_records = models.PositiveIntegerField(default=0)
    synced_records = models.PositiveIntegerField(default=0)
    failed_records = models.PositiveIntegerField(default=0)
    last_zkbio_sync = models.DateTimeField(null=True, blank=True)
    last_erp_sync = models.DateTimeField(null=True, blank=True)
    last_employee_sync = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'zkbio_sync_stats'

    @classmethod
    def update_stats(cls):
        """Update synchronization statistics"""
        stats, created = cls.objects.get_or_create(pk=1)
        stats.total_employees = Employee.objects.count()
        stats.active_employees = Employee.objects.filter(is_active=True).count()
        stats.total_records = AttendanceRecord.objects.count()
        stats.pending_records = AttendanceRecord.objects.filter(status='pending').count()
        stats.synced_records = AttendanceRecord.objects.filter(status='synced').count()
        stats.failed_records = AttendanceRecord.objects.filter(status='failed').count()
        
        # Get last sync times from logs
        last_zkbio = SyncLog.objects.filter(
            log_type='zkbio_fetch', 
            status='success'
        ).first()
        if last_zkbio:
            stats.last_zkbio_sync = last_zkbio.created_at
            
        last_erp = SyncLog.objects.filter(
            log_type='erp_sync', 
            status__in=['success', 'info']  # Include 'info' for existing records
        ).first()
        if last_erp:
            stats.last_erp_sync = last_erp.created_at
            
        last_emp = SyncLog.objects.filter(
            log_type='zkbio_employees', 
            status='success'
        ).first()
        if last_emp:
            stats.last_employee_sync = last_emp.created_at
        
        stats.save()
        return stats

    def __str__(self):
        return f"Sync Statistics - {self.updated_at}"

    @property
    def sync_success_rate(self):
        """Calculate sync success rate"""
        total = self.synced_records + self.failed_records
        if total > 0:
            return round((self.synced_records / total) * 100, 2)
        return 0