# app/routers/analysis_routes.py
from fastapi import APIRouter, Depends, HTTPException, Security, Query
from fastapi.security import HTTPBearer
from fastapi.responses import JSONResponse
from sqlmodel import Session
from datetime import date
from app.db.session import get_session
from app.core.security import get_current_user
from app.utils.organization_lookup import get_org_by_slug
from app.services.analysis_service import AnalysisService
from app.services.enhanced_analysis_service import EnhancedAnalysisService

router = APIRouter(prefix="/{org_slug}/analysis", tags=["Analysis"])
security = HTTPBearer()


def parse_dates(start: str, end: str):
    try:
        return date.fromisoformat(start), date.fromisoformat(end)
    except:
        raise HTTPException(400, "Invalid date format. Use YYYY-MM-DD")


# ---------------------------------------------------------
# GENERAL RANGE ANALYSIS
# ---------------------------------------------------------
@router.get("/range", dependencies=[Security(security)])
def analysis_range(org_slug: str, start: str, end: str,
                   detailed: bool = Query(False, description="Return comprehensive detailed analysis"),
                   session: Session = Depends(get_session),
                   current: dict = Depends(get_current_user)):

    org = get_org_by_slug(org_slug, session)
    s, e = parse_dates(start, end)

    if detailed:
        # Return enhanced comprehensive analysis
        result = EnhancedAnalysisService.get_comprehensive_analysis(session, org.id, s, e)
        return {"ok": True, "data": result}
    else:
        # Return basic analysis for backward compatibility
        result = AnalysisService.analyze_range(session, org.id, s, e)
        return {"ok": True, "data": result}


# # ---------------------------------------------------------
# # COMPREHENSIVE RANGE ANALYSIS (NEW)
# # ---------------------------------------------------------
# @router.get("/range/comprehensive", dependencies=[Security(security)])
# def analysis_range_comprehensive(org_slug: str, start: str, end: str,
#                                 session: Session = Depends(get_session),
#                                 current: dict = Depends(get_current_user)):
#     """
#     Comprehensive analysis endpoint that returns full details including:
#     - Executive summary with key metrics
#     - Detailed department breakdowns
#     - Complete staff analysis
#     - Full shift details with assignments
#     - Advanced analytics and insights
#     - Actionable recommendations
#     """
#     org = get_org_by_slug(org_slug, session)
#     s, e = parse_dates(start, end)

#     result = EnhancedAnalysisService.get_comprehensive_analysis(session, org.id, s, e)
#     return {"ok": True, "data": result}


# ---------------------------------------------------------
# ANALYSIS PER STAFF
# ---------------------------------------------------------
@router.get("/staff/{staff_id}", dependencies=[Security(security)])
def analysis_staff(org_slug: str, staff_id: str, start: str, end: str,
                   session: Session = Depends(get_session),
                   current: dict = Depends(get_current_user)):

    org = get_org_by_slug(org_slug, session)
    s, e = parse_dates(start, end)

    result = AnalysisService.analyze_for_staff(session, org.id, staff_id, s, e)
    return {"ok": True, "data": result}


# ---------------------------------------------------------
# ANALYSIS PER DEPARTMENT
# ---------------------------------------------------------
@router.get("/department/{dept_id}", dependencies=[Security(security)])
def analysis_dept(org_slug: str, dept_id: int, start: str, end: str,
                  session: Session = Depends(get_session),
                  current: dict = Depends(get_current_user)):

    org = get_org_by_slug(org_slug, session)
    s, e = parse_dates(start, end)

    result = AnalysisService.analyze_for_department(session, org.id, dept_id, s, e)
    return {"ok": True, "data": result}


# ---------------------------------------------------------
# EXPORT ANALYSIS TO JSON
# ---------------------------------------------------------
@router.get("/export", dependencies=[Security(security)])
def export_analysis(org_slug: str, start: str, end: str,
                    session: Session = Depends(get_session),
                    current: dict = Depends(get_current_user)):

    org = get_org_by_slug(org_slug, session)
    s, e = parse_dates(start, end)

    result = AnalysisService.analyze_range(session, org.id, s, e)

    # Return JSON file download
    return JSONResponse(
        content=result,
        headers={
            "Content-Disposition": f"attachment; filename=analysis_{org_slug}_{start}_{end}.json"
        }
    )
