"""API Key management endpoints."""

from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends

from app.auth.deps import get_current_user
from app.clients.litellm import LiteLLMClient, get_litellm_client
from app.db.models.custom_user import CustomUser

router = APIRouter(prefix="/api/keys", tags=["keys"])


class CreateKeyRequest(BaseModel):
    team_id: str
    key_alias: str | None = None
    models: list[str] | None = None
    max_budget: float | None = None
    budget_duration: str | None = Field(None, description="e.g. '30d', '7d', '1h'")


@router.post("")
async def create_key(
    body: CreateKeyRequest,
    user: CustomUser = Depends(get_current_user),
    litellm: LiteLLMClient = Depends(get_litellm_client),
) -> dict:
    """Create a new API key linked to the user's 사번 and team."""
    result = await litellm.generate_key(
        user_id=user.user_id,
        team_id=body.team_id,
        key_alias=body.key_alias or f"{user.user_id}-{body.team_id}",
        models=body.models,
        max_budget=body.max_budget,
        budget_duration=body.budget_duration,
    )
    return result


@router.get("")
async def list_my_keys(
    team_id: str | None = None,
    user: CustomUser = Depends(get_current_user),
    litellm: LiteLLMClient = Depends(get_litellm_client),
) -> dict:
    """List current user's API keys, optionally filtered by team."""
    key_hashes = await litellm.list_keys(user_id=user.user_id, team_id=team_id)
    # key/list now returns hashes only; fetch full info for each key
    keys = []
    for kh in key_hashes:
        if isinstance(kh, dict):
            # Ensure token field exists (normalize key_name -> token)
            if "token" not in kh and "key_name" in kh:
                kh["token"] = kh["key_name"]
            keys.append(kh)
        elif isinstance(kh, str):
            try:
                info = await litellm.get_key_info(kh)
                key_data = info.get("info", info)
                if isinstance(key_data, dict):
                    # Ensure token field exists
                    if "token" not in key_data and "key_name" in key_data:
                        key_data["token"] = key_data["key_name"]
                    elif "token" not in key_data:
                        key_data["token"] = kh
                    keys.append(key_data)
            except Exception:
                pass  # skip keys that can't be fetched
    return {"keys": keys}


@router.delete("/{key_hash}")
async def delete_key(
    key_hash: str,
    user: CustomUser = Depends(get_current_user),
    litellm: LiteLLMClient = Depends(get_litellm_client),
) -> dict:
    """Delete an API key (user can only delete their own keys)."""
    # Verify ownership
    key_info = await litellm.get_key_info(key_hash)
    info = key_info.get("info", key_info)
    if info.get("user_id") != user.user_id:
        from fastapi import HTTPException, status

        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only delete your own keys")
    return await litellm.delete_key(key_hash)
