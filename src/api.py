import json
import os
import httpx
from config import settings

BASE = "https://api.openchargemap.io/v3/poi"
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def fetch_stations(max_results: int = 5, offset: int = 0) -> list[dict]:
    resp = httpx.get(
        BASE,
        params={
            "key": settings.OCM_API_KEY,
            "countrycode": settings.COUNTRY_CODE,   #settings.country_code,
            "maxresults": max_results,
            "compact": True,
            "opendata": True,
        },
        timeout=30.0,
    )
    resp.raise_for_status()
    with open ("api_result.txt","w", encoding="utf-8") as f:
        f.write(resp.text)
    print(resp.json())
    return resp.json()

def print_stations(stations: list[dict]) -> None:
    print(f"Found {len(stations)} charging stations\n")
    print("KEY: ", settings.OCM_API_KEY,"\n\n")
    for s in stations:
        addr = s.get("AddressInfo", {})
        name = addr.get("Title", "Unknown")
        town = addr.get("Town", "?")
        connections = s.get("Connections", []) or []
        statuses = [(c.get("StatusType") or {}).get("Title", "Unknown") for c in connections]
        powers = [c.get("PowerKW") for c in connections if c.get("PowerKW")]
        power_str = f"{max(powers):.0f} kW" if powers else "n/a"
        print(f"- {name} ({town}) | {len(connections)} connectors, max {power_str} | status: {', '.join(statuses) or 'unknown'}")


def print_records(stations: list[dict]) -> None:
    for record in stations:
        print(json.dumps(record, indent=2))


def save_records(stations: list[dict], path: str | None = None) -> None:
    if path is None:
        path = os.path.join(PROJECT_ROOT, "result-set", "stations.txt")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for record in stations:
            f.write(json.dumps(record, indent=2))
            f.write("\n")


if __name__ == "__main__":
    result = fetch_stations(max_results=1000, offset=0)
    print(f"Found {len(result)} charging stations\n")
    print(type(result))
    #print(f"Keys: {result.__dict__.keys()}\n")
    #print_records(result)
    save_records(result)
