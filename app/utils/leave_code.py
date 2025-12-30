import random
import string
import logging
from sqlmodel import Session, select
from app.db.models import LeaveRequest

logger = logging.getLogger(__name__)

# Maximum number of attempts to generate a unique code
MAX_RETRIES = 100


def generate_random_code(length: int = 5) -> str:
    """Generate a random 5-character string of uppercase letters + digits."""
    alphabet = string.ascii_uppercase + string.digits
    return ''.join(random.choices(alphabet, k=length))


def generate_unique_leave_code(session: Session) -> str:
    """
    Generate a unique leave_code that does not exist in DB.
    
    Args:
        session: Database session
        
    Returns:
        str: Unique leave code
        
    Raises:
        ValueError: If unable to generate unique code after MAX_RETRIES attempts
    """
    for attempt in range(MAX_RETRIES):
        code = generate_random_code()

        exists = session.exec(
            select(LeaveRequest).where(LeaveRequest.leave_code == code)
        ).first()

        if not exists:
            if attempt > 10:
                logger.warning(f"Generated unique leave code after {attempt + 1} attempts")
            return code
    
    # If we reach here, we've exhausted all retries
    logger.error(f"Failed to generate unique leave code after {MAX_RETRIES} attempts")
    raise ValueError(
        f"Unable to generate unique leave code after {MAX_RETRIES} attempts. "
        "Database may be approaching capacity for leave codes."
    )
