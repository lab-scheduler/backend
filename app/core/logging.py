# app/core/logging.py
"""
Structured logging configuration for the Lab Scheduler application.
Provides consistent logging across all modules with context tracking.
"""
import logging
import sys
from typing import Any, Dict
from datetime import datetime

# Configure basic logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

def get_logger(name: str) -> logging.Logger:
    """
    Get a configured logger instance.
    
    Args:
        name: Logger name (usually __name__ from calling module)
        
    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)


class SchedulerLogger:
    """
    Specialized logger for scheduler operations with structured context.
    """
    
    def __init__(self, logger_name: str = "scheduler"):
        self.logger = logging.getLogger(logger_name)
    
    def log_scheduler_run(self, org_id: int, start_date: str, end_date: str, 
                         use_cpsat: bool, metadata: Dict[str, Any] = None):
        """Log scheduler execution start"""
        context = {
            "org_id": org_id,
            "start_date": start_date,
            "end_date": end_date,
            "use_cpsat": use_cpsat,
            "timestamp": datetime.utcnow().isoformat()
        }
        if metadata:
            context.update(metadata)
        
        self.logger.info(f"Scheduler run started: {context}")
    
    def log_scheduler_result(self, org_id: int, success: bool, 
                            shifts_count: int, staff_count: int,
                            metadata: Dict[str, Any] = None):
        """Log scheduler execution result"""
        context = {
            "org_id": org_id,
            "success": success,
            "shifts_count": shifts_count,
            "staff_count": staff_count,
            "timestamp": datetime.utcnow().isoformat()
        }
        if metadata:
            context.update(metadata)
        
        if success:
            self.logger.info(f"Scheduler run completed successfully: {context}")
        else:
            self.logger.error(f"Scheduler run failed: {context}")
    
    def log_leave_action(self, action: str, leave_code: str, employee_id: str,
                        approver_id: str = None, metadata: Dict[str, Any] = None):
        """Log leave approval/rejection actions"""
        context = {
            "action": action,
            "leave_code": leave_code,
            "employee_id": employee_id,
            "approver_id": approver_id,
            "timestamp": datetime.utcnow().isoformat()
        }
        if metadata:
            context.update(metadata)
        
        self.logger.info(f"Leave action: {context}")
    
    def log_error(self, operation: str, error: Exception, 
                 metadata: Dict[str, Any] = None):
        """Log errors with context"""
        context = {
            "operation": operation,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "timestamp": datetime.utcnow().isoformat()
        }
        if metadata:
            context.update(metadata)
        
        self.logger.error(f"Operation failed: {context}", exc_info=True)


# Global scheduler logger instance
scheduler_logger = SchedulerLogger()
