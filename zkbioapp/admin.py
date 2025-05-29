# zkbioapp/admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Q
from .models import Employee, AttendanceRecord, SyncLog, SyncStats

@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ['emp_code', 'full_name', 'department', 'area_name', 'is_active', 'created_at']
    list_filter = ['is_active', 'department', 'area_name']
    search_fields = ['emp_code', 'first_name', 'last_name', 'full_name']
    readonly_fields = ['created_at', 'updated_at']
    list_per_page = 50
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('emp_code', 'first_name', 'last_name', 'full_name')
        }),
        ('Work Details', {
            'fields': ('department', 'area_name', 'is_active')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

@admin.register(AttendanceRecord)
class AttendanceRecordAdmin(admin.ModelAdmin):
    list_display = [
        'employee_info', 'attendance_date', 'in_time', 'out_time', 
        'status_badge', 'sync_attempts', 'last_sync_attempt'
    ]
    list_filter = [
        'status', 'attendance_date', 'department', 'area_alias', 
        'employee__department', 'sync_attempts'
    ]
    search_fields = [
        'employee__emp_code', 'employee__full_name', 
        'zkbio_transaction_id', 'erp_attendance_id'
    ]
    readonly_fields = ['created_at', 'updated_at', 'total_hours_display']
    list_per_page = 50
    date_hierarchy = 'attendance_date'
    
    fieldsets = (
        ('Employee & Date', {
            'fields': ('employee', 'attendance_date')
        }),
        ('Time Information', {
            'fields': ('punch_time', 'in_time', 'out_time', 'total_hours_display')
        }),
        ('Sync Information', {
            'fields': ('status', 'sync_attempts', 'last_sync_attempt', 'error_message')
        }),
        ('External References', {
            'fields': ('zkbio_transaction_id', 'erp_attendance_id')
        }),
        ('Additional Details', {
            'fields': ('department', 'area_alias', 'details'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def employee_info(self, obj):
        return f"{obj.employee.full_name} ({obj.employee.emp_code})"
    employee_info.short_description = 'Employee'
    
    def status_badge(self, obj):
        colors = {
            'pending': 'orange',
            'synced': 'green',
            'failed': 'red',
            'duplicate': 'blue'
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def total_hours_display(self, obj):
        hours = obj.total_hours
        if hours > 0:
            return f"{hours} hours"
        return "N/A"
    total_hours_display.short_description = 'Total Hours'
    
    actions = ['mark_pending', 'retry_sync']
    
    def mark_pending(self, request, queryset):
        count = queryset.update(status='pending', sync_attempts=0, error_message=None)
        self.message_user(request, f'{count} records marked as pending for retry.')
    mark_pending.short_description = 'Mark selected records as pending'
    
    def retry_sync(self, request, queryset):
        failed_records = queryset.filter(status='failed')
        count = failed_records.update(status='pending', error_message=None)
        self.message_user(request, f'{count} failed records marked for retry.')
    retry_sync.short_description = 'Retry failed sync records'

@admin.register(SyncLog)
class SyncLogAdmin(admin.ModelAdmin):
    list_display = [
        'created_at', 'log_type', 'status_badge', 'message_preview', 
        'related_employee', 'execution_time_display'
    ]
    list_filter = ['log_type', 'status', 'created_at']
    search_fields = ['message', 'related_employee__emp_code', 'related_employee__full_name']
    readonly_fields = ['created_at']
    list_per_page = 100
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Log Information', {
            'fields': ('log_type', 'status', 'message')
        }),
        ('Related Data', {
            'fields': ('related_employee', 'execution_time')
        }),
        ('Details', {
            'fields': ('details',),
            'classes': ('collapse',)
        }),
        ('Timestamp', {
            'fields': ('created_at',)
        }),
    )
    
    def message_preview(self, obj):
        return obj.message[:100] + '...' if len(obj.message) > 100 else obj.message
    message_preview.short_description = 'Message'
    
    def status_badge(self, obj):
        colors = {
            'success': 'green',
            'error': 'red',
            'warning': 'orange',
            'info': 'blue'
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def execution_time_display(self, obj):
        if obj.execution_time:
            return f"{obj.execution_time:.2f}s"
        return "N/A"
    execution_time_display.short_description = 'Execution Time'

@admin.register(SyncStats)
class SyncStatsAdmin(admin.ModelAdmin):
    list_display = [
        'updated_at', 'total_employees', 'total_records', 
        'pending_records', 'synced_records', 'failed_records', 'success_rate_display'
    ]
    readonly_fields = [
        'total_employees', 'active_employees', 'total_records', 'pending_records',
        'synced_records', 'failed_records', 'sync_success_rate',
        'last_zkbio_sync', 'last_erp_sync', 'last_employee_sync', 'updated_at'
    ]
    
    fieldsets = (
        ('Employee Statistics', {
            'fields': ('total_employees', 'active_employees')
        }),
        ('Attendance Record Statistics', {
            'fields': (
                'total_records', 'pending_records', 'synced_records', 
                'failed_records', 'sync_success_rate'
            )
        }),
        ('Last Sync Times', {
            'fields': ('last_employee_sync', 'last_zkbio_sync', 'last_erp_sync')
        }),
        ('Timestamps', {
            'fields': ('updated_at',)
        }),
    )
    
    def success_rate_display(self, obj):
        return f"{obj.sync_success_rate}%"
    success_rate_display.short_description = 'Success Rate'
    
    def has_add_permission(self, request):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False