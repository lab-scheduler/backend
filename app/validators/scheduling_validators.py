# app/validators/scheduling_validators.py
"""
Input validators for scheduling operations.
Provides comprehensive validation for date ranges, scheduling parameters, and business rules.
"""
from pydantic import BaseModel, Field, validator
from datetime import date, timedelta
from typing import Optional


class DateRangeValidator(BaseModel):
    """Validates date range inputs"""
    start_date: date
    end_date: date
    
    @validator('end_date')
    def end_after_start(cls, v, values):
        """Ensure end_date is after start_date"""
        if 'start_date' in values and v < values['start_date']:
            raise ValueError('end_date must be on or after start_date')
        return v
    
    @validator('end_date')
    def max_range_one_year(cls, v, values):
        """Limit date range to maximum 1 year"""
        if 'start_date' in values:
            delta = (v - values['start_date']).days
            if delta > 365:
                raise ValueError('Date range cannot exceed 1 year (365 days)')
        return v


class ScheduleRequestValidator(BaseModel):
    """Validates scheduler run requests"""
    start_date: date
    end_date: date
    use_cpsat: bool = False
    cpsat_time: int = Field(default=30, ge=10, le=300, description="CPSAT solver time limit in seconds")
    max_shifts_per_day: int = Field(default=1, ge=1, le=3, description="Maximum shifts per staff per day")
    max_work_days_per_week: int = Field(default=5, ge=1, le=7, description="Maximum work days per week")
    
    @validator('end_date')
    def end_after_start(cls, v, values):
        if 'start_date' in values and v < values['start_date']:
            raise ValueError('end_date must be on or after start_date')
        return v
    
    @validator('end_date')
    def reasonable_range(cls, v, values):
        """Warn for very large ranges"""
        if 'start_date' in values:
            delta = (v - values['start_date']).days
            if delta > 90:
                # Allow but could add warning in logs
                pass
            if delta > 365:
                raise ValueError('Date range cannot exceed 1 year')
        return v
    
    @validator('start_date')
    def not_too_far_past(cls, v):
        """Prevent scheduling too far in the past"""
        if v < date.today() - timedelta(days=365):
            raise ValueError('Cannot schedule more than 1 year in the past')
        return v


class PaginationValidator(BaseModel):
    """Validates pagination parameters"""
    skip: int = Field(default=0, ge=0, description="Number of items to skip")
    limit: int = Field(default=50, ge=1, le=100, description="Maximum items per page")
    
    @validator('limit')
    def limit_not_too_large(cls, v):
        """Ensure limit is reasonable"""
        if v > 100:
            raise ValueError('Limit cannot exceed 100 items per page')
        return v
