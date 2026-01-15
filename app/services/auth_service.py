from sqlmodel import Session, select
from app.db.models import AuthUser, Staff
from app.schemas import AuthRegister, LoginRequest
from app.core.security import hash_password, verify_password, create_access_token
from datetime import datetime
from uuid import uuid4


class AuthService:

    @staticmethod
    def register(session: Session, payload: AuthRegister):
        # Check duplicates
        if payload.username:
            exists = session.exec(
                select(AuthUser).where(AuthUser.username == payload.username)
            ).first()
            if exists:
                raise ValueError("Username already exists")

        if payload.email:
            exists = session.exec(
                select(AuthUser).where(AuthUser.email == payload.email)
            ).first()
            if exists:
                raise ValueError("Email already exists")

        # Validate employee_id based on role
        if payload.role in ["STAFF", "MANAGER"]:
            # STAFF and MANAGER must have a valid employee_id in staff table
            if not payload.employee_id:
                raise ValueError(f"{payload.role} users must have an employee_id")
            
            # Verify employee_id exists in staff table
            staff = session.exec(
                select(Staff).where(Staff.employee_id == payload.employee_id)
            ).first()
            
            if not staff:
                raise ValueError(f"Employee ID '{payload.employee_id}' not found in staff table. Please create staff record first.")
        
        # ADMIN users don't need employee_id validation

        user = AuthUser(
            id=uuid4(),
            employee_id=payload.employee_id,
            username=payload.username,
            email=payload.email,
            password_hash=hash_password(payload.password),
            role=payload.role.value,   # role enum dari schemas
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )

        session.add(user)
        session.commit()
        session.refresh(user)
        return user

    @staticmethod
    def authenticate(session: Session, identifier: str, password: str):
        # identifier bisa berupa username OR email OR employee_id
        stmt = select(AuthUser).where(
            (AuthUser.username == identifier) |
            (AuthUser.email == identifier) |
            (AuthUser.employee_id == identifier)
        )
        user = session.exec(stmt).first()

        if not user:
            return None

        if not verify_password(password, user.password_hash):
            return None

        # Build token payload
        payload = {
            "role": user.role
        }

        # If account linked to staff, embed org & employee_id in token
        if user.employee_id:
            staff = session.exec(
                select(Staff).where(Staff.employee_id == user.employee_id)
            ).first()

            if staff:
                payload["employee_id"] = staff.employee_id
                payload["org_id"] = staff.org_id

        access_token, expires_in = create_access_token(payload)

        return {
            "user": user,
            "access_token": access_token,
            "expires_in": expires_in,
        }
