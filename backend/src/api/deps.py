from typing import Optional

from fastapi import Depends, Header, HTTPException, status
from pydantic import BaseModel, Field

from src.api.models import User
from src.api.store import USERS


class TokenData(BaseModel):
    """Simple token payload structure for MVP."""
    sub: str = Field(..., description="Subject (user id/email)")
    token: str = Field(..., description="Opaque token string")


def _parse_bearer_token(authorization: Optional[str]) -> Optional[str]:
    """
    Extract the token part from an Authorization header with the format 'Bearer <token>'.
    Returns None when header is missing or malformed.
    """
    if not authorization:
        return None
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[1]


# PUBLIC_INTERFACE
async def get_token_data(authorization: Optional[str] = Header(default=None)) -> TokenData:
    """
    PUBLIC_INTERFACE
    FastAPI dependency that parses the Authorization header and returns TokenData.

    Parameters:
        authorization (str | None): The Authorization header value ("Bearer <token>").

    Returns:
        TokenData: Extracted subject and token information.

    Raises:
        HTTPException: 401 Unauthorized if header is missing or invalid.
    """
    token = _parse_bearer_token(authorization)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # MVP mock: we treat token value as the user id/email and echo it back.
    # e.g., Authorization: Bearer user_1 or Bearer demo@example.com
    return TokenData(sub=token, token=token)


# PUBLIC_INTERFACE
async def get_current_user(token_data: TokenData = Depends(get_token_data)) -> User:
    """
    PUBLIC_INTERFACE
    Resolve and return the current user for a request.

    Behavior (MVP mock):
    - Uses the token subject (sub) as the user id/email.
    - If the user does not exist in the in-memory store, a placeholder user is created.

    Returns:
        User: The resolved or newly created user.
    """
    user_id = token_data.sub

    # Check existing
    existing = USERS.get(user_id)
    if existing:
        return existing

    # Create a simple user shape. If it looks like an email, use it; otherwise synthesize an email.
    email = user_id if "@" in user_id else f"{user_id}@example.com"
    display_name = user_id.split("@")[0] if "@" in user_id else user_id
    user = User(id=user_id, email=email, name=display_name)
    USERS[user_id] = user
    return user
