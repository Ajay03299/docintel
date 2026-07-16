from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.middleware import RequestIDMiddleware
from app.api.v1.documents import router as documents_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.session import engine
from app.models.extraction import Extraction  # noqa: F401  (registers table)
from app.models.validation import Validation  # noqa: F401  (registers table)
from app.models.document import Base


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.environment)
    Base.metadata.create_all(bind=engine)   # dev only; Alembic from Day 7
    yield


app = FastAPI(title="DocIntel", lifespan=lifespan)
app.add_middleware(RequestIDMiddleware)
app.include_router(documents_router, prefix="/api/v1")


@app.get("/health")
def health():
    return {"status": "ok"}
