from contextlib import asynccontextmanager

from fastapi import FastAPI

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

from app.api.did_web import router as did_web_router

app.include_router(health_router)
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
