"""Deterministic comparison of two confirmed budgets. No model, no I/O."""
from decimal import Decimal, ROUND_HALF_UP
from spendwise_core import money, CATEGORIES
from spendwise_service import folded

def _period_key(year, month):
    """Generate a period key string 'YYYY-MM'."""
    return f"{year:04d}-{month:02d}"

def _sum_by_category(movements):
    """Return a dictionary mapping category names to total Decimal amounts."""
    totals = {cat: Decimal('0.00') for cat in CATEGORIES}
    for mov in movements:
        cat = mov.get('category')
        if cat in totals:
            totals[cat] += money(float(mov.get('amount', '0')))
    return totals

def _to_float_mov(m):
    """Return a movement with float amount for JSON serialization."""
    return {
        'id': m['id'],
        'description': m['description'],
        'amount': float(money(float(m['amount']))),
        'category': m['category']
    }

def _match_movements(movements_a, movements_b):
    """Match movements from budget A and B based on normalized descriptions.
    
    Returns:
        tuple: (changed, added, removed, unmatched)
    """
    changed = []
    added = []
    removed = []
    unmatched = []

    def group_by_desc(movements):
        groups = {}
        for m in movements:
            norm = folded(m['description'])
            groups.setdefault(norm, []).append(m)
        return groups

    groups_a = group_by_desc(movements_a)
    groups_b = group_by_desc(movements_b)
    
    all_norms = set(groups_a.keys()) | set(groups_b.keys())
    
    for norm in all_norms:
        list_a = groups_a.get(norm, [])
        list_b = groups_b.get(norm, [])
        
        if len(list_a) > 1 or len(list_b) > 1:
            for m in list_a:
                unmatched.append({
                    'a': _to_float_mov(m), 
                    'b': None, 
                    'reason': 'Descripción repetida; verificar manualmente'
                })
            for m in list_b:
                unmatched.append({
                    'a': None, 
                    'b': _to_float_mov(m), 
                    'reason': 'Descripción repetida; verificar manualmente'
                })
        elif len(list_a) == 1 and len(list_b) == 1:
            m_a = list_a[0]
            m_b = list_b[0]
            
            amount_diff = float(money(float(m_b['amount'])) - money(float(m_a['amount'])))
            desc_match = 'exact' if m_a['description'] == m_b['description'] else 'partial'
            
            changed.append({
                'a': _to_float_mov(m_a),
                'b': _to_float_mov(m_b),
                'amount_diff': amount_diff,
                'description_match': desc_match
            })
        elif len(list_a) == 1:
            removed.append(_to_float_mov(list_a[0]))
        elif len(list_b) == 1:
            added.append(_to_float_mov(list_b[0]))
            
    return changed, added, removed, unmatched

def compare_budgets(budget_a, budget_b):
    """Compare two confirmed budgets. Convention: all diffs are B minus A.
    
    Args:
        budget_a: dict with keys id, year, month, income (str|None), movements (list of dicts)
        budget_b: dict with keys id, year, month, income (str|None), movements (list of dicts)
    
    Each movement dict has at minimum: id, description, amount (decimal string), category
    
    Returns dict with:
        period_a: 'YYYY-MM' string
        period_b: 'YYYY-MM' string
        budget_a_id: str
        budget_b_id: str
        income_a: float or None
        income_b: float or None  
        income_diff: float or None (None if either income missing)
        expense_a: float
        expense_b: float
        expense_diff: float (B - A)
        balance_a: float or None
        balance_b: float or None
        balance_diff: float or None
        category_diffs: dict keyed by category name, each value is:
            {a: float, b: float, diff: float, pct_change: float or None}
            pct_change is None if base (a) is zero
        movements_added: list of movement dicts from B with no match in A
        movements_removed: list of movement dicts from A with no match in B
        movements_changed: list of {a: movement, b: movement, amount_diff: float, description_match: 'exact'|'partial'}
        movements_unmatched: list of {a: movement, b: movement, reason: str} for low-confidence matches
        warnings: list of strings describing limitations
    
    Raises ValueError if budgets have same period, or if either has no movements.
    """
    if not budget_a.get('movements') or not budget_b.get('movements'):
        raise ValueError("Both budgets must have movements")
        
    period_a = _period_key(budget_a['year'], budget_a['month'])
    period_b = _period_key(budget_b['year'], budget_b['month'])
    
    if period_a == period_b:
        raise ValueError("Budgets have the same period")
        
    warnings = []
    
    income_a_str = budget_a.get('income')
    income_b_str = budget_b.get('income')
    
    income_a = float(money(float(income_a_str))) if income_a_str is not None else None
    income_b = float(money(float(income_b_str))) if income_b_str is not None else None
    
    if income_a is None or income_b is None:
        income_diff = None
        warnings.append("Income missing in one or both budgets; income_diff is None")
    else:
        income_diff = float(money(float(income_b_str)) - money(float(income_a_str)))
        
    cat_totals_a = _sum_by_category(budget_a['movements'])
    cat_totals_b = _sum_by_category(budget_b['movements'])
    
    expense_a_dec = sum(cat_totals_a.values())
    expense_b_dec = sum(cat_totals_b.values())
    
    expense_a = float(expense_a_dec)
    expense_b = float(expense_b_dec)
    expense_diff = float(expense_b_dec - expense_a_dec)
    
    balance_a = income_a - expense_a if income_a is not None else None
    balance_b = income_b - expense_b if income_b is not None else None
    balance_diff = balance_b - balance_a if balance_a is not None and balance_b is not None else None
    
    category_diffs = {}
    for cat in CATEGORIES:
        a_val = cat_totals_a[cat]
        b_val = cat_totals_b[cat]
        diff_val = b_val - a_val
        
        pct_change = None
        if a_val != Decimal('0.00'):
            pct = (diff_val / a_val * Decimal('100')).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
            pct_change = float(pct)
            
        category_diffs[cat] = {
            'a': float(a_val),
            'b': float(b_val),
            'diff': float(diff_val),
            'pct_change': pct_change
        }
        if a_val == Decimal('0.00') and b_val > Decimal('0.00'):
            warnings.append(f"Category '{cat}' went from zero to positive expense.")

    changed, added, removed, unmatched = _match_movements(budget_a['movements'], budget_b['movements'])
    
    if unmatched:
        warnings.append(f"{len(unmatched)} unmatched movements with low confidence.")
        
    return {
        'period_a': period_a,
        'period_b': period_b,
        'budget_a_id': budget_a['id'],
        'budget_b_id': budget_b['id'],
        'income_a': income_a,
        'income_b': income_b,
        'income_diff': income_diff,
        'expense_a': expense_a,
        'expense_b': expense_b,
        'expense_diff': expense_diff,
        'balance_a': balance_a,
        'balance_b': balance_b,
        'balance_diff': balance_diff,
        'category_diffs': category_diffs,
        'movements_added': added,
        'movements_removed': removed,
        'movements_changed': changed,
        'movements_unmatched': unmatched,
        'warnings': warnings
    }
