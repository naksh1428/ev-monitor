from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from api.connections import router as connections_router
from api.operator import router as operators_router
from api.reference import router as reference_router
from api.stations import router as stations_router

tags_metadata = [
    {
        "name": "Stations",
        "description": "Charging stations: browsing, searching, their connectors, and pulling fresh data in from Open Charge Map.",
    },
    {
        "name": "Connections",
        "description": "Individual connectors (plugs) across all stations, and their working/not-working history.",
    },
    {
        "name": "Operators",
        "description": "Charging network operators that own stations.",
    },
    {
        "name": "Reference",
        "description": "Lookup data for building filters (towns, status types).",
    },
    {
        "name": "Health",
        "description": "Service liveness check.",
    },
]

app = FastAPI(
    title="EV Station Monitor",
    description="Tracks the Dutch EV charging network and exposes availability data over a REST API.",
    openapi_tags=tags_metadata,
)

app.include_router(stations_router)
app.include_router(connections_router)
app.include_router(operators_router)
app.include_router(reference_router)


@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url="/docs")


@app.get("/health", tags=["Health"])
async def health():
    """Check that the app is up."""
    return {"status": "ok"}
