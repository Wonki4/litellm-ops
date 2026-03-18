"""Team join request workflow endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.auth.permissions import require_team_admin
from app.clients.litellm import LiteLLMClient, get_litellm_client
from app.clients.slack import send_slack_notification
from app.db.models.custom_team_join_request import CustomTeamJoinRequest, JoinRequestStatus
from app.db.models.custom_user import CustomUser
from app.db.session import get_db

router = APIRouter(prefix="/api/team-requests", tags=["team-requests"])


class CreateJoinRequest(BaseModel):
    team_id: str
    message: str | None = None


class ReviewRequest(BaseModel):
    comment: str | None = None


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_join_request(
    body: CreateJoinRequest,
    user: CustomUser = Depends(get_current_user),
    litellm: LiteLLMClient = Depends(get_litellm_client),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Request to join a team. Prevents duplicate pending requests."""
    # Check if user already has a pending request for this team
    existing = await db.execute(
        select(CustomTeamJoinRequest).where(
            CustomTeamJoinRequest.requester_id == user.user_id,
            CustomTeamJoinRequest.team_id == body.team_id,
            CustomTeamJoinRequest.status == JoinRequestStatus.PENDING,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="You already have a pending request for this team"
        )

    # Check if user is already a member
    try:
        team_info = await litellm.get_team_info(body.team_id)
        team_data = team_info.get("team_info", {})
        members = team_data.get("members", [])
        if user.user_id in members:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="You are already a member of this team")
        team_alias = team_data.get("team_alias", body.team_id)
    except HTTPException:
        raise
    except Exception:
        team_alias = body.team_id

    # Create the request
    join_request = CustomTeamJoinRequest(
        id=uuid.uuid4(),
        requester_id=user.user_id,
        team_id=body.team_id,
        team_alias=team_alias,
        message=body.message,
        status=JoinRequestStatus.PENDING,
    )
    db.add(join_request)
    await db.flush()

    # Send Slack notification (fire-and-forget)
    await send_slack_notification(
        requester_id=user.user_id,
        team_alias=team_alias,
        team_id=body.team_id,
        message=body.message,
    )

    return {
        "id": str(join_request.id),
        "status": join_request.status.value,
        "team_id": join_request.team_id,
        "team_alias": join_request.team_alias,
    }


@router.get("")
async def list_join_requests(
    team_id: str | None = None,
    status_filter: str | None = None,
    user: CustomUser = Depends(get_current_user),
    litellm: LiteLLMClient = Depends(get_litellm_client),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List join requests. Regular users see their own; admins see team requests."""
    from app.db.models.custom_user import GlobalRole

    query = select(CustomTeamJoinRequest).order_by(CustomTeamJoinRequest.created_at.desc())

    if user.global_role == GlobalRole.SUPER_USER:
        # Super users see all requests
        if team_id:
            query = query.where(CustomTeamJoinRequest.team_id == team_id)
    else:
        # For regular users/team admins
        if team_id:
            # Verify they're admin of the team
            await require_team_admin(user, team_id, litellm)
            query = query.where(CustomTeamJoinRequest.team_id == team_id)
        else:
            # Show user's own requests
            query = query.where(CustomTeamJoinRequest.requester_id == user.user_id)

    if status_filter:
        query = query.where(CustomTeamJoinRequest.status == JoinRequestStatus(status_filter))

    result = await db.execute(query)
    requests = result.scalars().all()

    return {
        "requests": [
            {
                "id": str(r.id),
                "requester_id": r.requester_id,
                "team_id": r.team_id,
                "team_alias": r.team_alias,
                "message": r.message,
                "status": r.status.value,
                "reviewed_by": r.reviewed_by,
                "review_comment": r.review_comment,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "updated_at": r.updated_at.isoformat() if r.updated_at else None,
            }
            for r in requests
        ]
    }


@router.post("/{request_id}/approve")
async def approve_request(
    request_id: str,
    body: ReviewRequest = ReviewRequest(),
    user: CustomUser = Depends(get_current_user),
    litellm: LiteLLMClient = Depends(get_litellm_client),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Approve a team join request. Must be team admin or super user."""
    result = await db.execute(select(CustomTeamJoinRequest).where(CustomTeamJoinRequest.id == uuid.UUID(request_id)))
    join_request = result.scalar_one_or_none()
    if not join_request:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    if join_request.status != JoinRequestStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Request already {join_request.status.value}"
        )

    # Verify admin permission
    await require_team_admin(user, join_request.team_id, litellm)

    # Add member to team in LiteLLM
    await litellm.add_team_member(join_request.team_id, join_request.requester_id)

    # Update request status
    join_request.status = JoinRequestStatus.APPROVED
    join_request.reviewed_by = user.user_id
    join_request.review_comment = body.comment
    await db.flush()

    return {"status": "approved", "team_id": join_request.team_id, "requester_id": join_request.requester_id}


@router.post("/{request_id}/reject")
async def reject_request(
    request_id: str,
    body: ReviewRequest = ReviewRequest(),
    user: CustomUser = Depends(get_current_user),
    litellm: LiteLLMClient = Depends(get_litellm_client),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Reject a team join request. Must be team admin or super user."""
    result = await db.execute(select(CustomTeamJoinRequest).where(CustomTeamJoinRequest.id == uuid.UUID(request_id)))
    join_request = result.scalar_one_or_none()
    if not join_request:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    if join_request.status != JoinRequestStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Request already {join_request.status.value}"
        )

    await require_team_admin(user, join_request.team_id, litellm)

    join_request.status = JoinRequestStatus.REJECTED
    join_request.reviewed_by = user.user_id
    join_request.review_comment = body.comment
    await db.flush()

    return {"status": "rejected", "team_id": join_request.team_id, "requester_id": join_request.requester_id}
