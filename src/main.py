from fastapi import FastAPI

from api.browse import router as browse_router
from api.connections import router as connections_router
from api.operator import router as operators_router
from api.station_status import router as station_status_router
from api.stations import router as stations_router

app = FastAPI(title="EV Station Monitor")

app.include_router(operators_router)
app.include_router(stations_router)
app.include_router(station_status_router)
app.include_router(connections_router)
app.include_router(browse_router)

@app.get("/health", tags=["health"])
async def health():
    """Liveness: is the app process up and responding?"""
    return {"status": "ok"}
