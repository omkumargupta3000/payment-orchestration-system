from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError

from app.database import Base, engine, SessionLocal
from app.models.psp import PSP
from app.routes import payments, psps, analytics

# create tables if they don't already exist
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Payment Orchestration & Transaction Routing System",
    description=(
        "A student-built simulation of a payment orchestration layer. "
        "No real payment gateways are involved - PSPs are simulated."
    ),
    version="1.0.0",
)


def seed_psps():
    """Insert the default PSPs on first run if the table is empty."""
    db = SessionLocal()
    try:
        if db.query(PSP).count() == 0:
            default_psps = [
                PSP(name="PSP Alpha", success_rate=0.92, avg_latency_ms=450, is_active=True),
                PSP(name="PSP Beta", success_rate=0.86, avg_latency_ms=250, is_active=True),
                PSP(name="PSP Gamma", success_rate=0.95, avg_latency_ms=600, is_active=True),
            ]
            db.add_all(default_psps)
            db.commit()
    finally:
        db.close()


seed_psps()

# --- routes ------------------------------------------------------------------
app.include_router(payments.router)
app.include_router(psps.router)
app.include_router(analytics.router)


# --- error handling ------------------------------------------------------------
# Don't leak stack traces to clients - return clean, understandable error responses.

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # pydantic gives a fairly verbose error list, just surface the messages
    errors = [err["msg"] for err in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": errors})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    # last-resort catch-all so a bug never returns a raw traceback to the client
    return JSONResponse(
        status_code=500,
        content={"detail": "Something went wrong while processing the request."},
    )


# --- static frontend -----------------------------------------------------------
# Serve the dashboard directly from FastAPI so the whole project is one
# deployable unit / one public URL.

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
def serve_dashboard():
    return FileResponse("static/index.html")


@app.get("/health")
def health_check():
    return {"status": "ok"}
