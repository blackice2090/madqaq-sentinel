from fastapi import FastAPI
from pydantic import BaseModel

from sentinel.conformance.engine import ConformanceEngine
from sentinel.domain.models import ConformanceResult
from simulator.scenarios import SCENARIOS, scenario

app = FastAPI(title="MADQAQ Sentinel M0", version="0.1.0")


@app.get("/health")
def health():
    return {"status": "ok", "engine_version": "m0.1"}


@app.get("/m0/scenarios")
def list_scenarios():
    return {"scenarios": SCENARIOS}


@app.post("/m0/scenarios/{name}/evaluate", response_model=ConformanceResult)
def evaluate_scenario(name: str):
    if name not in SCENARIOS:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="scenario not found")
    proc, journey, physical, digital, _ = scenario(name)
    return ConformanceEngine().evaluate(proc, journey, physical, digital)
