from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.authorization_dependency import evaluate_authorization, resolve_policy_target
from app.api.dependencies import Principal, get_current_principal
from app.database.connection import get_db
from app.schemas.authorization import AuthorizationPreCheckRequest, AuthorizationPreCheckResponse

router = APIRouter(prefix="/authorization", tags=["Pre-Authorization"])


@router.post("/pre-check", response_model=AuthorizationPreCheckResponse)
async def pre_check_authorization(
    request: AuthorizationPreCheckRequest,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> AuthorizationPreCheckResponse:
    resource_type, action_name = resolve_policy_target(request.action_type)
    decision = await evaluate_authorization(
        resource_type,
        action_name,
        db,
        principal,
        request.agent_id,
        request.delegation_id,
        event_type="pre_authorization_checked",
    )
    return AuthorizationPreCheckResponse(
        **decision.model_dump(),
        agent_id=request.agent_id,
        action_type=request.action_type,
        resource_type=resource_type,
    )
