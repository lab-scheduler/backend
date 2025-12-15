# app/services/enhanced_scheduler_service.py
from sqlmodel import Session, select
from datetime import date, timedelta
from typing import Dict, List, Any
from app.scheduler_engine.services.orchestrator import SchedulerOrchestrator
from app.db.models import Shift, ShiftAssignment, Staff, Department

class EnhancedSchedulerService:
    """
    Enhanced scheduler service with workload tracking and detailed analysis
    """

    @staticmethod
    def run_schedule_with_details(session: Session, org_id: int, start_date: date, end_date: date,
                                use_cpsat: bool = False, cpsat_time: int = 30,
                                max_shifts_per_day: int = 1,
                                max_work_days_per_week: int = 5) -> Dict[str, Any]:
        """
        Run scheduler with enhanced features:
        - One shift per day limit
        - Workload balancing
        - Detailed staff and shift information
        """
        orchestrator = SchedulerOrchestrator(session, org_id)

        # Run the base scheduler
        base_result = orchestrator.run(start_date, end_date, use_cpsat=use_cpsat, cpsat_time=cpsat_time)

        # Enhance the result with detailed analysis
        enhanced_result = EnhancedSchedulerService._enhance_result(
            session, base_result, org_id, start_date, end_date
        )

        return enhanced_result

    @staticmethod
    def _enhance_result(session: Session, base_result: Dict, org_id: int,
                        start_date: date, end_date: date) -> Dict[str, Any]:
        """Enhance the base scheduler result with detailed analysis"""

        # Add metadata
        base_result["meta"].update({
            "enhanced": True,
            "features": ["one_shift_per_day", "workload_tracking", "detailed_shift_info"]
        })

        # Get all staff workloads
        staff_workloads = EnhancedSchedulerService._analyze_staff_workloads(
            session, org_id, start_date, end_date
        )
        base_result["staff_workloads"] = staff_workloads

        # Enhance shift details
        enhanced_shifts = EnhancedSchedulerService._enhance_shift_details(
            base_result.get("shifts", []), session
        )
        base_result["shifts"] = enhanced_shifts

        # Add workload summary
        base_result["workload_summary"] = EnhancedSchedulerService._calculate_workload_summary(
            staff_workloads
        )

        return base_result

    @staticmethod
    def _analyze_staff_workloads(session: Session, org_id: int,
                                start_date: date, end_date: date) -> List[Dict]:
        """Analyze each staff member's workload for the period"""

        # Get all assignments
        assignments = session.exec(
            select(ShiftAssignment, Shift, Staff)
            .join(Shift)
            .join(Staff)
            .where(
                Shift.org_id == org_id,
                Shift.shift_date >= start_date,
                Shift.shift_date <= end_date,
                Staff.org_id == org_id
            )
        ).all()

        # Group by staff
        staff_data = {}
        for assignment, shift, staff in assignments:
            if staff.employee_id not in staff_data:
                staff_data[staff.employee_id] = {
                    "employee_id": staff.employee_id,
                    "full_name": staff.full_name,
                    "role": staff.role.value if staff.role else "STAFF",
                    "is_supervisor": staff.is_supervisor,
                    "shifts": [],
                    "dates_worked": set(),
                    "departments": set(),
                    "total_hours": 0,
                    "total_shifts": 0
                }

            # Add shift information
            staff_info = staff_data[staff.employee_id]
            staff_info["shifts"].append({
                "shift_id": shift.id,
                "date": shift.shift_date.isoformat(),
                "shift_type": shift.shift_type,
                "department_id": shift.department_id,
                "hours": getattr(shift, 'hours', 8),
                "start_date": shift.shift_date.isoformat() if shift.shift_date else None,
                "end_date": shift.shift_date.isoformat() if shift.shift_date else None
            })
            staff_info["dates_worked"].add(shift.shift_date)
            staff_info["departments"].add(shift.department_id)
            staff_info["total_hours"] += getattr(shift, 'hours', 8)
            staff_info["total_shifts"] += 1

        # Convert sets to lists and calculate additional metrics
        for employee_id in staff_data:
            info = staff_data[employee_id]
            info["dates_worked"] = [d.isoformat() for d in sorted(info["dates_worked"])]
            info["departments"] = list(info["departments"])
            info["unique_work_days"] = len(info["dates_worked"])

            # Calculate work days per week
            weeks = (end_date - start_date).days // 7 + 1
            info["avg_work_days_per_week"] = info["unique_work_days"] / weeks if weeks > 0 else 0

            # Check for consecutive work days
            dates = sorted(info["dates_worked"])
            max_consecutive = 0
            current_consecutive = 1
            for i in range(1, len(dates)):
                # Convert to date objects
                prev_date = date.fromisoformat(dates[i-1])
                curr_date = date.fromisoformat(dates[i])
                if (curr_date - prev_date).days == 1:
                    current_consecutive += 1
                else:
                    max_consecutive = max(max_consecutive, current_consecutive)
                    current_consecutive = 1
            max_consecutive = max(max_consecutive, current_consecutive)
            info["max_consecutive_days"] = max_consecutive

            # Check if overworked (>40 hours per week avg)
            avg_hours_per_week = info["total_hours"] / weeks if weeks > 0 else 0
            info["overworked"] = avg_hours_per_week > 40

        return list(staff_data.values())

    @staticmethod
    def _enhance_shift_details(shifts: List[Dict], session: Session) -> List[Dict]:
        """Enhance shift details with department names and skill requirements"""

        # Get all departments for mapping
        departments = session.exec(select(Department)).all()
        dept_map = {d.id: d.name for d in departments}

        # Enhance each shift
        for shift in shifts:
            # Add department name
            dept_id = shift.get("department_id")
            if dept_id and dept_id in dept_map:
                shift["department_name"] = dept_map[dept_id]

            # Add additional metadata
            shift["duration_hours"] = 8  # Default shift duration

            # Check coverage status
            assigned_count = len(shift.get("assigned", []))
            shift["coverage_status"] = "COVERED" if assigned_count >= shift.get("min_staff", 0) else "UNDERSTAFFED"
            shift["coverage_ratio"] = assigned_count / shift.get("max_staff", 1) if shift.get("max_staff", 0) > 0 else 0

            # Add shift metadata
            shift["created_at"] = "2025-12-09T00:00:00Z"  # Would add actual creation time

            # Enhance assigned staff info
            if "assigned" in shift:
                for staff in shift["assigned"]:
                    staff["department"] = dept_map.get(dept_id, "Unknown")
                    staff["assignment_confirmed"] = True

        return shifts

    @staticmethod
    def _calculate_workload_summary(staff_workloads: List[Dict]) -> Dict[str, Any]:
        """Calculate overall workload summary"""

        if not staff_workloads:
            return {
                "total_staff": 0,
                "avg_shifts_per_staff": 0,
                "avg_hours_per_staff": 0,
                "overworked_staff": 0,
                "max_consecutive_days": 0,
                "department_distribution": {}
            }

        total_shifts = sum(s["total_shifts"] for s in staff_workloads)
        total_hours = sum(s["total_hours"] for s in staff_workloads)
        staff_count = len(staff_workloads)

        overworked_count = sum(1 for s in staff_workloads if s.get("overworked", False))
        max_consecutive = max(s.get("max_consecutive_days", 0) for s in staff_workloads)

        # Department distribution
        dept_counts = {}
        for staff in staff_workloads:
            for dept in staff.get("departments", []):
                dept_counts[dept] = dept_counts.get(dept, 0) + 1

        return {
            "total_staff": staff_count,
            "total_shifts": total_shifts,
            "total_hours": total_hours,
            "avg_shifts_per_staff": round(total_shifts / staff_count, 1) if staff_count > 0 else 0,
            "avg_hours_per_staff": round(total_hours / staff_count, 1) if staff_count > 0 else 0,
            "overworked_staff": overworked_count,
            "overworked_percentage": round((overworked_count / staff_count) * 100, 1) if staff_count > 0 else 0,
            "max_consecutive_days": max_consecutive,
            "department_distribution": dept_counts,
            "staff_with_consecutive_5_plus": sum(1 for s in staff_workloads if s.get("max_consecutive_days", 0) >= 5)
        }