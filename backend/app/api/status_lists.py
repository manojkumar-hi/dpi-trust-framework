from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database.connection import get_db
from app.models.bitstring_status_list import BitstringStatusList

router = APIRouter(tags=["status_lists"])

@router.get("/.well-known/status-lists/{list_id}", responses={
    200: {
        "content": {"application/vc+jwt": {}}
    }
})
def get_status_list(list_id: UUID, db: Session = Depends(get_db)):
    """
    Public resolution endpoint for a signed Bitstring Status List VC.
    """
    status_list = db.get(BitstringStatusList, list_id)
    if not status_list or not status_list.status_list_vc_jwt:
        raise HTTPException(status_code=404, detail="Status list not found")
        
    return Response(
        content=status_list.status_list_vc_jwt,
        media_type="application/vc+jwt",
        headers={
            "Cache-Control": "public, max-age=300"
        }
    )
