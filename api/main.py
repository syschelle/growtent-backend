from fastapi import FastAPI

import app as legacy
from routes.auth import router as auth_router
from routes.tents import router as tents_router
from routes.sensors import router as sensors_router
from routes.system import router as system_router

app = FastAPI(title="GrowTent Backend PoC")

# Keep legacy middleware behavior.
app.middleware("http")(legacy.auth_middleware)

# Keep legacy startup behavior (DB init + poller thread).
@app.on_event("startup")
def startup_event():
    legacy.startup_event()

app.include_router(auth_router)
app.include_router(tents_router)
app.include_router(sensors_router)
app.include_router(system_router)
