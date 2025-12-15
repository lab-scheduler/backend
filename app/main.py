# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Database initialization (ensures models & engine are ready)
from app.db import init  # noqa

# Routers
from app.routers.auth import router as auth_router
from app.routers.staff import router as staff_router
from app.routers.skill import router as skill_router
from app.routers.shift import router as shift_router
from app.routers.leave import router as leave_router
from app.routers.scheduler import router as scheduler_router
from app.routers.analysis import router as analysis_router
# from app.routers.demo import router as demo_router
from app.routers.shift_generator import router as shift_generator_router

# (New) Additional routers you will add
from app.routers.organization import router as organization_router
from app.routers.department import router as department_router
from app.routers.skill_staff import router as skill_staff_router


# -------------------------------------------------------------------
# API TAGS
# -------------------------------------------------------------------
tags_metadata = [
    {"name": "Auth", "description": "Authentication and authorization"},
    {"name": "Organizations", "description": "Manage hospital organizations (Admin only)"},
    {"name": "Departments", "description": "Manage lab departments (Admin only)"},
    {"name": "Skills", "description": "Manage laboratory skills"},
    {"name": "Staff", "description": "Manage lab staff records"},
    {"name": "Leaves", "description": "Submit and approve leave requests"},
    {"name": "Scheduler", "description": "Auto-scheduling and optimization"},
    {"name": "Analysis", "description": "Generate scheduling analysis reports"},
    {"name": "Staff Skills", "description": "Manage skills assigned to staff members"},
    # {"name": "Demo", "description": "Demo utilities and testing modules"},
]


# -------------------------------------------------------------------
# CREATE APP
# -------------------------------------------------------------------
def create_app() -> FastAPI:
    app = FastAPI(
        title="Hospital Lab Scheduling API",
        description=(
            "Backend API for hospital laboratory workforce management.\n\n"
            "Includes:\n"
            "- Staff & departments\n"
            "- Skill management\n"
            "- Shift scheduling\n"
            "- Auto-optimization (greedy & CP-SAT)\n"
            "- Leave management\n\n"
            "### Authentication\n"
            "Uses **JWT Bearer tokens**. Obtain via `/auth/login`.\n"
            "Then use the **Authorize** button in Swagger.\n"
        ),
        version="1.0.0",
        openapi_tags=tags_metadata,
        contact={
            "name": "Biologic Engineering",
            "url": "https://biologic.com",
            "email": "email@biologic.com",
        },
        servers=[
            {"url": "/"}
        ],
    )

    # -------------------------------------------------------------------
    # CORS SECURITY
    # -------------------------------------------------------------------
    # ⚠️ Untuk production, ganti * ke domain tertentu!
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",
            "https://lab-scheduler-ten.vercel.app",   # frontend nanti
            "https://lab-scheduler.up.railway.app"
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    # -------------------------------------------------------------------
    # ROUTER REGISTRY (CLEAN & ORGANIZED)
    # -------------------------------------------------------------------
    API_PREFIX = "/api/v1"

    # Auth (no org slug)
    app.include_router(auth_router, prefix=f"{API_PREFIX}/auth")

    # Organization level resource (Admin only)
    app.include_router(organization_router, prefix=f"{API_PREFIX}")

    # Routes that depend on org_slug
    app.include_router(staff_router, prefix=f"{API_PREFIX}")
    app.include_router(department_router, prefix=f"{API_PREFIX}")
    app.include_router(skill_router, prefix=f"{API_PREFIX}")
    app.include_router(leave_router, prefix=f"{API_PREFIX}")
    app.include_router(scheduler_router, prefix=f"{API_PREFIX}")
    app.include_router(analysis_router, prefix=f"{API_PREFIX}")
    app.include_router(skill_staff_router, prefix=f"{API_PREFIX}")
    app.include_router(shift_router, prefix=f"{API_PREFIX}")
    app.include_router(shift_generator_router, prefix=f"{API_PREFIX}")

    # Demo tools
    # app.include_router(demo_router, prefix=f"{API_PREFIX}/demo")

    # Health check / root
    @app.get("/", tags=["System"])
    def root():
        return {
            "message": "Lab Scheduler API is running",
            "version": "1.0.0",
            "docs": "/docs"
        }

    return app


# Instantiate
app = create_app()
