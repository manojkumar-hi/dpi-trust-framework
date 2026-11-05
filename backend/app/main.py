import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from app import models
from app.api.agents import router as agents_router
from app.api.agent_credentials import router as agent_credentials_router
from app.api.credentials import router as credentials_router
from app.api.health import router as health_router
from app.api.identities import router as identities_router
from app.api.identity_resolution import router as identity_resolution_router
from app.api.organizations import router as organizations_router
from app.api.organization_identities import router as organization_identities_router
from app.api.organization_key_management import router as organization_key_management_router
from app.api.organization_identity_resolution import (
    router as organization_identity_resolution_router,
)
from app.api.delegations import router as delegations_router
from app.api.trust import router as trust_router
from app.api.audit import router as audit_router
from app.api.action_gateway import router as action_gateway_router
from app.api.authorization import router as authorization_router
from app.core.config import get_settings
from app.database.base import Base
from app.database.connection import engine
from app.database.migrations import apply_development_migrations
from app.middleware.correlation import CorrelationIdMiddleware

settings = get_settings()

from app.services.outbox_worker import outbox_worker

@asynccontextmanager
async def lifespan(_: FastAPI):
    apply_development_migrations()
    Base.metadata.create_all(bind=engine)
    outbox_worker.start()
    yield
    await outbox_worker.stop()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)

app.add_middleware(CorrelationIdMiddleware)

from fastapi.middleware.cors import CORSMiddleware

logger = logging.getLogger(__name__)

if settings.cors_allowed_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    if isinstance(exc, HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
            headers=getattr(exc, "headers", None),
        )
    logger.exception("Unhandled server exception: %s", exc)
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal server error: {exc}"},
    )

from app.api.did_web import router as did_web_router

from app.api.auth import router as auth_router
from app.api.status_lists import router as status_lists_router

app.include_router(health_router)
app.include_router(status_lists_router)
app.include_router(auth_router)
app.include_router(did_web_router)
app.include_router(organizations_router)
app.include_router(agents_router)
app.include_router(credentials_router)
app.include_router(agent_credentials_router)
app.include_router(identities_router)
app.include_router(identity_resolution_router)
app.include_router(organization_identities_router)
app.include_router(organization_key_management_router)
app.include_router(organization_identity_resolution_router)
app.include_router(delegations_router)
app.include_router(trust_router)
app.include_router(audit_router)
app.include_router(action_gateway_router)
app.include_router(authorization_router)
