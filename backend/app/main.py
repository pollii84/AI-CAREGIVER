from fastapi import FastAPI

from app.api.v1 import agent, auth, caregiver_invites, checkins, medications, patients

app = FastAPI(title="AI Caregiver API", version="0.1.0")

app.include_router(auth.router, prefix="/api/v1")
app.include_router(caregiver_invites.router, prefix="/api/v1")
app.include_router(patients.router, prefix="/api/v1")
app.include_router(medications.router, prefix="/api/v1")
app.include_router(checkins.router, prefix="/api/v1")
app.include_router(agent.router, prefix="/api/v1")


@app.get("/health")
def health():
    return {"status": "ok"}
