from fastapi import APIRouter, Depends, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import Session
from app.db.session import get_session
from app.services.auth_service import AuthService
from app.schemas import AuthRegister, LoginRequest, TokenResponse
from app.core.security import get_current_user

router = APIRouter(prefix="/auth", tags=["Auth"])
security = HTTPBearer()


# REGISTER → ADMIN ONLY
@router.post("/register", dependencies=[Security(security)])
def register_user(
    payload: AuthRegister,
    session: Session = Depends(get_session),
    current=Depends(get_current_user)
):

    if not current or current.get("role") != "ADMIN":
        raise HTTPException(403, "Only ADMIN may register new users")

    try:
        user = AuthService.register(session, payload)
    except ValueError as e:
        raise HTTPException(400, str(e))

    return {
        "id": str(user.id),
        "username": user.username,
        "email": user.email,
        "employee_id": user.employee_id,
        "role": user.role,
    }


# LOGIN → returns JWT + expiry
@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, session: Session = Depends(get_session)):
    result = AuthService.authenticate(session, req.identifier, req.password)

    if not result:
        raise HTTPException(401, "Invalid credentials")

    return {
        "access_token": result["access_token"],
        "token_type": "bearer",
        "expires_in": result["expires_in"],
    }
