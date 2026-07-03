from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import agent, auth, caregiver_invites, checkins, medications, patients

app = FastAPI(title="AI Caregiver API", version="0.1.0")

# Local dev only: Expo web (localhost:8081) and the marketing site (localhost:3000)
# are cross-origin to this API. Lock this down before any non-local deployment.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8081", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1")
app.include_router(caregiver_invites.router, prefix="/api/v1")
app.include_router(patients.router, prefix="/api/v1")
app.include_router(medications.router, prefix="/api/v1")
app.include_router(checkins.router, prefix="/api/v1")
app.include_router(agent.router, prefix="/api/v1")


@app.get("/health")
def health():
    return {"status": "ok"}
