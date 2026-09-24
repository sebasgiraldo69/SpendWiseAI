'use strict';
const $ = id => document.getElementById(id);
const money = value => value === null || value === undefined ? 'Sin dato' : new Intl.NumberFormat('es-CO',{style:'currency',currency:'COP',maximumFractionDigits:2}).format(value);
const diffMoney = value => { if (value === null || value === undefined) return 'Sin dato'; const prefix = value > 0 ? '+' : ''; return prefix + money(value); };
const labels = {vivienda:'Vivienda',alimentacion:'Alimentación',transporte:'Transporte',educacion:'Educación',entretenimiento:'Entretenimiento',otros:'Otros'};
const monthNames = ['Enero','Febrero','Marzo','Abril','Mayo','Junio','Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre'];
const caseLabels = ['Un mes completo','Sin ingreso registrado','Dos arriendos ambiguos','Instrucción maliciosa','Gastos mayores al ingreso','Ingreso de cero','Montos coloquiales','COP y USD mezclados','Un gasto sin monto','Una devolución','Categoría desconocida'];
let config, review, result, busy = false;
let currentComparison = null, currentScenario = null, currentScenarioType = 'goal';
const say = message => { $('notice').textContent = message; };
function node(tag,text,cls){const el=document.createElement(tag);if(text!==undefined)el.textContent=text;if(cls)el.className=cls;return el;}
function switchSection(name) { document.querySelectorAll('.app-section').forEach(s => s.hidden = true); document.querySelectorAll('.section-tabs .tab').forEach(t => t.classList.remove('active')); const section = $('section-' + name); if (section) section.hidden = false; const tab = document.querySelector(`.tab[data-section="${name}"]`); if (tab) tab.classList.add('active'); say(''); if (name === 'history') loadHistory(); if (name === 'compare') loadCompareOptions(); if (name === 'plan') loadPlanOptions(); }
$('section-tabs').addEventListener('click', e => { const tab = e.target.closest('.tab'); if (!tab) return; switchSection(tab.dataset.section); });
function show(step) { ['entry','review','result'].forEach((id,i) => { $(id).hidden = i !== step - 1; $('step'+(i+1)).classList.toggle('active', i === step - 1); }); }
async function post(path, payload) { const controller = new AbortController(); const timeout = setTimeout(() => controller.abort(), 50000); try { const response = await fetch(path, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload), signal:controller.signal}); const body = await response.json(); if (!response.ok) throw new Error(body.error || (typeof body.detail === 'string' ? body.detail : 'No se pudo completar la solicitud.')); return body; } finally { clearTimeout(timeout); } }
async function api(method, path, payload) { const controller = new AbortController(); const timeout = setTimeout(() => controller.abort(), 50000); try { const opts = {method, headers:{'Content-Type':'application/json'}, signal:controller.signal}; if (payload) opts.body = JSON.stringify(payload); const response = await fetch(path, opts); const body = await response.json(); if (!response.ok) throw new Error(body.error || (typeof body.detail === 'string' ? body.detail : 'No se pudo completar la solicitud.')); return body; } finally { clearTimeout(timeout); } }
async function task(fn) { if (busy) return; busy = true; document.querySelectorAll('button').forEach(b => b.disabled = true); try { await fn(); } catch (e) { say(e.name === 'AbortError' ? 'Tardó demasiado.' : e.message); } finally { busy = false; document.querySelectorAll('button').forEach(b => b.disabled = false); } }
async function forget() { if (review) { await post('/api/forget', {token: review.token}); review = null; } result = null; }
// profile logic removed
function modeChanged() { const live = $('mode').value === 'live'; $('consent-wrap').hidden = !live; $('input').readOnly = !live; $('mode-note').textContent = live ? (config.live_available ? 'OpenAI configurado.' : 'Falta OPENAI_API_KEY en .env. Reinicia el servidor.') : 'Ensayo con datos preparados.'; }
function exampleChanged() { $('input').value = config.examples[Number($('example').value)].input; }
function renderReview() {
  $('income').value = review.ingreso_total ?? ''; $('confirmed').checked = false; $('rows').replaceChildren(); $('issues').replaceChildren();
  $('review-mode').textContent = review.metadata.mode === 'fixture' ? 'ENSAYO SIMULADO' : 'INTERPRETADO CON OPENAI';
  if (review.incidencias.length) { const list = node('ul'); review.incidencias.forEach(i => list.append(node('li', i.detalle))); $('issues').append(list); }
  review.movimientos.forEach(m => {
    const row = node('tr'); row.dataset.id = m.id;
    const include = node('input'); include.type = 'checkbox'; include.checked = m.incluir; include.className = 'include'; include.setAttribute('aria-label', 'Incluir ' + m.descripcion); include.disabled = m.tipo === 'refund' || m.moneda !== 'COP';
    const description = node('input'); description.type = 'text'; description.value = m.descripcion; description.className = 'description'; description.maxLength = 200; description.setAttribute('aria-label', 'Descripción de ' + m.descripcion);
    const amount = node('input'); amount.type = 'number'; amount.min = '0'; amount.max = '1000000000000'; amount.step = '.01'; amount.value = m.valor ?? ''; amount.className = 'amount'; amount.setAttribute('aria-label', 'Monto de ' + m.descripcion); amount.disabled = include.disabled;
    const category = node('select'); category.className = 'category'; category.setAttribute('aria-label', 'Categoría de ' + m.descripcion); Object.entries(labels).forEach(([value, text]) => { const opt = node('option', text); opt.value = value; category.append(opt); }); category.value = m.categoria;
    const simulate = node('input'); simulate.type = 'checkbox'; simulate.className = 'simulate'; simulate.setAttribute('aria-label', 'Simular reducción de ' + m.descripcion); simulate.disabled = !include.checked;
    include.addEventListener('change', () => { simulate.disabled = !include.checked; if (!include.checked) simulate.checked = false; $('confirmed').checked = false; });
    [description, amount, category, simulate].forEach(el => el.addEventListener('change', () => { $('confirmed').checked = false; }));
    [include, description, amount, category, simulate].forEach((el, index) => { const cell = node('td'); cell.append(el); if (index === 1) { cell.append(node('div', '"' + m.fuente + '"', 'source')); if (m.moneda !== 'COP') cell.append(node('div', 'Moneda original: ' + m.moneda, 'source')); } row.append(cell); });
    $('rows').append(row);
  }); show(2);
}
function renderResult() {
  const output = result.output; $('total-income').textContent = money(output.ingreso_total); $('total-expense').textContent = money(output.gasto_total); $('total-balance').textContent = money(output.saldo_disponible); $('state').textContent = output.estado_financiero;
  $('result-mode').textContent = result.metadata.mode === 'fixture' ? 'ENSAYO SIMULADO · REVISADO POR TI' : 'DATOS REVISADOS POR TI';
  $('chart').replaceChildren(); Object.entries(output.categorias).forEach(([category, value]) => { const row = node('div', undefined, 'bar-row'); row.append(node('span', labels[category])); const progress = node('progress'); progress.max = output.gasto_total || 1; progress.value = value; progress.setAttribute('aria-label', labels[category]); row.append(progress, node('span', money(value))); $('chart').append(row); });
  $('percentage').textContent = output.porcentaje_gastado === null ? 'Sin ingreso para calcular porcentaje.' : `Gastaste el ${output.porcentaje_gastado.toLocaleString('es-CO')}% de tu ingreso.`;
  $('saving').textContent = money(output.ahorro_potencial); $('recommendation').textContent = output.recomendacion_principal || 'No seleccionaste un escenario.';
  $('opportunities').replaceChildren(); output.oportunidades_ahorro.forEach(o => { const m = result.movimientos_confirmados.find(m => m.id === o.id); $('opportunities').append(node('li', m.descripcion + ': ' + money(o.ahorro) + ' al reducir 10%.')); });
  $('trace').textContent = JSON.stringify({modo:result.metadata, flujo:['Texto','Extracción','Validación','Confirmación','Cálculo','Escenario'], confirmado:result.human_confirmed, correcciones:result.corregidos, excluidos:result.excluidos, movimientos:result.movimientos_confirmados, output}, null, 2);
  $('save-budget').hidden = false; show(3);
}
$('extract').addEventListener('click', () => task(async () => { await forget(); say('Interpretando…'); const selected = config.examples[Number($('example').value)]; review = await post('/api/extract', {input:$('input').value, mode:$('mode').value, case_id:selected.id, consent:$('consent').checked}); say('Revisa los datos.'); renderReview(); }));
$('confirm').addEventListener('click', () => task(async () => { if (!$('confirmed').checked) throw new Error('Confirma que revisaste los datos.'); const rows = [...$('rows').children]; const movements = rows.map(row => ({id:row.dataset.id, descripcion:row.querySelector('.description').value, valor:row.querySelector('.amount').value === '' ? null : Number(row.querySelector('.amount').value), categoria:row.querySelector('.category').value, incluir:row.querySelector('.include').checked})); result = await post('/api/confirm', {token:review.token, confirmed:true, ingreso_total:$('income').value === '' ? null : Number($('income').value), movimientos:movements, selected_ids:rows.filter(row => row.querySelector('.simulate').checked).map(row => row.dataset.id)}); say('Presupuesto calculado.'); renderResult(); }));
$('back').addEventListener('click', () => task(async () => { await forget(); show(1); say('Edita la entrada.'); }));
$('edit-review').addEventListener('click', () => { $('confirmed').checked = false; show(2); say('Ajusta los movimientos.'); });
$('income').addEventListener('input', () => { $('confirmed').checked = false; });
$('restart').addEventListener('click', () => task(async () => { await forget(); show(1); say('Revisión eliminada.'); $('trace').textContent = ''; $('rows').replaceChildren(); }));
$('download').addEventListener('click', () => { if (!result) return; const url = URL.createObjectURL(new Blob([JSON.stringify(result, null, 2)], {type:'application/json'})); const a = node('a'); a.href = url; a.download = 'spendwise-' + result.metadata.mode + '.json'; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000); });
$('save-budget').addEventListener('click', () => task(async () => {
  if (!result) { say('Necesitas un presupuesto.'); return; }
  const year = Number($('period-year').value), month = Number($('period-month').value);
  if (!year || !month || year < 2000 || year > 2200 || month < 1 || month > 12) { say('Selecciona año y mes.'); return; }
  const movements = result.movimientos_confirmados.map(m => ({description:m.descripcion, amount:m.valor, category:m.categoria, source_quote:m.fuente||null, origin:'interpreted'}));
  try { await post('/api/budgets', {year, month, income:result.output.ingreso_total, movements, source_mode:result.metadata.mode||'manual', replace:false}); say(`${monthNames[month-1]} ${year} guardado.`); }
  catch (e) { if (e.message.includes('Ya existe')) { if (confirm(`¿Reemplazar ${monthNames[month-1]} ${year}?`)) { await post('/api/budgets', {year, month, income:result.output.ingreso_total, movements, source_mode:result.metadata.mode||'manual', replace:true}); say('Reemplazado.'); } } else throw e; }
}));
async function loadHistory() {
  // no profile check
  try { const res = await api('GET', '/api/budgets'); const budgets = res.budgets || [];
    if (!budgets.length) { $('history-empty').hidden = false; $('history-list').hidden = true; return; }
    $('history-empty').hidden = true; $('history-list').hidden = false; $('history-rows').replaceChildren();
    budgets.forEach(b => { const row = node('tr'); row.append(node('td', `${monthNames[(b.month||1)-1]} ${b.year}`), node('td', b.income ? money(Number(b.income)) : 'Sin dato'), node('td', money(b.total_expense||0)), node('td', String(b.movement_count||0)), node('td', b.source_mode||'—'), node('td', b.updated_at ? b.updated_at.substring(0,10) : '—'));
      const actions = node('td'); const viewBtn = node('button', 'Ver', 'small-btn'); viewBtn.addEventListener('click', () => task(async () => { await showBudgetDetail(b.id); }));
      const delBtn = node('button', 'Eliminar', 'small-btn danger-text'); delBtn.addEventListener('click', () => task(async () => { if (!confirm(`¿Eliminar ${monthNames[(b.month||1)-1]} ${b.year}?`)) return; await api('DELETE', `/api/budgets/${b.id}`); say('Eliminado.'); await loadHistory(); }));
      actions.append(viewBtn, delBtn); row.append(actions); $('history-rows').append(row); });
  } catch (e) { say('Error al cargar historial.'); }
}
async function showBudgetDetail(bid) { const res = await api('GET', `/api/budgets/${bid}`); const b = res.budget; $('detail-title').textContent = `${monthNames[(b.month||1)-1]} ${b.year}`; $('detail-mode').textContent = (b.source_mode||'manual').toUpperCase(); const movs = b.movements||[]; const expense = movs.reduce((s,m) => s + Number(m.amount), 0); const inc = b.income ? Number(b.income) : null; $('detail-income').textContent = money(inc); $('detail-expense').textContent = money(expense); $('detail-balance').textContent = inc !== null ? money(inc - expense) : 'Sin dato'; $('detail-movements').replaceChildren(); movs.forEach(m => { const row = node('tr'); row.append(node('td',m.description), node('td',money(Number(m.amount))), node('td',labels[m.category]||m.category), node('td',m.origin||'—')); $('detail-movements').append(row); }); $('budget-detail').hidden = false; $('budget-detail').dataset.budgetId = bid; }
$('detail-back').addEventListener('click', () => { $('budget-detail').hidden = true; });
$('detail-delete').addEventListener('click', () => task(async () => { const bid = $('budget-detail').dataset.budgetId; if (!bid || !confirm('¿Eliminar?')) return; await api('DELETE', `/api/budgets/${bid}`); $('budget-detail').hidden = true; say('Eliminado.'); await loadHistory(); }));
$('refresh-history').addEventListener('click', () => task(async () => { await loadHistory(); }));
async function loadCompareOptions() { try { const res = await api('GET', '/api/budgets'); const budgets = res.budgets||[]; [$('compare-a'), $('compare-b')].forEach(sel => { const cur = sel.value; sel.replaceChildren(node('option', 'Selecciona un mes')); sel.querySelector('option').value = ''; budgets.forEach(b => { const opt = node('option', `${monthNames[(b.month||1)-1]} ${b.year}`); opt.value = b.id; sel.append(opt); }); if (cur) sel.value = cur; }); } catch (e) {} }
$('run-compare').addEventListener('click', () => task(async () => { const aId = $('compare-a').value, bId = $('compare-b').value; if (!aId || !bId) throw new Error('Selecciona dos meses.'); if (aId === bId) throw new Error('Meses diferentes.'); const res = await post('/api/compare', {budget_a_id:aId, budget_b_id:bId}); currentComparison = res.comparison; currentComparison._aId = aId; currentComparison._bId = bId; renderComparison(res.comparison); }));
function renderComparison(c) {
  $('compare-title').textContent = `${c.period_a} vs ${c.period_b}`; $('compare-income-diff').textContent = diffMoney(c.income_diff); $('compare-expense-diff').textContent = diffMoney(c.expense_diff); $('compare-balance-diff').textContent = diffMoney(c.balance_diff);
  const ct = document.createElement('table'); const ch = node('tr'); ['Categoría','A','B','Dif','%'].forEach(h => ch.append(node('th',h))); ct.append(ch);
  if (c.category_diffs) Object.entries(c.category_diffs).forEach(([cat,d]) => { const r = node('tr'); r.append(node('td',labels[cat]||cat), node('td',money(d.a)), node('td',money(d.b)), node('td',diffMoney(d.diff)), node('td',d.pct_change!==null?d.pct_change.toFixed(1)+'%':'—')); if (d.diff>0) r.children[3].classList.add('increase'); else if (d.diff<0) r.children[3].classList.add('decrease'); ct.append(r); });
  $('compare-categories').replaceChildren(ct);
  $('compare-warnings').replaceChildren(); if (c.warnings?.length) { const wl = node('ul'); c.warnings.forEach(w => wl.append(node('li',w))); $('compare-warnings').append(wl); }
  const md = $('compare-movements'); md.replaceChildren();
  if (c.movements_added?.length) { md.append(node('h4',`${c.movements_added.length} nuevo(s)`)); c.movements_added.forEach(m => md.append(node('p',`+ ${m.description}: ${money(m.amount)}`,'movement-added'))); }
  if (c.movements_removed?.length) { md.append(node('h4',`${c.movements_removed.length} eliminado(s)`)); c.movements_removed.forEach(m => md.append(node('p',`− ${m.description}: ${money(m.amount)}`,'movement-removed'))); }
  if (c.movements_changed?.length) { md.append(node('h4',`${c.movements_changed.length} cambiado(s)`)); c.movements_changed.forEach(mc => md.append(node('p',`${mc.a.description}: ${money(mc.a.amount)} → ${money(mc.b.amount)} (${diffMoney(mc.amount_diff)})`,mc.description_match==='partial'?'movement-partial':'movement-changed'))); }
  if (c.movements_unmatched?.length) { md.append(node('h4','Posibles coincidencias')); c.movements_unmatched.forEach(mu => md.append(node('p',`${mu.a.description} ↔ ${mu.b.description}`,'movement-partial'))); }
  $('compare-result').hidden = false; $('explanation-result').hidden = true;
}
$('explain-changes').addEventListener('click', () => task(async () => { if (!currentComparison) throw new Error('Compara primero.'); if (!$('compare-consent').checked) throw new Error('Autoriza envío.'); say('Pidiendo explicación…'); const res = await post('/api/compare/explanation', {comparison:currentComparison, budget_a_id:currentComparison._aId, budget_b_id:currentComparison._bId, consent:true}); renderExplanation(res.explanation); }));
function renderExplanation(exp) { const od = $('explanation-observations'); od.replaceChildren(); if (exp.observaciones) exp.observaciones.forEach(o => { const card = node('div',undefined,'observation-card'); card.append(node('h4',o.titulo), node('p',o.explicacion), node('p',`Diferencia: ${money(o.diferencia_calculada)}`,'hint')); if (o.needs_review) card.append(node('span','Verificar','tag scenario-tag')); card.append(node('span',`Confianza: ${o.confidence}`,'tag')); od.append(card); }); const ld = $('explanation-limitations'); ld.replaceChildren(); if (exp.limitaciones?.length) { ld.append(node('h4','Limitaciones')); const l = node('ul'); exp.limitaciones.forEach(li => l.append(node('li',li))); ld.append(l); } $('explanation-result').hidden = false; }
$('mode').addEventListener('change', modeChanged); $('example').addEventListener('change', exampleChanged);
(async () => { try { const response = await fetch('/api/config'); if (!response.ok) throw new Error('Error.'); config = await response.json(); config.examples.forEach((example, index) => { const option = node('option', caseLabels[index] || example.id); option.value = index; $('example').append(option); }); modeChanged(); const now = new Date(); $('period-year').value = now.getFullYear(); $('period-month').value = now.getMonth() + 1; } catch (e) { say('Error al iniciar: ' + e.message); $('extract').disabled = true; } })();
