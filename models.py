from pydantic import BaseModel, Field
from typing import List, Optional, Literal, Dict, Any

class ExtractRequest(BaseModel):
    input: str
    mode: Literal["live", "fixture"]
    case_id: Optional[str] = None
    consent: Optional[bool] = False

class MovementConfirm(BaseModel):
    id: str
    descripcion: str
    valor: Optional[float] = None
    categoria: str
    incluir: bool

class ConfirmRequest(BaseModel):
    token: str
    confirmed: bool
    ingreso_total: Optional[float] = None
    movimientos: List[MovementConfirm]
    selected_ids: List[str] = []

class ForgetRequest(BaseModel):
    token: str

class MovementInput(BaseModel):
    description: Optional[str] = None
    descripcion: Optional[str] = None
    amount: Optional[float] = None
    valor: Optional[float] = None
    category: Optional[str] = None
    categoria: Optional[str] = None
    source_quote: Optional[str] = None
    origin: Optional[str] = "manual"

class BudgetCreateRequest(BaseModel):
    year: int
    month: int
    income: Optional[float] = None
    movements: List[MovementInput]
    source_mode: str = "manual"
    replace: bool = False

class BudgetUpdateRequest(BaseModel):
    income: Optional[float] = None
    movements: List[MovementInput]

class CompareRequest(BaseModel):
    budget_a_id: str
    budget_b_id: str

class CompareExplanationRequest(BaseModel):
    comparison: dict
    budget_a_id: str
    budget_b_id: str
    consent: bool = False

class ScenarioInterpretRequest(BaseModel):
    text: str
    type: Literal["goal", "event"] = "goal"
    budget_id: Optional[str] = None
    consent: bool = False

class EventItem(BaseModel):
    description: str
    estimated_amount: Optional[float] = None
    source: str = "Estimación"

class ScenarioCalculateRequest(BaseModel):
    type: Literal["goal", "event"]
    budget_income: Optional[float] = None
    budget_expense: Optional[float] = 0.0
    target_amount: Optional[float] = None
    reductions: List[dict] = []
    items: List[EventItem] = []

