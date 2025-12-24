# app/scheduler_engine/services/shift_generator.py
from datetime import timedelta
from sqlmodel import Session
from app.db.models import Shift, ShiftRequiredSkill, WorkPipeline, PipelineRequiredSkill

class ShiftGeneratorService:

    @staticmethod
    def generate_dept_shifts(session: Session, org_id: int, dept_rules: list, start, end):
        """
        dept_rules = [
          {
            "department_id": 1,
            "required_skill_ids": [10, 11],
            "shift_types": ["DAY", "EVENING", "NIGHT"],
            "min_staff": 2,
            "max_staff": 4,
            "priority": 3
          }
        ]
        """
        created = []

        total_days = (end - start).days + 1
        for day_i in range(total_days):
            cur = start + timedelta(days=day_i)

            for rule in dept_rules:
                # Validate required fields
                if not isinstance(rule, dict):
                    raise ValueError(f"Invalid department rule: expected dict, got {type(rule)}")
                
                if "department_id" not in rule:
                    raise ValueError(f"Missing 'department_id' in department rule: {rule}")
                
                dept_id = rule["department_id"]
                shift_types = rule.get("shift_types", ["DAY"])
                min_staff = rule.get("min_staff", 1)
                max_staff = rule.get("max_staff", 1)
                priority = rule.get("priority", 1)
                hours = rule.get("hours", 8)

                for stype in shift_types:
                    shift = Shift(
                        org_id=org_id,
                        shift_date=cur,
                        shift_type=stype,
                        department_id=dept_id,
                        min_staff=min_staff,
                        max_staff=max_staff,
                        priority=priority,
                        hours=hours
                    )
                    session.add(shift)
                    session.commit()
                    session.refresh(shift)

                    # Add required skills
                    for skill_id in rule.get("required_skill_ids", []):
                        rs = ShiftRequiredSkill(
                            shift_id=shift.id,
                            skill_id=skill_id
                        )
                        session.add(rs)
                    session.commit()

                    created.append(shift)

        return created

    @staticmethod
    def generate_pipeline_shifts(session: Session, org_id: int, pipelines: list, start, end):
        """
        pipelines = [
          {
            "name": "PCR Test",
            "department_id": 5,
            "required_skill_ids": [12],
            "estimated_staff_hours": 8,
            "recurrence_days": [0,1,2,3,4],
            "priority": 5
          }
        ]
        """
        created = []

        for pl in pipelines:
            # Create pipeline record
            pipe = WorkPipeline(
                org_id=org_id,
                name=pl["name"],
                department_id=pl["department_id"],
                start_date=start,
                end_date=end,
                estimated_staff_hours=pl.get("estimated_staff_hours", 8),
                is_recurring=True,
                recurrence_days=pl.get("recurrence_days", [0,1,2,3,4]),
                priority=pl.get("priority", 3)
            )
            session.add(pipe)
            session.commit()
            session.refresh(pipe)

            # Add skill requirements
            for skill_id in pl.get("required_skill_ids", []):
                prs = PipelineRequiredSkill(
                    pipeline_id=pipe.id,
                    skill_id=skill_id
                )
                session.add(prs)
            session.commit()

            # Generate shifts based on recurrence
            total_days = (end - start).days + 1
            for di in range(total_days):
                cur = start + timedelta(days=di)
                if cur.weekday() in pipe.recurrence_days:
                    shift = Shift(
                        org_id=org_id,
                        shift_date=cur,
                        shift_type="DAY",
                        department_id=pipe.department_id,
                        min_staff=1,
                        max_staff=1,
                        priority=pipe.priority,
                        hours=pipe.estimated_staff_hours
                    )
                    session.add(shift)
                    session.commit()
                    session.refresh(shift)

                    # add required skills from pipeline
                    for req in pipe.required_skills:
                        sr = ShiftRequiredSkill(
                            shift_id=shift.id,
                            skill_id=req.skill_id
                        )
                        session.add(sr)
                    session.commit()
                    created.append(shift)

        return created
