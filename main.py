import secrets
import time
from typing import Dict, Tuple
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError
import os
from pathlib import Path

from models import (
    ExtractRequest, ConfirmRequest, ForgetRequest, BudgetCreateRequest, BudgetUpdateRequest,
    CompareRequest, CompareExplanationRequest, ScenarioInterpretRequest, ScenarioCalculateRequest
)
from database import (
    initialize_database, create_budget, list_budgets, get_budget, update_budget, delete_budget, get_budget_by_period
)
from services import (
    extract_budget_from_text, prepare_review, build_output, compare_budgets, explain_comparison,
    interpret_scenario, calculate_goal_scenario, calculate_event_scenario, MODEL_NAME
)
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="SpendWiseAI")

ROOT = Path(__file__).resolve().parent

# Application state
SESSIONS: Dict[str, Tuple[float, dict]] = {}
TTL = 1800

@app.on_event("startup")
def startup():
    initialize_database()

def prune_sessions():
    now = time.monotonic()
    expired = [k for k, v in SESSIONS.items() if now - v[0] > TTL]
    for k in expired:
        del SESSIONS[k]

@app.get("/api/config")
def get_config():
    # Return mock examples so the frontend doesn't break
    examples = [
        {"id": "c1", "input": "Me pagaron 2 millones. Pagué 500mil de arriendo (vivienda), 300mil en mercado (alimentacion), y 100mil en transporte."},
        {"id": "c2", "input": "Pagué la luz 80000, internet 100000. Salí a comer y gasté 150000."},
    ]
    return {
        "live_available": bool(os.getenv("GEMINI_API_KEY")),
        "model": MODEL_NAME,
        "examples": examples
    }

@app.get("/api/profiles")
def get_profiles():
    # Return an empty list or mock to not break frontend before full refactor
    return {"profiles": []}

@app.post("/api/extract")
def extract(req: ExtractRequest):
    try:
        if req.mode == "live":
            if not req.consent:
                raise ValueError("Autoriza el envio del texto a Gemini.")
            raw = extract_budget_from_text(req.input)
            meta = {"mode": "live", "model": MODEL_NAME}
        else:
            # Handle fixture minimally or just fall back to live
            raw = extract_budget_from_text(req.input)
            meta = {"mode": "fixture"}
            
        review = prepare_review(raw, req.input, meta)
        token = secrets.token_urlsafe(32)
        prune_sessions()
        SESSIONS[token] = (time.monotonic(), review)
        return {"token": token, **review}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/confirm")
def confirm(req: ConfirmRequest):
    prune_sessions()
    entry = SESSIONS.get(req.token)
    if not entry:
        raise HTTPException(status_code=410, detail="La revision expiro.")
    review = entry[1]
    
    if not req.confirmed:
        raise HTTPException(status_code=400, detail="Confirma que revisaste los datos.")
        
    accepted = []
    excluded = []
    corrections = []
    
    for m in req.movimientos:
        if not m.incluir:
            excluded.append(m.id)
            continue
        accepted.append({"id": m.id, "descripcion": m.descripcion, "valor": m.valor, "categoria": m.categoria})
    
    if not accepted:
        raise HTTPException(status_code=400, detail="Incluye al menos un gasto valido.")
        
    result = build_output(req.ingreso_total, accepted, req.selected_ids)
    if excluded:
        result['estado_financiero'] += f' Resumen parcial: excluiste {len(excluded)} movimiento(s).'
        
    return {
        "output": result,
        "movimientos_confirmados": accepted,
        "excluidos": excluded,
        "corregidos": corrections,
        "incidencias_revisadas": review['incidencias'],
        "metadata": review['metadata'],
        "human_confirmed": True
    }

@app.post("/api/forget")
def forget(req: ForgetRequest):
    SESSIONS.pop(req.token, None)
    return {"forgotten": True}

