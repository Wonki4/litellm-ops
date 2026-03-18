"""User session/profile endpoints."""

from fastapi import APIRouter, Depends

from app.auth.deps import get_current_user
from app.clients.litellm import LiteLLMClient, get_litellm_client
from app.db.models.custom_user import CustomUser

router = APIRouter(prefix="/api/me", tags=["me"])


@router.get("")
async def get_me(
    user: CustomUser = Depends(get_current_user),
    litellm: LiteLLMClient = Depends(get_litellm_client),
) -> dict:
    """Get current user profile including LiteLLM data."""
    # Try to get LiteLLM user info; auto-provision if missing
    try:
        litellm_info = await litellm.get_user_info(user.user_id)
    except Exception:
        # User doesn't exist in LiteLLM yet - create them
        await litellm.create_user(user.user_id, user.email)
        litellm_info = await litellm.get_user_info(user.user_id)

    user_data = litellm_info.get("user_info", {})
    teams = litellm_info.get("teams", [])

    return {
        "user_id": user.user_id,
        "email": user.email,
        "display_name": user.display_name,
        "role": user.global_role.value,
        "teams": teams,
        "spend": user_data.get("spend", 0),
        "max_budget": user_data.get("max_budget"),
    }
