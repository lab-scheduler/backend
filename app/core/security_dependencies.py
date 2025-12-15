from fastapi import Security, HTTPBearer, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from typing import Optional, Dict, Any
from app.core.security import get_current_user

# Centralized HTTP Bearer security scheme
security = HTTPBearer(
    description="Enter your JWT token as: Bearer <your_token>"
)

# This is a simple dependency that just requires the token format
# The actual validation happens in get_current_user
bearer_security = Security(security)