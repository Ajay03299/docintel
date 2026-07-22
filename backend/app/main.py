from contextlib import asynccontextmanager

from fastapi import FastAPI

from fastapi.middleware.cors import CORSMiddleware
from app.api.middleware import RequestIDMiddleware
from app.api.v1.documents import router as documents_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.models.extraction import Extraction  # noqa: F401  (registers table)
from app.models.validation import Validation  # noqa: F401  (registers table)
from app.models.review import Review  # noqa: F401  (registers table)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.environment)
    # Schema is owned by Alembic (`alembic upgrade head`), not create_all:
    # create_all never ALTERs existing tables, so every column addition cost a
    # manual DROP. Two sources of schema truth is worse than either alone.
    yield


app = FastAPI(title="DocIntel", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite dev server
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestIDMiddleware)
app.include_router(documents_router, prefix="/api/v1")


@app.get("/health")
def health():
    return {"status": "ok"}
