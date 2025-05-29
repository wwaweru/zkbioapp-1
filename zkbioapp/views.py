# zkbioapp/views.py
import logging
from django.shortcuts import render, redirect
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.core.paginator import Paginator
from django.db.models import Q, Count
from datetime import datetime, timedelta
from .models import Employee, AttendanceRecord, SyncLog, SyncStats
from .services.zkbio_service import ZKBioService
from .services.erp_service import ERPService

logger = logging.getLogger(__name__)

def dashboard(request):
    """Main dashboard view"""
    # Update stats
    stats = SyncStats.update_stats()
    
    # Get recent logs
    recent_logs = SyncLog.objects.select_related('related_employee').order_by('-created_at')[:10]
    
    # Get recent attendance records
    recent_attendance = AttendanceRecord.objects.select_related('employee').order_by('-created_at')[:10]
    
    # Get sync statistics for chart data
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=7)
    
    daily_stats = []
    try:
        for i in range(7):
            date = start_date + timedelta(days=i)
            day_records = AttendanceRecord.objects.filter(attendance_date=date)
            daily_stats.append({
                'date': date.strftime('%Y-%m-%d'),
                'total': day_records.count(),
                'synced': day_records.filter(status='synced').count(),
                'failed': day_records.filter(status='failed').count(),
                'pending': day_records.filter(status='pending').count(),
            })
    except Exception as e:
        logger.error(f"Error generating daily stats: {str(e)}")
        daily_stats = []
    
    # Convert daily_stats to JSON for safe template rendering
    import json
    daily_stats_json = json.dumps(daily_stats)
    
    context = {
        'stats': stats,
        'recent_logs': recent_logs,
        'recent_attendance': recent_attendance,
        'daily_stats': daily_stats,
        'daily_stats_json': daily_stats_json,
    }
    
    return render(request, 'zkbioapp/dashboard.html', context)

def sync_employees(request):
    """Sync employees from ZKBio"""
    if request.method == 'POST':
        try:
            service = ZKBioService()
            count = service.sync_employees()
            messages.success(request, f'Successfully synced {count} employees from ZKBio')
        except Exception as e:
            messages.error(request, f'Failed to sync employees: {str(e)}')
    
    return redirect('zkbioapp:dashboard')

def sync_attendance(request):
    """Sync attendance from ZKBio"""
    if request.method == 'POST':
        try:
            days = int(request.POST.get('days', 1))
            start_date_str = request.POST.get('start_date')
            end_date_str = request.POST.get('end_date')
            
            service = ZKBioService()
            
            if start_date_str and end_date_str:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
                count = service.sync_attendance(start_date=start_date, end_date=end_date)
                messages.success(request, f'Successfully synced {count} attendance records from {start_date} to {end_date}')
            else:
                count = service.sync_attendance(days=days)
                messages.success(request, f'Successfully synced {count} attendance records for last {days} day(s)')
                
        except Exception as e:
            messages.error(request, f'Failed to sync attendance: {str(e)}')
    
    return redirect('zkbioapp:dashboard')

def sync_erp(request):
    """Sync attendance to ERP"""
    if request.method == 'POST':
        try:
            max_records = int(request.POST.get('max_records', 100))
            date_str = request.POST.get('date')
            employee_code = request.POST.get('employee_code')
            retry_failed = request.POST.get('retry_failed') == 'on'
            
            service = ERPService()
            
            attendance_date = None
            if date_str:
                attendance_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            
            result = service.sync_attendance(
                max_records=max_records,
                attendance_date=attendance_date,
                employee_code=employee_code,
                retry_failed=retry_failed
            )
            
            messages.success(
                request, 
                f'ERP sync completed - Synced: {result["synced"]}, Duplicates: {result["duplicates"]}, Failed: {result["failed"]}'
            )
            
        except Exception as e:
            messages.error(request, f'Failed to sync to ERP: {str(e)}')
    
    return redirect('zkbioapp:dashboard')

def full_sync(request):
    """Perform full synchronization"""
    if request.method == 'POST':
        try:
            skip_employees = request.POST.get('skip_employees') == 'on'
            skip_attendance = request.POST.get('skip_attendance') == 'on'
            skip_erp = request.POST.get('skip_erp') == 'on'
            days = int(request.POST.get('days', 1))
            
            zkbio_service = ZKBioService()
            erp_service = ERPService()
            
            results = []
            
            # Sync employees
            if not skip_employees:
                emp_count = zkbio_service.sync_employees()
                results.append(f'Employees: {emp_count}')
            
            # Sync attendance
            if not skip_attendance:
                att_count = zkbio_service.sync_attendance(days=days)
                results.append(f'Attendance: {att_count}')
            
            # Sync to ERP
            if not skip_erp:
                erp_result = erp_service.sync_attendance()
                results.append(f'ERP - Synced: {erp_result["synced"]}, Failed: {erp_result["failed"]}')
            
            messages.success(request, f'Full sync completed - {", ".join(results)}')
            
        except Exception as e:
            messages.error(request, f'Full sync failed: {str(e)}')
    
    return redirect('zkbioapp:dashboard')

def api_stats(request):
    """API endpoint for dashboard statistics"""
    stats = SyncStats.objects.first()
    if not stats:
        return JsonResponse({'error': 'No statistics available'}, status=404)
    
    # Get recent sync stats
    erp_service = ERPService()
    recent_stats = erp_service.get_sync_stats(days=7)
    
    data = {
        'overall': {
            'total_employees': stats.total_employees,
            'active_employees': stats.active_employees,
            'total_records': stats.total_records,
            'pending_records': stats.pending_records,
            'synced_records': stats.synced_records,
            'failed_records': stats.failed_records,            
            'success_rate': stats.sync_success_rate,
        },
        'recent': recent_stats,
        'last_sync_times': {
            'employees': stats.last_employee_sync.isoformat() if stats.last_employee_sync else None,
            'zkbio': stats.last_zkbio_sync.isoformat() if stats.last_zkbio_sync else None,
            'erp': stats.last_erp_sync.isoformat() if stats.last_erp_sync else None,
        }
    }
    
    return JsonResponse(data)