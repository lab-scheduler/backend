"""
Hospital Lab Resource Scheduling System - Scheduler Engine
"""
from datetime import date, timedelta
from typing import List, Dict, Set, Optional, Tuple
from collections import defaultdict
from models import (
    StaffMember, Shift, LeaveRequest, WorkPipeline, 
    LabDepartment, ShiftType, LeaveStatus, SkillLevel
)


class SchedulingConflict:
    """Represents a scheduling conflict or issue"""
    def __init__(self, severity: str, message: str, affected_shift: Optional[Shift] = None):
        self.severity = severity  # 'critical', 'warning', 'info'
        self.message = message
        self.affected_shift = affected_shift
    
    def __str__(self):
        return f"[{self.severity.upper()}] {self.message}"


class LabScheduler:
    """Main scheduling engine for hospital lab resources"""
    
    def __init__(self):
        self.staff_members: List[StaffMember] = []
        self.shifts: List[Shift] = []
        self.leave_requests: List[LeaveRequest] = []
        self.work_pipelines: List[WorkPipeline] = []
        self.staff_hours: Dict[str, Dict[date, float]] = defaultdict(lambda: defaultdict(float))
    
    def add_staff(self, staff: StaffMember):
        """Add a staff member to the system"""
        self.staff_members.append(staff)
    
    def add_shift(self, shift: Shift):
        """Add a shift to the schedule"""
        self.shifts.append(shift)
    
    def add_leave_request(self, leave: LeaveRequest) -> Tuple[bool, str]:
        """Add and process a leave request"""
        self.leave_requests.append(leave)
        
        # Auto-approve urgent leave
        if leave.is_urgent():
            leave.approve("System - Urgent Leave")
            self._handle_urgent_leave(leave)
            return True, "Urgent leave auto-approved and schedule adjusted"
        
        return True, "Leave request submitted for approval"
    
    def add_work_pipeline(self, pipeline: WorkPipeline):
        """Add a work pipeline to the system"""
        self.work_pipelines.append(pipeline)
    
    def approve_leave(self, leave_id: str, approver: str) -> bool:
        """Approve a leave request and adjust schedule"""
        leave = self._find_leave(leave_id)
        if leave and leave.status == LeaveStatus.PENDING:
            leave.approve(approver)
            self._handle_approved_leave(leave)
            return True
        return False
    
    def _find_leave(self, leave_id: str) -> Optional[LeaveRequest]:
        """Find a leave request by ID"""
        for leave in self.leave_requests:
            if leave.id == leave_id:
                return leave
        return None
    
    def _handle_urgent_leave(self, leave: LeaveRequest):
        """Handle urgent leave by finding replacements"""
        affected_dates = leave.get_affected_dates()
        affected_shifts = [
            shift for shift in self.shifts
            if shift.date in affected_dates and leave.staff in shift.assigned_staff
        ]
        
        for shift in affected_shifts:
            shift.remove_staff(leave.staff)
            # Try to find replacement
            replacement = self._find_replacement(shift, leave.staff)
            if replacement:
                shift.assign_staff(replacement)
    
    def _handle_approved_leave(self, leave: LeaveRequest):
        """Handle approved leave by adjusting schedule"""
        self._handle_urgent_leave(leave)  # Same process as urgent
    
    def _find_replacement(self, shift: Shift, unavailable_staff: StaffMember) -> Optional[StaffMember]:
        """Find a replacement staff member for a shift"""
        for staff in self.staff_members:
            if staff == unavailable_staff:
                continue
            
            if self.is_staff_available(staff, shift.date):
                can_assign, _ = shift.can_assign(staff)
                if can_assign:
                    # Check weekly hour constraints
                    week_start = shift.date - timedelta(days=shift.date.weekday())
                    weekly_hours = self._get_weekly_hours(staff, week_start)
                    if weekly_hours + 8 <= staff.max_hours_per_week:
                        return staff
        
        return None
    
    def is_staff_available(self, staff: StaffMember, check_date: date) -> bool:
        """Check if staff member is available on a given date"""
        approved_leaves = [
            leave for leave in self.leave_requests
            if leave.staff == staff and 
            leave.status == LeaveStatus.APPROVED and
            leave.start_date <= check_date <= leave.end_date
        ]
        return len(approved_leaves) == 0
    
    def assign_staff_to_shift(self, staff: StaffMember, shift: Shift) -> Tuple[bool, str]:
        """Manually assign staff to a shift"""
        # Check availability
        if not self.is_staff_available(staff, shift.date):
            return False, "Staff member is on leave"
        
        # Check weekly hours
        week_start = shift.date - timedelta(days=shift.date.weekday())
        weekly_hours = self._get_weekly_hours(staff, week_start)
        if weekly_hours + 8 > staff.max_hours_per_week:
            return False, f"Would exceed maximum weekly hours ({staff.max_hours_per_week})"
        
        # Check if can assign
        can_assign, reason = shift.can_assign(staff)
        if not can_assign:
            return False, reason
        
        # Assign
        success = shift.assign_staff(staff)
        if success:
            self._record_hours(staff, shift.date, 8)
            return True, "Staff assigned successfully"
        
        return False, "Assignment failed"
    
    def _record_hours(self, staff: StaffMember, work_date: date, hours: float):
        """Record hours worked by staff member"""
        self.staff_hours[staff.id][work_date] += hours
    
    def _get_weekly_hours(self, staff: StaffMember, week_start: date) -> float:
        """Get total hours worked by staff in a week"""
        total_hours = 0
        for i in range(7):
            check_date = week_start + timedelta(days=i)
            total_hours += self.staff_hours[staff.id][check_date]
        return total_hours
    
    def auto_schedule_shift(self, shift: Shift) -> List[SchedulingConflict]:
        """Automatically schedule staff for a shift using constraint satisfaction"""
        conflicts = []
        
        # Get available staff for this department
        available_staff = [
            staff for staff in self.staff_members
            if staff.can_work_in_department(shift.department) and
            self.is_staff_available(staff, shift.date)
        ]
        
        if not available_staff:
            conflicts.append(SchedulingConflict(
                'critical',
                f"No available staff for {shift.department.value} on {shift.date}",
                shift
            ))
            return conflicts
        
        # Score staff based on suitability
        scored_staff = []
        for staff in available_staff:
            score = self._calculate_staff_score(staff, shift)
            if score > 0:
                scored_staff.append((staff, score))
        
        # Sort by score (highest first)
        scored_staff.sort(key=lambda x: x[1], reverse=True)
        
        # Assign staff
        assigned_count = 0
        supervisor_assigned = False
        
        for staff, score in scored_staff:
            if assigned_count >= shift.max_staff:
                break
            
            success, reason = self.assign_staff_to_shift(staff, shift)
            if success:
                assigned_count += 1
                if staff.is_supervisor:
                    supervisor_assigned = True
        
        # Check if requirements are met
        if assigned_count < shift.min_staff:
            conflicts.append(SchedulingConflict(
                'critical',
                f"Shift understaffed: {assigned_count}/{shift.min_staff} minimum",
                shift
            ))
        
        if shift.requires_supervisor and not supervisor_assigned:
            conflicts.append(SchedulingConflict(
                'warning',
                f"No supervisor assigned to shift",
                shift
            ))
        
        return conflicts
    
    def _calculate_staff_score(self, staff: StaffMember, shift: Shift) -> float:
        """Calculate suitability score for staff-shift pairing"""
        score = 0
        
        # Check if shift type is preferred
        if shift.shift_type in staff.preferred_shifts:
            score += 10
        
        # Check skill levels
        for skill in shift.required_skills:
            if staff.has_skill(skill):
                skill_level = staff.skills[skill]
                score += skill_level.value * 5
        
        # Supervisor bonus if needed
        if shift.requires_supervisor and staff.is_supervisor:
            score += 20
        
        # Check weekly hours utilization
        week_start = shift.date - timedelta(days=shift.date.weekday())
        weekly_hours = self._get_weekly_hours(staff, week_start)
        utilization = weekly_hours / staff.max_hours_per_week
        
        # Prefer staff with lower utilization to balance workload
        if utilization < 0.5:
            score += 5
        elif utilization > 0.9:
            score -= 10
        
        # Priority boost
        score += shift.priority * 2
        
        return score
    
    def schedule_date_range(self, start_date: date, end_date: date) -> Dict[date, List[SchedulingConflict]]:
        """Auto-schedule all shifts in a date range"""
        conflicts_by_date = {}
        
        shifts_in_range = [
            shift for shift in self.shifts
            if start_date <= shift.date <= end_date
        ]
        
        # Sort by priority (highest first) and date
        shifts_in_range.sort(key=lambda s: (s.date, -s.priority))
        
        for shift in shifts_in_range:
            if not shift.is_fully_staffed():
                conflicts = self.auto_schedule_shift(shift)
                if conflicts:
                    if shift.date not in conflicts_by_date:
                        conflicts_by_date[shift.date] = []
                    conflicts_by_date[shift.date].extend(conflicts)
        
        return conflicts_by_date
    
    def schedule_work_pipelines(self):
        """Schedule shifts for all active work pipelines"""
        for pipeline in self.work_pipelines:
            scheduled_dates = pipeline.get_scheduled_dates()
            
            for work_date in scheduled_dates:
                # Create shift for pipeline work
                shift = Shift(
                    date=work_date,
                    shift_type=ShiftType.DAY,
                    department=pipeline.department,
                    required_skills=pipeline.required_skills,
                    min_staff=max(1, len(pipeline.assigned_staff)),
                    max_staff=len(pipeline.assigned_staff) if pipeline.assigned_staff else 3,
                    priority=pipeline.priority
                )
                
                self.add_shift(shift)
                
                # Try to assign pre-assigned staff
                for staff in pipeline.assigned_staff:
                    self.assign_staff_to_shift(staff, shift)
    
    def get_staff_schedule(self, staff: StaffMember, start_date: date, end_date: date) -> List[Shift]:
        """Get all shifts for a staff member in date range"""
        return [
            shift for shift in self.shifts
            if start_date <= shift.date <= end_date and
            staff in shift.assigned_staff
        ]
    
    def get_department_schedule(self, department: LabDepartment, start_date: date, end_date: date) -> List[Shift]:
        """Get all shifts for a department in date range"""
        return [
            shift for shift in self.shifts
            if start_date <= shift.date <= end_date and
            shift.department == department
        ]
    
    def get_conflicts_summary(self) -> Dict[str, int]:
        """Get summary of all scheduling conflicts"""
        all_conflicts = []
        for shift in self.shifts:
            if not shift.is_fully_staffed():
                all_conflicts.append(SchedulingConflict(
                    'critical' if len(shift.assigned_staff) < shift.min_staff else 'warning',
                    f"Shift not fully staffed",
                    shift
                ))
        
        summary = {
            'critical': len([c for c in all_conflicts if c.severity == 'critical']),
            'warning': len([c for c in all_conflicts if c.severity == 'warning']),
            'info': len([c for c in all_conflicts if c.severity == 'info'])
        }
        
        return summary
    
    def get_workload_analysis(self) -> Dict[str, Dict]:
        """Analyze workload distribution across staff"""
        analysis = {}
        
        for staff in self.staff_members:
            total_hours = sum(self.staff_hours[staff.id].values())
            shifts_count = len([
                shift for shift in self.shifts 
                if staff in shift.assigned_staff
            ])
            
            analysis[staff.name] = {
                'total_hours': total_hours,
                'shifts_count': shifts_count,
                'max_weekly_hours': staff.max_hours_per_week,
                'utilization': total_hours / (staff.max_hours_per_week * 4) if staff.max_hours_per_week > 0 else 0
            }
        
        return analysis
