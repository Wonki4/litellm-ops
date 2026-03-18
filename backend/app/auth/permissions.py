"""Authorization helpers for team-level and global permissions."""

from fastapi import HTTPException, status

from app.clients.litellm import LiteLLMClient
from app.db.models.custom_user import CustomUser, GlobalRole


async def require_team_admin(user: CustomUser, team_id: str, litellm: LiteLLMClient) -> None:
    """Verify the user is an admin of the specified team or a super user."""
    if user.global_role == GlobalRole.SUPER_USER:
        return

    team_info = await litellm.get_team_info(team_id)
    admins = team_info.get("team_info", {}).get("admins", [])
    if user.user_id not in admins:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You are not an admin of team {team_id}",
        )
