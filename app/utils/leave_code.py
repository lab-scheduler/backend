import random
import string
from sqlmodel import Session, select
from app.db.models import LeaveRequest


def generate_random_code(length: int = 5) -> str:
    """Generate a random 5-character string of uppercase letters + digits."""
    alphabet = string.ascii_uppercase + string.digits
    return ''.join(random.choices(alphabet, k=length))


def generate_unique_leave_code(session: Session) -> str:
    """Generate a unique leave_code that does not exist in DB."""
    while True:
        code = generate_random_code()

        exists = session.exec(
            select(LeaveRequest).where(LeaveRequest.leave_code == code)
        ).first()

        if not exists:
            return code
