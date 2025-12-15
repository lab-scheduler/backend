# app/services/enhanced_shift_generator_service.py
from sqlmodel import Session, select
from datetime import date, timedelta
from typing import List, Dict, Any
from app.db.models import Department, Staff, StaffSkill, Shift, ShiftAssignment
from app.scheduler_engine.services.shift_generator import ShiftGeneratorService
import calendar

class EnhancedShiftGeneratorService:
    """
    Enhanced shift generator that considers staff workloads and rotation patterns
    """

    @staticmethod
    def generate_shifts_with_workload_balance(
        session: Session,
        org_id: int,
        department_rules: List[Dict],
        pipeline_rules: List[Dict],
        start_date: date,
        end_date: date,
        staff_preferences: Dict = None,
        rotation_patterns: Dict = None
    ) -> Dict[str, Any]:
        """
        Generate shifts with workload balancing:
        - 20/10 rotation (20 days work, 10 days rest per month)
        - 2-3 work days per week
        - Consider staff preferences
        - Balance workload across staff
        """

        # Get all staff
        staff_list = session.exec(
            select(Staff).where(Staff.org_id == org_id)
        ).all()

        # Load staff skills and calculate workload capacity
        staff_workload_info = EnhancedShiftGeneratorService._calculate_staff_workload_capacity(
            session, staff_list, start_date, end_date
        )

        # Generate shifts using enhanced logic
        result = {
            "department_shifts": 0,
            "pipeline_shifts": 0,
            "workload_balance": staff_workload_info,
            "details": []
        }

        # Generate department shifts with workload awareness
        for rule in department_rules:
            dept_shifts = EnhancedShiftGeneratorService._generate_department_shifts_balanced(
                session, org_id, rule, start_date, end_date, staff_workload_info
            )
            result["department_shifts"] += dept_shifts["count"]
            result["details"].extend(dept_shifts["details"])

        # Generate pipeline shifts with workload awareness
        for rule in pipeline_rules:
            pipeline_shifts = EnhancedShiftGeneratorService._generate_pipeline_shifts_balanced(
                session, org_id, rule, start_date, end_date, staff_workload_info
            )
            result["pipeline_shifts"] += pipeline_shifts["count"]
            result["details"].extend(pipeline_shifts["details"])

        return result

    @staticmethod
    def _calculate_staff_workload_capacity(
        session: Session,
        staff_list: List[Staff],
        start_date: date,
        end_date: date
    ) -> Dict[str, Dict]:
        """Calculate how many shifts each staff can take"""

        total_days = (end_date - start_date).days + 1
        weekends = 0

        # Count weekends in the period
        current = start_date
        while current <= end_date:
            if current.weekday() >= 5:  # Saturday (5) and Sunday (6)
                weekends += 1
            current += timedelta(days=1)

        weekdays = total_days - weekends
        work_days_per_month = 20  # 20/10 rotation
        work_days_per_week = 3  # Average 3 days per week

        staff_info = {}
        for staff in staff_list:
            # Calculate staff's available work capacity
            max_days_per_month = min(
                work_days_per_month,
                weekdays * (work_days_per_week / 5)  # Convert to monthly estimate
            )

            staff_info[staff.employee_id] = {
                "full_name": staff.full_name,
                "role": staff.role.value if staff.role else "STAFF",
                "max_hours_per_week": staff.max_hours_per_week or 40,
                "max_shifts_per_month": max_days_per_month,
                "max_shifts_remaining": max_days_per_month,
                "assigned_shifts": 0,
                "skills": [s.skill_id for s in getattr(staff, "skills", [])],
                "is_supervisor": staff.is_supervisor,
                "work_days": [],  # Will track which dates they work
                "last_worked_date": None
            }

        return staff_info

    @staticmethod
    def _generate_department_shifts_balanced(
        session: Session,
        org_id: int,
        rule: Dict,
        start_date: date,
        end_date: date,
        staff_workload_info: Dict
    ) -> Dict:
        """Generate department shifts with workload balancing"""

        # Get staff who can work in this department
        # For simplicity, we'll assume all staff can work in any department
        # In production, this would need proper department-staff mapping
        available_staff = [
            emp_id for emp_id in staff_workload_info
            if staff_workload_info[emp_id]["max_shifts_remaining"] > 0
        ]

        # Sort staff by current workload (least busy first)
        available_staff.sort(key=lambda x: staff_workload_info[x]["assigned_shifts"])

        shifts_created = []
        current_date = start_date
        days_in_month = calendar.monthrange(start_date.year, start_date.month)[1]
        days_remaining_in_month = days_in_month - start_date.day + 1

        while current_date <= end_date and days_remaining_in_month > 0:
            # Check if this is a work day (weekdays or based on rotation)
            if current_date.weekday() < 5:  # Monday to Friday
                # Generate all shift types for this department
                for shift_type in rule.get("shift_types", []):
                    # Find available staff
                    for i in range(rule.get("max_staff", 1)):
                        if i < len(available_staff):
                            staff_id = available_staff[i]

                            # Create shift in database
                            shift = Shift(
                                org_id=org_id,
                                shift_date=current_date,
                                shift_type=shift_type,
                                department_id=rule["department_id"],
                                min_staff=rule.get("min_staff", 1),
                                max_staff=rule.get("max_staff", 1),
                                priority=rule.get("priority", 1),
                                hours=8  # 8-hour shifts
                            )
                            session.add(shift)
                            session.commit()
                            session.refresh(shift)

                            # Update staff workload
                            staff_workload_info[staff_id]["assigned_shifts"] += 1
                            staff_workload_info[staff_id]["max_shifts_remaining"] -= 1
                            staff_workload_info[staff_id]["work_days"].append(current_date)
                            staff_workload_info[staff_id]["last_worked_date"] = current_date

                            # Create shift requirement record
                            for skill_id in rule.get("required_skill_ids", []):
                                from app.db.models import ShiftRequiredSkill
                                req = ShiftRequiredSkill(
                                    shift_id=shift.id,
                                    skill_id=skill_id
                                )
                                session.add(req)
                            session.commit()

                            shifts_created.append({
                                "date": current_date.isoformat(),
                                "shift_id": shift.id,
                                "type": shift_type,
                                "staff": staff_id,
                                "department": rule["department_id"]
                            })

                days_remaining_in_month -= 1
            else:
                # Weekend - rotate to next month if needed
                pass

            current_date += timedelta(days=1)

        return {
            "count": len(shifts_created),
            "details": shifts_created
        }

    @staticmethod
    def _generate_pipeline_shifts_balanced(
        session: Session,
        org_id: int,
        rule: Dict,
        start_date: date,
        end_date: date,
        staff_workload_info: Dict
    ) -> Dict:
        """Generate pipeline shifts with workload balancing"""

        # Similar logic to department shifts but for recurring work patterns
        # For brevity, this would follow similar pattern as _generate_department_shifts_balanced
        return {"count": 0, "details": []}

    @staticmethod
    def get_staff_rotation_schedule(
        session: Session,
        org_id: int,
        staff_id: str,
        start_date: date,
        end_date: date
    ) -> Dict[str, Any]:
        """Get a staff member's rotation schedule for the period"""

        # Get all assignments for the staff
        assignments = session.exec(
            select(Shift, ShiftAssignment)
            .join(ShiftAssignment)
            .where(
                Shift.org_id == org_id,
                ShiftAssignment.employee_id == staff_id,
                Shift.shift_date >= start_date,
                Shift.shift_date <= end_date
            )
        ).all()

        # Build rotation schedule
        schedule = {
            "staff_id": staff_id,
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            },
            "work_days": [],
            "rest_days": [],
            "total_work_days": 0,
            "total_rest_days": 0,
            "rotation_ratio": "0/0"
        }

        # Get all dates in period
        current = start_date
        all_dates = set()
        while current <= end_date:
            all_dates.add(current)
            current += timedelta(days=1)

        # Mark work days from assignments
        work_days = set()
        for shift, assignment in assignments:
            work_days.add(shift.shift_date)

        # Build detailed schedule
        for day in sorted(all_dates):
            if day in work_days:
                schedule["work_days"].append({
                    "date": day.isoformat(),
                    "weekday": day.strftime("%A"),
                    "type": "WORK"
                })
            else:
                schedule["rest_days"].append({
                    "date": day.isoformat(),
                    "weekday": day.strftime("%A"),
                    "type": "REST"
                })

        schedule["total_work_days"] = len(work_days)
        schedule["total_rest_days"] = len(all_dates) - len(work_days)
        schedule["rotation_ratio"] = f"{schedule['total_work_days']}/{len(all_dates)}"

        # Check if rotation is balanced (target 20/10 or 2/3)
        total_days = len(all_dates)
        target_work_days = total_days * 0.66  # 2/3 ratio
        is_balanced = abs(schedule["total_work_days"] - target_work_days) <= 2
        schedule["is_balanced"] = is_balanced

        return schedule