# zkbioapp/services/erp_service.py
import json
import time
import re
import logging
import requests
from datetime import timedelta
from django.conf import settings
from django.utils import timezone
from django.db import transaction
from .base import BaseService
from ..models import Employee, AttendanceRecord, SyncLog, SyncStats

logger = logging.getLogger(__name__)

class ERPService(BaseService):
    """Service for interacting with ERP system"""
    
    def __init__(self):
        super().__init__()
        self.base_url = settings.ERP_API_BASE_URL
        self.username = settings.ERP_API_KEY
        self.password = settings.ERP_API_SECRET
        self.token = f'token {self.username}:{self.password}'
        self.session = requests.Session()
        self.session.timeout = 30
        self.max_retries = 5
        self.retry_delay = 2

    def _get_auth_headers(self):
        """Get authenticated headers with concatenated token"""
        return {
            'Content-Type': 'application/json',
            'Authorization': self.token
        }

    def _find_existing_record(self, employee_code, attendance_date):
        """Find existing attendance record in ERP by employee and date"""
        try:
            # First try with the original employee code
            erp_id = self._search_erp_attendance(employee_code, attendance_date)
            if erp_id:
                return erp_id
            
            # If not found, try to find the ERP employee ID mapping
            erp_employee_id = self._get_erp_employee_id(employee_code)
            if erp_employee_id and erp_employee_id != employee_code:
                # Try again with the ERP employee ID
                erp_id = self._search_erp_attendance(erp_employee_id, attendance_date)
                if erp_id:
                    logger.info(f"Found record using ERP employee ID {erp_employee_id} instead of {employee_code}")
                    return erp_id
            
        except Exception as e:
            logger.warning(f"Could not search for existing record: {str(e)}")
        
        return None

    def _search_erp_attendance(self, employee_identifier, attendance_date):
        """Search for attendance record in ERP using employee identifier"""
        try:
            url = f"{self.base_url}/api/resource/Attendance"
            params = {
                'filters': f'[["employee", "=", "{employee_identifier}"], ["attendance_date", "=", "{attendance_date.strftime("%Y-%m-%d")}"]]',
                'fields': '["name", "employee", "attendance_date"]',
                'limit': 1
            }
            
            response = self.session.get(
                url,
                headers=self._get_auth_headers(),
                params=params
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('data') and len(data['data']) > 0:
                    existing_record = data['data'][0]
                    return existing_record.get('name')
            
        except Exception as e:
            logger.warning(f"Error searching ERP attendance for {employee_identifier}: {str(e)}")
        
        return None

    def _get_erp_employee_id(self, employee_code):
        """Get ERP employee ID (HR-EMP-XXXXX) from employee code"""
        try:
            url = f"{self.base_url}/api/resource/Employee"
            params = {
                'filters': f'[["employee", "=", "{employee_code}"]]',
                'fields': '["name", "employee"]',
                'limit': 1
            }
            
            response = self.session.get(
                url,
                headers=self._get_auth_headers(),
                params=params
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('data') and len(data['data']) > 0:
                    employee_record = data['data'][0]
                    erp_employee_id = employee_record.get('name')
                    logger.debug(f"Found ERP employee ID {erp_employee_id} for employee code {employee_code}")
                    return erp_employee_id
            
        except Exception as e:
            logger.warning(f"Could not get ERP employee ID for {employee_code}: {str(e)}")
        
        return None

    def _extract_duplicate_id(self, response):
        """Extract ERP ID and employee ID from duplicate error response"""
        try:
            error_details = response.json()
            if error_details.get('exc_type') == 'DuplicateAttendanceError':
                exception_text = error_details.get('exception', '')
                
                # Try multiple patterns to extract the ERP attendance ID
                import re
                
                # Pattern 1: Direct HR-ATT-YYYY-NNNNN pattern
                erp_match = re.search(r'HR-ATT-\d{4}-\d{5}', exception_text)
                if erp_match:
                    erp_id = erp_match.group(0)
                    logger.info(f"Extracted ERP attendance ID from exception: {erp_id}")
                    return erp_id
                
                # Pattern 2: From HTML link in the message
                link_match = re.search(r'<a href="[^"]*attendance/([^"]*)">', exception_text)
                if link_match:
                    erp_id = link_match.group(1)
                    logger.info(f"Extracted ERP attendance ID from link: {erp_id}")
                    return erp_id
                
                # Pattern 3: From _server_messages if available
                server_messages = error_details.get('_server_messages', '')
                if server_messages:
                    server_match = re.search(r'HR-ATT-\d{4}-\d{5}', server_messages)
                    if server_match:
                        erp_id = server_match.group(0)
                        logger.info(f"Extracted ERP attendance ID from server messages: {erp_id}")
                        return erp_id
                
                # Pattern 4: Generic attendance ID extraction (fallback)
                generic_match = re.search(r'attendance/([A-Z]+-[A-Z]+-\d{4}-\d{5})', exception_text)
                if generic_match:
                    erp_id = generic_match.group(1)
                    logger.info(f"Extracted generic ERP attendance ID: {erp_id}")
                    return erp_id
                
                logger.warning(f"Could not extract ERP attendance ID from duplicate error: {exception_text}")
                
        except Exception as e:
            logger.error(f"Failed to parse duplicate error response: {e}")
        
        return "existing-record"

    def _extract_employee_id_from_duplicate(self, response):
        """Extract ERP employee ID (HR-EMP-XXXXX) from duplicate error response"""
        try:
            error_details = response.json()
            if error_details.get('exc_type') == 'DuplicateAttendanceError':
                exception_text = error_details.get('exception', '')
                
                import re
                # Extract HR-EMP-XXXXX pattern from the error message
                emp_match = re.search(r'HR-EMP-\d{5}', exception_text)
                if emp_match:
                    erp_employee_id = emp_match.group(0)
                    logger.info(f"Extracted ERP employee ID from duplicate error: {erp_employee_id}")
                    return erp_employee_id
                
                # Also try to extract from server messages
                server_messages = error_details.get('_server_messages', '')
                if server_messages:
                    server_emp_match = re.search(r'HR-EMP-\d{5}', server_messages)
                    if server_emp_match:
                        erp_employee_id = server_emp_match.group(0)
                        logger.info(f"Extracted ERP employee ID from server messages: {erp_employee_id}")
                        return erp_employee_id
                
        except Exception as e:
            logger.error(f"Failed to extract employee ID from duplicate error: {e}")
        
        return None

    def sync_attendance(self, max_records=100, attendance_date=None, employee_code=None, 
                       retry_failed=False, status_filter=None):
        """Sync attendance records to ERP"""
        with self.log_execution('erp_sync', 'ERP attendance synchronization'):
            # Build queryset
            queryset = self._build_sync_queryset(
                max_records, attendance_date, employee_code, retry_failed, status_filter
            )
            
            if not queryset.exists():
                filter_info = self._get_filter_info(attendance_date, employee_code, retry_failed)
                logger.info(f"No records to sync{filter_info}")
                return {'success': True, 'synced': 0, 'failed': 0}
            
            results = {'synced': 0, 'failed': 0}
            
            for record in queryset:
                try:
                    success, result_type, erp_id, response_data = self._sync_single_record(record)
                    
                    if success:
                        # Whether it's a new sync or existing record, mark as synced
                        self._mark_synced(record, erp_id, response_data, is_existing=(result_type == 'synced'))
                        results['synced'] += 1
                        
                        if result_type == 'synced':
                            logger.info(f"Record {record.id} found as existing in ERP (ID: {erp_id})")
                        else:
                            logger.info(f"Record {record.id} synced successfully (ERP ID: {erp_id})")
                    else:
                        self._mark_failed(record, "ERP sync failed")
                        results['failed'] += 1
                        logger.error(f"Failed to sync record {record.id}")
                        
                except Exception as e:
                    logger.error(f"Error syncing record {record.id}: {str(e)}")
                    self._mark_failed(record, str(e))
                    results['failed'] += 1
            
            SyncStats.update_stats()
            logger.info(f"Sync completed: {results}")
            return results

    def _build_sync_queryset(self, max_records, attendance_date, employee_code, retry_failed, status_filter):
        """Build queryset for records to sync"""
        if retry_failed:
            queryset = AttendanceRecord.objects.filter(
                status='failed',
                sync_attempts__lt=self.max_retries
            )
        else:
            if status_filter:
                queryset = AttendanceRecord.objects.filter(status__in=status_filter)
            else:
                queryset = AttendanceRecord.objects.filter(
                    status__in=['pending', 'failed'],
                    sync_attempts__lt=self.max_retries
                )
        
        if attendance_date:
            queryset = queryset.filter(attendance_date=attendance_date)
            
        if employee_code:
            queryset = queryset.filter(employee__emp_code=employee_code)
        
        return queryset.select_related('employee').order_by(
            'sync_attempts', 'attendance_date'
        )[:max_records]

    def _get_filter_info(self, attendance_date, employee_code, retry_failed):
        """Get human-readable filter information"""
        filters = []
        if attendance_date:
            filters.append(f"date {attendance_date}")
        if employee_code:
            filters.append(f"employee {employee_code}")
        if retry_failed:
            filters.append("failed records")
        
        return f" for {', '.join(filters)}" if filters else ""

    def _sync_single_record(self, record):
        """Sync a single attendance record to ERP"""
        payload = self._build_payload(record)
        
        for attempt in range(self.max_retries):
            try:
                success, result_type, erp_id, response_data = self._send_to_erp(payload)
                return success, result_type, erp_id, response_data
                
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 401:
                    logger.error("Invalid ERP credentials - cannot retry")
                    return False, 'error', None, None
                
                if e.response.status_code == 417:
                    # Handle duplicate error
                    duplicate_id = self._extract_duplicate_id(e.response)
                    return True, 'duplicate', duplicate_id, e.response.json() if e.response.content else {}
                
                if attempt == self.max_retries - 1:
                    logger.error(f"Failed to sync after {self.max_retries} attempts: {str(e)}")
                    return False, 'error', None, None
                
                time.sleep(self.retry_delay * (attempt + 1))
                
            except Exception as e:
                if attempt == self.max_retries - 1:
                    logger.error(f"Failed to sync after {self.max_retries} attempts: {str(e)}")
                    return False, 'error', None, None
                
                time.sleep(self.retry_delay * (attempt + 1))
        
        return False, 'error', None, None

    def _build_payload(self, record):
        """Build ERP payload in the required format"""
        in_time = None
        out_time = None
        
        if record.in_time:
            in_datetime = timezone.datetime.combine(record.attendance_date, record.in_time)
            in_time = in_datetime.strftime('%Y-%m-%d %H:%M:%S')
            
        if record.out_time:
            out_datetime = timezone.datetime.combine(record.attendance_date, record.out_time)
            out_time = out_datetime.strftime('%Y-%m-%d %H:%M:%S')
        
        # Try to get the ERP employee ID first, fallback to emp_code
        erp_employee_id = self._get_erp_employee_id(record.employee.emp_code)
        employee_identifier = erp_employee_id if erp_employee_id else record.employee.emp_code
        
        if erp_employee_id:
            logger.debug(f"Using ERP employee ID {erp_employee_id} for employee {record.employee.emp_code}")
        else:
            logger.debug(f"Using employee code {record.employee.emp_code} (ERP ID not found)")
        
        return {
            "employee": employee_identifier,
            "attendance_date": record.attendance_date.strftime('%Y-%m-%d'),
            "status": "Present",
            "in_time": in_time,
            "out_time": out_time
        }

    def _send_to_erp(self, payload):
        """Send attendance data to ERP with retry logic"""
        url = f"{self.base_url}/api/resource/Attendance"
        
        # Log the attempt
        logger.info(f"Attempting to sync to ERP: {payload}")
        print(f"ERP URL: {url}")
        print(f"Payload: {payload}")
        
        for attempt in range(self.max_retries):
            try:
                # Convert payload to JSON string as per working example
                json_payload = json.dumps(payload)
                
                print(f"Attempt {attempt + 1}: Sending to {url}")
                
                response = self.session.post(
                    url,
                    headers=self._get_auth_headers(),
                    data=json_payload  # Use data instead of json parameter
                )
                
                print(f"Response status: {response.status_code}")
                print(f"Response headers: {dict(response.headers)}")
                
                # Log response regardless of status
                try:
                    response_text = response.text
                    print(f"Response text: {response_text}")
                    logger.info(f"ERP API response (status {response.status_code}): {response_text}")
                except Exception as e:
                    print(f"Could not read response text: {e}")
                
                response.raise_for_status()
                data = response.json()
                print(f"Response data: {data}")
                logger.info(f"ERP API response: {data}")
                
                # Handle the response based on the actual structure
                # The response should contain the created record details
                if 'data' in data:
                    if isinstance(data['data'], dict) and 'name' in data['data']:
                        # Single record response - this is the expected format for POST
                        erp_id = data['data']['name']
                        logger.info(f"Successfully created attendance record: {erp_id}")
                        return True, 'success', erp_id, data
                    elif isinstance(data['data'], list) and len(data['data']) > 0:
                        # List response - get the last/newest record
                        latest_record = data['data'][-1]
                        if 'name' in latest_record:
                            erp_id = latest_record['name']
                            logger.info(f"Successfully created attendance record: {erp_id}")
                            return True, 'success', erp_id, data
                
                # If we can't extract the record ID but got a successful response
                logger.warning(f"Got successful response but could not extract record ID: {data}")
                # For debugging, let's still consider this a success if status is 200
                return True, 'success', "unknown", data
                
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 401:
                    logger.error("Invalid credentials for ERP API - cannot retry")
                    return False, 'error', None, None
                
                # Handle duplicate attendance error (HTTP 417)
                if e.response.status_code == 417:
                    try:
                        error_details = e.response.json()
                        if error_details.get('exc_type') == 'DuplicateAttendanceError':
                            # Extract ERP employee ID from the error message
                            erp_employee_id = self._extract_employee_id_from_duplicate(e.response)
                            
                            logger.info(f"Record already exists in ERP for employee {erp_employee_id or payload.get('employee', 'unknown')} on {payload.get('attendance_date', 'unknown date')}")
                            
                            # Extract existing ERP attendance ID from the error response
                            erp_attendance_id = self._extract_duplicate_id(e.response)
                            
                            if erp_attendance_id and erp_attendance_id != "existing-record":
                                logger.info(f"Successfully extracted existing ERP attendance ID: {erp_attendance_id}")
                            else:
                                # Try to find the record using the extracted employee ID
                                if erp_employee_id:
                                    logger.info(f"Attempting to find attendance record using ERP employee ID: {erp_employee_id}")
                                    # Parse attendance date from payload
                                    from datetime import datetime
                                    att_date = datetime.strptime(payload.get('attendance_date'), '%Y-%m-%d').date()
                                    found_attendance_id = self._search_erp_attendance(erp_employee_id, att_date)
                                    if found_attendance_id:
                                        erp_attendance_id = found_attendance_id
                                        logger.info(f"Found existing attendance record via ERP employee ID search: {erp_attendance_id}")
                                    else:
                                        logger.info("Could not find attendance record via search, using generic identifier")
                                        erp_attendance_id = "existing-record"
                                else:
                                    logger.info("Using generic existing record identifier")
                                    erp_attendance_id = "existing-record"
                            
                            # Mark as synced since record exists in ERP (likely was synced before but status not updated)
                            return True, 'synced', erp_attendance_id, error_details
                            
                    except Exception as parse_error:
                        logger.error(f"Failed to parse duplicate error response: {parse_error}")
                        # Still treat as successful sync since record exists
                        return True, 'synced', "existing-record", {}
                
                # Log the error response details for debugging
                try:
                    error_details = e.response.json()
                    logger.error(f"ERP API error: {error_details}")
                    print(f"ERP API error response: {error_details}")
                except:
                    logger.error(f"ERP API error: {str(e)}")
                
                if attempt == self.max_retries - 1:
                    logger.error(f"Failed to sync to ERP after {self.max_retries} attempts: {str(e)}")
                    return False, 'error', None, None
                
                time.sleep(self.retry_delay * (attempt + 1))
                logger.warning(f"Retrying ERP sync (attempt {attempt + 2})")
                
            except Exception as e:
                logger.error(f"Exception during ERP sync: {str(e)}")
                print(f"Exception during ERP sync: {str(e)}")
                if attempt == self.max_retries - 1:
                    logger.error(f"Failed to sync to ERP after {self.max_retries} attempts: {str(e)}")
                    return False, 'error', None, None
                
                time.sleep(self.retry_delay * (attempt + 1))
                logger.warning(f"Retrying ERP sync (attempt {attempt + 2})")
        
        # If we reach here, all attempts failed
        return False, 'error', None, None

    def _extract_erp_id(self, response_data):
        """Extract ERP ID from response data"""
        if 'data' in response_data:
            if isinstance(response_data['data'], dict) and 'name' in response_data['data']:
                return response_data['data']['name']
            elif isinstance(response_data['data'], list) and len(response_data['data']) > 0:
                latest_record = response_data['data'][-1]
                if 'name' in latest_record:
                    return latest_record['name']
        return None

    def _extract_duplicate_id(self, response):
        """Extract ERP ID from duplicate error response"""
        try:
            error_details = response.json()
            if error_details.get('exc_type') == 'DuplicateAttendanceError':
                exception_text = error_details.get('exception', '')
                
                # Try multiple patterns to extract the ERP ID
                import re
                
                # Pattern 1: Direct HR-ATT-YYYY-NNNNN pattern
                erp_match = re.search(r'HR-ATT-\d{4}-\d{5}', exception_text)
                if erp_match:
                    erp_id = erp_match.group(0)
                    logger.info(f"Extracted ERP ID from exception: {erp_id}")
                    return erp_id
                
                # Pattern 2: From HTML link in the message
                link_match = re.search(r'<a href="[^"]*attendance/([^"]*)">', exception_text)
                if link_match:
                    erp_id = link_match.group(1)
                    logger.info(f"Extracted ERP ID from link: {erp_id}")
                    return erp_id
                
                # Pattern 3: From _server_messages if available
                server_messages = error_details.get('_server_messages', '')
                if server_messages:
                    server_match = re.search(r'HR-ATT-\d{4}-\d{5}', server_messages)
                    if server_match:
                        erp_id = server_match.group(0)
                        logger.info(f"Extracted ERP ID from server messages: {erp_id}")
                        return erp_id
                
                # Pattern 4: Generic attendance ID extraction (fallback)
                generic_match = re.search(r'attendance/([A-Z]+-[A-Z]+-\d{4}-\d{5})', exception_text)
                if generic_match:
                    erp_id = generic_match.group(1)
                    logger.info(f"Extracted generic ERP ID: {erp_id}")
                    return erp_id
                
                logger.warning(f"Could not extract ERP ID from duplicate error: {exception_text}")
                
        except Exception as e:
            logger.error(f"Failed to parse duplicate error response: {e}")
        
        return "existing-record"

    def _mark_synced(self, record, erp_id, response_data=None, is_existing=False):
        """Mark record as successfully synced"""
        with transaction.atomic():
            record.erp_attendance_id = erp_id
            record.status = 'synced'
            record.sync_attempts += 1
            record.last_sync_attempt = timezone.now()
            record.error_message = None
            record.save()
            
            # Log message depends on whether this was a new sync or existing record
            if is_existing:
                log_message = f"Found existing attendance record in ERP for {record.employee.emp_code}"
                log_status = 'info'
            else:
                log_message = f"Synced attendance for {record.employee.emp_code}"
                log_status = 'success'
            
            self._create_log(
                log_type='erp_sync',
                status=log_status,
                message=log_message,
                details={
                    'erp_attendance_id': erp_id,
                    'zkbio_record_id': record.id,
                    'attendance_date': record.attendance_date.isoformat(),
                    'is_existing_record': is_existing,
                    'full_response': response_data
                },
                related_employee=record.employee
            )

    def _mark_failed(self, record, error):
        """Mark record as failed to sync"""
        with transaction.atomic():
            record.status = 'failed'
            record.sync_attempts += 1
            record.last_sync_attempt = timezone.now()
            record.error_message = str(error)[:500]  # Limit error message length
            record.save()
            
            self._create_log(
                log_type='erp_sync',
                status='error',
                message=f"Failed to sync attendance for {record.employee.emp_code}",
                details={
                    'error': str(error),
                    'attempts': record.sync_attempts,
                    'zkbio_record_id': record.id,
                    'attendance_date': record.attendance_date.isoformat()
                },
                related_employee=record.employee
            )

    def get_sync_stats(self, days=7):
        """Get synchronization statistics for the last N days"""
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)
        
        records = AttendanceRecord.objects.filter(
            attendance_date__gte=start_date,
            attendance_date__lte=end_date
        )
        
        stats = {
            'total_records': records.count(),
            'pending': records.filter(status='pending').count(),
            'synced': records.filter(status='synced').count(),
            'failed': records.filter(status='failed').count(),
            'success_rate': 0
        }
        
        total_processed = stats['synced'] + stats['failed']
        if total_processed > 0:
            stats['success_rate'] = round((stats['synced'] / total_processed) * 100, 2)
        
        return stats
