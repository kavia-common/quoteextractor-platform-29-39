from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr, Field

from src.api.deps import get_current_user
from src.api.models import User

router = APIRouter(tags=["auth"])


class LoginRequest(BaseModel):
    email: EmailStr = Field(..., description="User email for sign-in.")
    password: str = Field(..., min_length=1, description="User password (ignored for MVP mock).")


class LoginResponse(BaseModel):
    access_token: str = Field(..., description="Opaque access token (mock).")
    token_type: str = Field(default="bearer", description="Token type, always 'bearer'.")
    user: User = Field(..., description="Authenticated user info.")


# PUBLIC_INTERFACE
@router.post(
    "/login",
    summary="Login (MVP mock)",
    description=(
        "Accepts email and password, returns a mock bearer token that equals the email. "
        "In production, replace with real authentication (e.g., Supabase, OAuth, etc.)."
    ),
    response_model=LoginResponse,
    responses={
        200: {"description": "Authenticated."},
        401: {"description": "Invalid credentials."},
    },
)
def login(payload: LoginRequest) -> LoginResponse:
    """
    PUBLIC_INTERFACE
    Login endpoint (mock).

    Parameters:
        payload (LoginRequest): Contains email and password (password not validated in MVP).

    Returns:
        LoginResponse: Includes a mock access_token and the user object.

    Notes:
        - For MVP, any email/password produces a token equal to the email.
        - The in-memory user store is populated on first login if needed.
    """
    # For MVP, accept any password and generate a token that equals the email.
    token = payload.email

    user = User(id=payload.email, email=payload.email, name=payload.email.split("@")[0])
    # Return without persisting here; user will be created on first use by dependency if needed.
    return LoginResponse(access_token=token, token_type="bearer", user=user)


class MeResponse(BaseModel):
    user: User = Field(..., description="Current authenticated user.")


# PUBLIC_INTERFACE
@router.get(
    "/me",
    summary="Get current user (MVP mock)",
    description="Return the currently authenticated user based on the provided bearer token.",
    response_model=MeResponse,
    responses={
        200: {"description": "Current user info."},
        401: {"description": "Missing/invalid token."},
    },
)
async def get_me(current_user: User = Depends(get_current_user)) -> MeResponse:
    """
    PUBLIC_INTERFACE
    Return the current authenticated user.

    Security:
        Requires Authorization: Bearer <token> header.

    Returns:
        MeResponse: The current user object.
    """
    return MeResponse(user=current_user)
