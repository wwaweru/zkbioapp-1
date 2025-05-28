# zkbioapp/services/zkbio_service.py
import json
import logging
import requests
from datetime import datetime, timedelta
from django.conf import settings
from django.utils import timezone
from django.db import transaction
from .base import BaseService
from ..models import Employee, AttendanceRecord, SyncLog, SyncStats

logger = logging.getLogger(__name__)

class ZKBioService(BaseService):
    """Service for interacting with ZKBio API"""
    
    def __init__(self):
        super().__init__()
        self.base_url = settings.ZKBIO_API_BASE_URL
        self.username = settings.ZKBIO_USERNAME
        self.password = settings.ZKBIO_PASSWORD
        self.token = None
        self.token_expiry = None
        self.session = requests.Session()
        self.session.timeout = 30

    def _get_auth_headers(self):
        """Get authenticated headers with current token"""
        if not self.token or (self.token_expiry and self.token_expiry <= timezone.now()):
            self._refresh_token()
        return {
            'Content-Type': 'application/json',
            'Authorization': f'Token {self.token}'
        }

    def _refresh_token(self):
        """Refresh authentication token"""
        url = f"{self.base_url}/api-token-auth/"
        try:
            response = self.session.post(
                url,
                json={'username': self.username, 'password': self.password}
            )
            response.raise_for_status()
            data = response.json()
            self.token = data['token']
            self.token_expiry = timezone.now() + timedelta(hours=1)
            logger.info("Successfully refreshed ZKBio token")
        except Exception as e:
            logger.error(f"Failed to refresh ZKBio token: {str(e)}")
            raise

    def sync_employees(self):
        """Fetch and sync all employees from ZKBio"""
        with self.log_execution('zkbio_employees', 'Employee synchronization'):
            employees_data = self._fetch_all_employees()
            count = self._process_employees(employees_data)
            SyncStats.update_stats()
            logger.info(f"Successfully synced {count} employees")
            return count

    def _fetch_all_employees(self):
        """Fetch all employees from ZKBio with pagination support"""
        base_url = f"{self.base_url}/personnel/api/employees/"
        all_employees = []
        page = 1
        max_pages = 100
        
        for current_page in range(1, max_pages + 1):
            url = f"{base_url}?page={current_page}"
            
            try:
                response = self.session.get(url, headers=self._get_auth_headers())
                if response.status_code == 401:
                    self._refresh_token()
                    response = self.session.get(url, headers=self._get_auth_headers())
                response.raise_for_status()
            except Exception as e:
                logger.error(f"Error fetching employee page {current_page}: {str(e)}")
                break
            
            data = response.json()
            if data.get('code') != 0:
                logger.error(f"API error on employee page {current_page}: {data.get('msg', 'Unknown error')}")
                break
            
            page_employees = data.get('data', [])
            if not page_employees:
                break
                
            all_employees.extend(page_employees)
            
            if len(page_employees) < 10:
                break
        
        return all_employees

    def _process_employees(self, employees_data):
        """Process and save employee data"""
        count = 0
        with transaction.atomic():
            for emp_data in employees_data:
                try:
                    emp_code = emp_data.get('emp_code')
                    if not emp_code:
                        continue
                        
                    area_name = ''
                    if emp_data.get('area') and isinstance(emp_data.get('area'), list) and len(emp_data.get('area')) > 0:
                        area_name = emp_data.get('area')[0].get('area_name', '')
                        
                    defaults = {
                        'first_name': emp_data.get('first_name', 'Unknown'),
                        'last_name': emp_data.get('last_name', ''),
                        'full_name': emp_data.get('full_name', ''),
                        'department': emp_data.get('department', {}).get('dept_name', ''),
                        'area_name': area_name,
                        'is_active': True,
                    }
                    
                    employee, created = Employee.objects.update_or_create(
                        emp_code=emp_code,
                        defaults=defaults
                    )
                    count += 1
                    
                    if created:
                        logger.info(f"Created new employee: {emp_code}")
                    else:
                        logger.debug(f"Updated employee: {emp_code}")
                        
                except Exception as e:
                    logger.error(f"Error processing employee {emp_data.get('emp_code', 'unknown')}: {str(e)}")
        
        return count

    def sync_attendance(self, days=1, start_date=None, end_date=None):
        """Fetch attendance records for given period"""
        with self.log_execution('zkbio_fetch', 'Attendance synchronization'):
            if start_date and end_date:
                # Use provided date range
                start_datetime = timezone.make_aware(datetime.combine(start_date, datetime.min.time()))
                end_datetime = timezone.make_aware(datetime.combine(end_date, datetime.max.time()))
            else:
                # Use days parameter
                end_datetime = timezone.now()
                start_datetime = end_datetime - timedelta(days=days)
            
            records_data = self._fetch_attendance_records(start_datetime, end_datetime)
            count = self._process_attendance_records(records_data)
            SyncStats.update_stats()
            
            logger.info(f"Successfully synced {count} attendance records")
            return count

    def _fetch_attendance_records(self, start_datetime, end_datetime):
        """Fetch attendance records from ZKBio API"""
        base_url = f"{self.base_url}/iclock/api/transactions/"
        all_records = []
        page = 1
        max_pages = 100
        
        base_params = {
            'start_time': start_datetime.strftime('%Y-%m-%d %H:%M:%S'),
            'end_time': end_datetime.strftime('%Y-%m-%d %H:%M:%S')
        }
        
        for current_page in range(1, max_pages + 1):
            params = {**base_params, 'page': current_page}
            
            try:
                response = self.session.get(
                    base_url,
                    headers=self._get_auth_headers(),
                    params=params
                )
                if response.status_code == 401:
                    self._refresh_token()
                    response = self.session.get(
                        base_url,
                        headers=self._get_auth_headers(),
                        params=params
                    )
                response.raise_for_status()
            except Exception as e:
                logger.error(f"Error fetching attendance page {current_page}: {str(e)}")
                break
            
            data = response.json()
            if data.get('code') != 0:
                logger.error(f"API error on attendance page {current_page}: {data.get('msg', 'Unknown error')}")
                break
            
            page_records = data.get('data', [])
            if not page_records:
                break
                
            all_records.extend(page_records)
            
            if len(page_records) < 10:
                break
        
        return all_records

    def _process_attendance_records(self, records):
        """Process and save attendance records"""
        count = 0
        
        # Group records by employee and date
        employee_date_records = {}
        for record in records:
            try:
                emp_code = record.get('emp_code')
                punch_time_str = record.get('punch_time')
                transaction_id = record.get('id')
                department = record.get('department', 'DELIVERY')
                area_alias = record.get('area_alias', 'THIKA BRANCH')
                
                if not all([emp_code, punch_time_str, transaction_id]):
                    continue
                    
                punch_time = timezone.make_aware(datetime.strptime(punch_time_str, '%Y-%m-%d %H:%M:%S'))
                attendance_date = punch_time.date()
                
                key = f"{emp_code}_{attendance_date}"
                
                if key not in employee_date_records:
                    employee_date_records[key] = {
                        'emp_code': emp_code,
                        'date': attendance_date,
                        'punches': [],
                        'transaction_ids': [],
                        'department': department,
                        'area_alias': area_alias
                    }
                
                employee_date_records[key]['punches'].append(punch_time)
                employee_date_records[key]['transaction_ids'].append(transaction_id)
                
            except Exception as e:
                logger.error(f"Error processing attendance record: {str(e)}")
        
        # Save grouped records
        with transaction.atomic():
            for key, data in employee_date_records.items():
                try:
                    count += self._save_attendance_record(data)
                except Exception as e:
                    logger.error(f"Error saving attendance record for key {key}: {str(e)}")
        
        return count

    def _save_attendance_record(self, data):
        """Save individual attendance record"""
        emp_code = data['emp_code']
        attendance_date = data['date']
        
        try:
            employee = Employee.objects.get(emp_code=emp_code)
        except Employee.DoesNotExist:
            logger.warning(f"Employee {emp_code} not found, skipping record")
            return 0
        
        punches = sorted(data['punches'])
        if not punches:
            return 0
        
        in_time = punches[0]
        out_time = punches[-1]
        latest_transaction_id = str(data['transaction_ids'][-1])
        
        details = {
            'all_punches': [pt.strftime('%Y-%m-%d %H:%M:%S') for pt in punches],
            'all_transaction_ids': [str(tid) for tid in data['transaction_ids']],
            'punch_count': len(punches)
        }
        
        # Check for existing record
        existing_record = AttendanceRecord.objects.filter(
            employee=employee,
            attendance_date=attendance_date
        ).first()
        
        if existing_record:
            # Update existing record
            existing_record.punch_time = out_time
            existing_record.in_time = in_time.time()
            existing_record.out_time = out_time.time()
            existing_record.department = data['department']
            existing_record.area_alias = data['area_alias']
            existing_record.details = details
            existing_record.save()
        else:
            # Create new record
            AttendanceRecord.objects.create(
                employee=employee,
                attendance_date=attendance_date,
                punch_time=out_time,
                in_time=in_time.time(),
                out_time=out_time.time(),
                zkbio_transaction_id=latest_transaction_id,
                department=data['department'],
                area_alias=data['area_alias'],
                details=details,
                status='pending',
                sync_attempts=0
            )
        
        return 1