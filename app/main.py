from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, HTTPException, status
from sqlmodel import Session, SQLModel, text
from app.infrastructure.database import engine, get_session
from app.infrastructure import models  # noqa: F401
from app.presentation.exception_handlers import register_exception_handlers
from app.presentation.payment_router import router as payment_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(engine)
    yield


app = FastAPI(title="Payment Service", lifespan=lifespan)
register_exception_handlers(app)
app.include_router(payment_router)


@app.get("/health")
def health_check():
    return {"status": "healthy"}


@app.get("/health/db", status_code=status.HTTP_200_OK)
def database_health_check(session: Session = Depends(get_session)):
    try:
        session.exec(text("SELECT 1"))
        return {"status": "healthy", "database": "connected"}
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database connection failed",
        )
