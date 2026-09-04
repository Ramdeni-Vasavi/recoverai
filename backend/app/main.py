from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.health import router as health_router
from app.api.v1.payments import router as payments_router
from app.api.v1.predictions import router as predictions_router
from app.api.v1.decisions import router as decisions_router
from app.api.v1.optimization import router as optimization_router
from app.api.v1.execution import router as execution_router
from app.api.v1.dashboard import router as dashboard_router
from app.core.config import get_settings
from app.core.database import init_db
from app.integrations.razorpay.webhook import router as razorpay_webhook_router

settings = get_settings()

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root() -> dict[str, str]:
    return {"service": settings.app_name, "status": "running"}


app.include_router(health_router, prefix=settings.api_v1_prefix)
app.include_router(payments_router, prefix=settings.api_v1_prefix)
app.include_router(predictions_router, prefix=settings.api_v1_prefix)
app.include_router(decisions_router, prefix=settings.api_v1_prefix)
app.include_router(optimization_router, prefix=settings.api_v1_prefix)
app.include_router(execution_router, prefix=settings.api_v1_prefix)
app.include_router(dashboard_router, prefix=settings.api_v1_prefix)


@app.on_event("startup")
def initialize_database() -> None:
    init_db()
app.include_router(razorpay_webhook_router, prefix=settings.api_v1_prefix)
