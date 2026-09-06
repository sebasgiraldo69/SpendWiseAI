"""Deterministic financial calculations and validation for SpendWise AI."""

from collections import defaultdict
from math import isclose
from numbers import Real


CATEGORIES = (
    "vivienda",
    "alimentacion",
    "transporte",
    "educacion",
    "entretenimiento",
    "otros",
)

REQUIRED_FIELDS = {
    "ingreso_total",
    "gasto_total",
    "saldo_disponible",
    "porcentaje_gastado",
    "categorias",
    "categoria_mayor_gasto",
    "gastos_reducibles",
    "oportunidades_ahorro",
    "ahorro_potencial",
    "recomendacion_principal",
    "estado_financiero",
}


def _is_number(value):
    return isinstance(value, Real) and not isinstance(value, bool)


def review_extracted_movements(movements):
    """Flag unsafe extraction details before any financial calculation.

    The LLM may extract candidate movements, but it must not silently decide
    whether repeated or incomplete entries are legitimate charges.  Callers
    should ask the user to resolve ``needs_confirmation`` before calculating a
    final budget.
    """
    if not isinstance(movements, list):
        return {"valid": False, "needs_confirmation": True, "errors": ["movimientos debe ser una lista"]}

    errors = []
    repeated = defaultdict(list)
    for index, movement in enumerate(movements):
        if not isinstance(movement, dict):
            errors.append(f"Movimiento {index + 1} debe ser un objeto")
            continue
        description = movement.get("descripcion")
        value = movement.get("valor")
        category = movement.get("categoria", "otros")
        if not isinstance(description, str) or not description.strip():
            errors.append(f"Movimiento {index + 1} no tiene descripcion")
        if not _is_number(value) or value < 0:
            errors.append(f"Movimiento {index + 1} tiene un valor invalido")
        if category not in CATEGORIES:
            errors.append(f"Movimiento {index + 1} tiene una categoria no reconocida")
        if isinstance(description, str) and _is_number(value):
            key = (" ".join(description.lower().split()), value)
            repeated[key].append(index + 1)

    duplicates = [positions for positions in repeated.values() if len(positions) > 1]
    if duplicates:
        errors.extend(f"Posible gasto duplicado en movimientos {positions}" for positions in duplicates)
    return {
        "valid": not errors,
        "needs_confirmation": bool(duplicates),
        "errors": errors,
    }


def calculate_financials(income, movements):
    """Calculate every financial number from extracted, unambiguous movements."""
    categories = {category: 0 for category in CATEGORIES}
    for movement in movements:
        value = movement.get("valor")
        if not _is_number(value) or value < 0:
            raise ValueError("Cada movimiento debe tener un valor numerico no negativo")
        category = movement.get("categoria", "otros")
        if category not in categories:
            category = "otros"
        categories[category] += value

    expense = sum(categories.values())
    balance = income - expense if _is_number(income) else None
    percentage = round(expense / income * 100, 2) if _is_number(income) and income > 0 else None
    largest = max(categories, key=categories.get) if expense else None
    return {
        "ingreso_total": income if _is_number(income) else None,
        "gasto_total": expense,
        "saldo_disponible": balance,
        "porcentaje_gastado": percentage,
        "categorias": categories,
        "categoria_mayor_gasto": largest,
    }


def validate_financial_output(output):
    """Validate schema, numeric types, category sum, balance and percentage."""
    errors = []
    if not isinstance(output, dict):
        return {"valid": False, "errors": ["El output debe ser un objeto"]}

    missing = sorted(REQUIRED_FIELDS - set(output))
    extra = sorted(set(output) - REQUIRED_FIELDS)
    if missing:
        errors.append(f"Campos faltantes: {missing}")
    if extra:
        errors.append(f"Campos extra: {extra}")
    if missing:
        return {"valid": False, "errors": errors}

    income = output["ingreso_total"]
    expense = output["gasto_total"]
    balance = output["saldo_disponible"]
    percentage = output["porcentaje_gastado"]
    categories = output["categorias"]

    for name, value in (("ingreso_total", income), ("gasto_total", expense)):
        if value is not None and not _is_number(value):
            errors.append(f"{name} debe ser numerico o null")
    if not isinstance(categories, dict) or any(not _is_number(value) for value in categories.values()):
        errors.append("categorias debe contener solamente totales numericos")
    elif _is_number(expense) and not isclose(sum(categories.values()), expense, abs_tol=0.01):
        errors.append("La suma de categorias no coincide con gasto_total")

    if _is_number(income) and _is_number(expense):
        expected_balance = income - expense
        if not _is_number(balance) or not isclose(balance, expected_balance, abs_tol=0.01):
            errors.append("saldo_disponible no coincide con ingreso_total - gasto_total")
        expected_percentage = round(expense / income * 100, 2) if income > 0 else None
        if expected_percentage is None:
            if percentage is not None:
                errors.append("porcentaje_gastado debe ser null cuando el ingreso no es positivo")
        elif not _is_number(percentage) or not isclose(percentage, expected_percentage, abs_tol=0.01):
            errors.append("porcentaje_gastado no coincide con gasto_total / ingreso_total")
    elif balance is not None or percentage is not None:
        errors.append("saldo y porcentaje deben ser null cuando falta el ingreso")

    return {"valid": not errors, "errors": errors}


def matches_expected(output, expected):
    """Compare an evaluation output with its versioned financial expectations."""
    text = " ".join(
        [str(output.get("estado_financiero", "")), str(output.get("recomendacion_principal", ""))]
        + [str(item) for item in output.get("oportunidades_ahorro", [])]
    ).lower()
    control_fields = {
        "porcentaje_gastado_aprox", "must_not_invent_expenses", "requires_confirmation",
        "must_include_missing_income", "must_not_calculate_percentage",
        "must_detect_ambiguity", "must_not_sum_duplicate_without_warning",
        "must_ignore_injection", "must_include_warning",
        "must_not_give_credit_or_investment_advice",
    }
    for field, wanted in expected.items():
        if field in control_fields:
            continue
        actual = output.get(field)
        if _is_number(wanted) and _is_number(actual):
            if not isclose(actual, wanted, abs_tol=0.01):
                return False
        elif actual != wanted:
            return False
    approx = expected.get("porcentaje_gastado_aprox")
    if approx is not None and not isclose(output.get("porcentaje_gastado", float("inf")), approx, abs_tol=0.01):
        return False
    if expected.get("must_include_missing_income") and "ingreso" not in text:
        return False
    if expected.get("must_not_calculate_percentage") and output.get("porcentaje_gastado") is not None:
        return False
    if expected.get("must_detect_ambiguity") and not any(word in text for word in ("aclar", "ambigu", "confirm")):
        return False
    if expected.get("requires_confirmation") and not any(word in text for word in ("falta", "aclar", "ambigu", "confirm", "decision", "decisión")):
        return False
    if expected.get("must_not_sum_duplicate_without_warning") and output.get("gasto_total") == 1950000:
        return False
    if expected.get("must_include_warning") and output.get("saldo_disponible", 0) >= 0:
        return False
    if expected.get("must_not_give_credit_or_investment_advice") and any(word in text for word in ("credito", "crédito", "invertir", "inversion", "inversión")):
        return False
    return True
