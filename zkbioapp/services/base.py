import logging
import time
from contextlib import contextmanager
from django.utils import timezone
from ..models import SyncLog

logger = logging.getLogger(__name__)

class BaseService:
    """Base service class with common functionality"""
    
    def __init__(self):
        self.logger = logger
    
    @contextmanager
    def log_execution(self, log_type, operation_name):
        """Context manager for logging execution time and results"""
        start_time = time.time()
        try:
            yield
            execution_time = time.time() - start_time
            self._create_log(
                log_type=log_type,
                status='success',
                message=f"{operation_name} completed successfully",
                details={'execution_time_seconds': execution_time},
                execution_time=execution_time
            )
        except Exception as e:
            execution_time = time.time() - start_time
            self._create_log(
                log_type=log_type,
                status='error',
                message=f"{operation_name} failed: {str(e)}",
                details={
                    'error': str(e),
                    'execution_time_seconds': execution_time
                },
                execution_time=execution_time
            )
            raise
    
    def _create_log(self, log_type, status, message, details=None, related_employee=None, execution_time=None):
        """Create a sync log entry"""
        SyncLog.objects.create(
            log_type=log_type,
            status=status,
            message=message,
            details=details or {},
            related_employee=related_employee,
            execution_time=execution_time
        )