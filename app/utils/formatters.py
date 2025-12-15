# app/utils/formatters.py
from typing import Dict, Any, List
from collections import defaultdict
from datetime import date

def _str_id(x):
    try:
        return str(x)
    except Exception:
        return x

def build_shift_objects(state: Dict[str, Any]):
    """
    Convert internal shifts dict + assignments list into UI-friendly shift list:
    [
      {
        "id": "<shift_id>",
        "date": "YYYY-MM-DD",
        "shift_type": "DAY",
        "department": "Hematology",
        "staff": [{"id":"...","name":"..."}, ...],
        "assigned": 2,
        "min_staff": 1,
        "max_staff": 3
      }, ...
    ]
    """
    shifts_out = []
    # prepare staff map if available
    staff_map = state.get("staff_map") or state.get("staff", {})
    # assignments -> group by shift_id
    assignments = state.get("assignments", [])
    ass_by_shift = defaultdict(list)
    for a in assignments:
        ass_by_shift[a["shift_id"]].append(a["employee_id"])

    for sid, s in state.get("shifts", {}).items():
        employee_ids = ass_by_shift.get(sid, [])
        staff_objs = []
        for emp_id in employee_ids:
            entry = {"id": _str_id(emp_id)}
            # try to get name from staff_map (which might map id->obj)
            if isinstance(staff_map, dict):
                sm = staff_map.get(_str_id(emp_id)) or staff_map.get(emp_id)
                if sm and isinstance(sm, dict) and sm.get("name"):
                    entry["name"] = sm.get("name")
                else:
                    entry["name"] = sm.get("name") if getattr(sm, "name", None) else str(emp_id)
            else:
                entry["name"] = str(emp_id)
            staff_objs.append(entry)

        shifts_out.append({
            "id": _str_id(sid),
            "date": s.get("date"),
            "shift_type": s.get("shift_type"),
            "department": s.get("department"),
            "assigned": len(staff_objs),
            "staff": staff_objs,
            "min_staff": s.get("min_staff"),
            "max_staff": s.get("max_staff"),
            "requires_supervisor": s.get("requires_supervisor", False),
            "hours": s.get("hours"),
        })
    # sort by date
    shifts_out.sort(key=lambda x: x.get("date") or "")
    return shifts_out

def build_calendar_days(shifts_out: List[Dict[str, Any]]):
    """
    Convert flat shifts list into days array:
    [
      {"date":"YYYY-MM-DD", "shifts":[...], "status": "ok"/"warning"/"critical" }
    ]
    """
    days = defaultdict(list)
    for s in shifts_out:
        days[s["date"]].append(s)

    days_list = []
    for d in sorted(days.keys()):
        day_shifts = days[d]
        # compute day status from shifts: if any shift critical -> critical; elif any warning -> warning else ok
        day_status = "ok"
        for sh in day_shifts:
            if sh["assigned"] < (sh.get("min_staff") or 1):
                day_status = "critical"
                break
        days_list.append({
            "date": d,
            "shifts": day_shifts,
            "status": day_status
        })
    return days_list

def build_cards(report: Dict[str, Any]):
    """
    Convert analyzer report to card-friendly metrics (summary).
    Return dict keyed by metric short name.
    """
    metrics = report.get("metrics", {})
    out = {
        "system_health": {
            "score": report.get("overall_score", 0),
            "grade": report.get("grade", "N/A"),
            "recommendations": report.get("recommendations", [])
        },
        "coverage": {
            "value": metrics.get("coverage_adequacy", {}).get("value"),
            "target": metrics.get("coverage_adequacy", {}).get("target"),
        },
        "utilization": {
            "value": metrics.get("staff_utilization", {}).get("value"),
            "per_staff": metrics.get("staff_utilization", {}).get("per_staff")
        },
        "conflicts": metrics.get("conflicts", {})
    }
    return out

def ui_payload_from_state(state: Dict[str, Any], report: Dict[str, Any]):
    """
    Top-level builder; returns:
    {
      "shifts": [...],
      "calendar": {"days": [...]},
      "analysis": { ...cards and metrics... }
    }
    """
    shifts_out = build_shift_objects(state)
    days = build_calendar_days(shifts_out)
    cards = build_cards(report)
    return {
        "shifts": shifts_out,
        "calendar": {"days": days},
        "analysis": cards,
        "raw_report": report
    }