@app.post("/api/budgets")
def create_budget_endpoint(req: BudgetCreateRequest):
    try:
        existing_id = get_budget_by_period(req.year, req.month)
        if existing_id and not req.replace:
            return JSONResponse(status_code=409, content={
                "error": f"Ya existe un presupuesto para {req.year}-{req.month:02d}.",
                "existing_id": existing_id,
                "action_required": "replace"
            })
        if existing_id and req.replace:
            delete_budget(existing_id)
            
        movements = [m.model_dump(exclude_unset=True) for m in req.movements]
        result = create_budget(req.year, req.month, req.income, movements, req.source_mode)
        return {"budget": result, "saved": True}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/budgets")
def list_budgets_endpoint():
    return {"budgets": list_budgets()}

@app.get("/api/budgets/{budget_id}")
def get_budget_endpoint(budget_id: str):
    budget = get_budget(budget_id)
    if not budget:
        raise HTTPException(status_code=404, detail="No encontrado.")
    return {"budget": budget}

@app.put("/api/budgets/{budget_id}")
def update_budget_endpoint(budget_id: str, req: BudgetUpdateRequest):
    budget = get_budget(budget_id)
    if not budget:
        raise HTTPException(status_code=404, detail="No encontrado.")
    try:
        movements = [m.model_dump(exclude_unset=True) for m in req.movements]
        updated = update_budget(budget_id, req.income, movements)
        return {"budget": updated, "updated": True}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/api/budgets/{budget_id}")
def delete_budget_endpoint(budget_id: str):
    deleted = delete_budget(budget_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="No encontrado.")
    return {"deleted": True}

@app.post("/api/compare")
def compare_endpoint(req: CompareRequest):
    budget_a = get_budget(req.budget_a_id)
    budget_b = get_budget(req.budget_b_id)
    if not budget_a or not budget_b:
        raise HTTPException(status_code=404, detail="No encontrados.")
    comparison = compare_budgets(budget_a, budget_b)
    return {"comparison": comparison}

@app.post("/api/compare/explanation")
def compare_explanation_endpoint(req: CompareExplanationRequest):
    if not req.consent:
        raise HTTPException(status_code=400, detail="Autoriza el envío de datos.")
    budget_a = get_budget(req.budget_a_id)
    budget_b = get_budget(req.budget_b_id)
    if not budget_a or not budget_b:
        raise HTTPException(status_code=404, detail="No encontrados.")
    explanation = explain_comparison(req.comparison, budget_a['movements'], budget_b['movements'])
    return {"explanation": explanation}

@app.post("/api/scenarios/interpret")
def interpret_scenario_endpoint(req: ScenarioInterpretRequest):
    if not req.consent:
        raise HTTPException(status_code=400, detail="Autoriza el envío de datos.")
    budget_summary = {}
    if req.budget_id:
        budget = get_budget(req.budget_id)
        if budget:
            movs = budget.get('movements', [])
            expense = sum(float(m['amount']) for m in movs)
            inc = float(budget['income']) if budget.get('income') else None
            budget_summary = {'income': inc, 'expense': expense, 'balance': (inc - expense) if inc is not None else None, 'movements': [{'category': m['category'], 'amount': float(m['amount']), 'description': m['description']} for m in movs]}
    
    scenario = interpret_scenario(req.text, req.type, budget_summary)
    return {"scenario": scenario}

@app.post("/api/scenarios/calculate")
def calculate_scenario_endpoint(req: ScenarioCalculateRequest):
    if req.type == "goal":
        if req.target_amount is None:
            raise HTTPException(status_code=400, detail="Indica el monto objetivo.")
        result = calculate_goal_scenario(req.budget_expense, req.budget_income, req.target_amount, req.reductions)
    else:
        items = [i.model_dump(exclude_unset=True) for i in req.items]
        result = calculate_event_scenario(req.budget_income, req.budget_expense, items)
    return {"result": result, "type": req.type}

# Fallback for static files and frontend
app.mount("/", StaticFiles(directory=str(ROOT / "web"), html=True), name="web")

if __name__ == "__main__":
    import uvicorn
    # Make sure to run inside SpendWiseAI directory
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)

