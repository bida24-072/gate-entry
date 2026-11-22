from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .routers import access, auth, enrollment, health, monitoring, registration, visitors

app = FastAPI(title="Campus Gate Entry System")

origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
    allow_credentials=False,  # we use a bearer header, never cookies
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(enrollment.router)
app.include_router(access.router)
app.include_router(registration.router)
app.include_router(visitors.router)
app.include_router(monitoring.router)
