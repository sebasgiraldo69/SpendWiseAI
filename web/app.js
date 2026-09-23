import * as API from '/api.js';
'use strict';
const $ = id => document.getElementById(id);
const money = value => value === null || value === undefined ? 'Sin dato' : new Intl.NumberFormat('es-CO',{style:'currency',currency:'COP',maximumFractionDigits:2}).format(value);
const diffMoney = value => { if (value === null || value === undefined) return 'Sin dato'; const prefix = value > 0 ? '+' : ''; return prefix + money(value); };
const labels = {vivienda:'Vivienda',alimentacion:'Alimentación',transporte:'Transporte',educacion:'Educación',entretenimiento:'Entretenimiento',otros:'Otros'};
const monthNames = ['Enero','Febrero','Marzo','Abril','Mayo','Junio','Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre'];
let config, review, result;
const busyActions = new Set();
let budgetCache = null, detailedBudget = null;
let currentComparison = null, currentScenario = null, currentScenarioType = 'goal', scenarioBudget=null, scenarioKind=null, scenarioResult=null;
const say = message => { $('notice').textContent = message; };
function node(tag,text,cls){const el=document.createElement(tag);if(text!==undefined)el.textContent=text;if(cls)el.className=cls;return el;}
function switchSection(name) { document.querySelectorAll('.app-section').forEach(s => s.hidden = true); document.querySelectorAll('.section-tabs .tab').forEach(t => t.classList.remove('active')); const section = $('section-' + name); if (section) section.hidden = false; const tab = document.querySelector(`.tab[data-section="${name}"]`); if (tab) tab.classList.add('active'); say(''); if (name === 'history') loadHistory(); if (name === 'compare') loadCompareOptions(); if (name === 'plan') loadPlanOptions(); }
$('section-tabs').addEventListener('click', e => { const tab = e.target.closest('.tab'); if (!tab) return; if (!config?.active_profile && tab.dataset.section !== 'register') { say('Selecciona un perfil primero.'); return; } switchSection(tab.dataset.section); });
function show(step) { ['entry','review','result'].forEach((id,i) => { $(id).hidden = i !== step - 1; $('step'+(i+1)).classList.toggle('active', i === step - 1); }); }
const api = (method,path,payload) => API.request(method,path,payload);
const post = (path,payload) => api('POST',path,payload);
async function task(fn) {
  const control=document.activeElement, key=control?.id || 'action';
  if(busyActions.has(key))return;
  busyActions.add(key);
  if(control?.tagName==='BUTTON')control.disabled=true;
  try{await fn();}catch(e){if(e.name!=='AbortError')say(e.message);}
  finally{busyActions.delete(key);if(control?.tagName==='BUTTON')control.disabled=false;}
}
async function analyze(path,payload){
  return API.analyze(path,payload,(state,elapsed)=>{
    $('analysis-progress').hidden=state==='finished';
    $('analysis-status').textContent=(state==='queued'?'En espera':'Gemini está analizando')+' · '+elapsed+' s';
  });
}
$('cancel-analysis').onclick=()=>{API.cancelAnalysis();say('Análisis cancelado. Puedes volver a intentarlo.');};
async function forget(){const token=review?.token;review=null;result=null;if(token)post('/api/forget',{token}).catch(()=>{});}
function clearProfileViews(){
  review=null;result=null;currentComparison=null;currentScenario=null;scenarioBudget=null;scenarioResult=null;budgetCache=null;
  ['rows','history-rows','detail-movements','plan-items','trace','chart','opportunities','explanation-observations','compare-movements'].forEach(id=>$(id).replaceChildren());
  ['budget-detail','saved-income-holder','compare-result','explanation-result','plan-assumptions','plan-result','history-list','analysis-progress'].forEach(id=>$(id).hidden=true);
  ['compare-a','compare-b','plan-budget'].forEach(id=>$(id).replaceChildren());
  $('input').value='';$('plan-text').value='';show(1);switchSection('register');
}
$('profile-select').addEventListener('change',async()=>{
  const control=$('profile-select'),pid=control.value,previous=config.active_profile;
  if(!pid)return;
  API.invalidate();clearProfileViews();control.disabled=true;
  try{const res=await post('/api/profile/select',{profile_id:pid});config.active_profile=pid;$('profile-label').textContent=res.profile.display_name.toUpperCase();say('Perfil: '+res.profile.display_name);}
  catch(e){control.value=previous||'';say(e.message);}
  finally{control.disabled=false;}
});
$('add-profile').onclick=()=>task(async()=>{
  const name=prompt('Nombre del perfil local');if(!name?.trim())return;
  const {profile}=await post('/api/profiles',{display_name:name.trim()});
  const option=node('option',profile.display_name);option.value=profile.id;$('profile-select').append(option);
  $('profile-select').value=profile.id;$('profile-select').dispatchEvent(new Event('change'));
});
async function getBudgets(){
  if(budgetCache && Date.now()-budgetCache.time<10000)return budgetCache.data;
  const data=await api('GET','/api/budgets');budgetCache={time:Date.now(),data};return data;
}
function renderReview() {
  $('income').value = review.ingreso_total ?? ''; $('confirmed').checked = false; $('rows').replaceChildren(); $('issues').replaceChildren();
  $('review-mode').textContent = 'INTERPRETADO CON GEMINI';
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
  $('result-mode').textContent = 'DATOS REVISADOS POR TI';
  $('chart').replaceChildren(); Object.entries(output.categorias).forEach(([category, value]) => { const row = node('div', undefined, 'bar-row'); row.append(node('span', labels[category])); const progress = node('progress'); progress.max = output.gasto_total || 1; progress.value = value; progress.setAttribute('aria-label', labels[category]); row.append(progress, node('span', money(value))); $('chart').append(row); });
  $('percentage').textContent = output.porcentaje_gastado === null ? 'Sin ingreso para calcular porcentaje.' : `Gastaste el ${output.porcentaje_gastado.toLocaleString('es-CO')}% de tu ingreso.`;
  $('saving').textContent = money(output.ahorro_potencial); $('recommendation').textContent = output.recomendacion_principal || 'No seleccionaste un escenario.';
  $('opportunities').replaceChildren(); output.oportunidades_ahorro.forEach(o => { const m = result.movimientos_confirmados.find(m => m.id === o.id); $('opportunities').append(node('li', m.descripcion + ': ' + money(o.ahorro) + ' al reducir 10%.')); });
  $('trace').textContent = JSON.stringify({modo:result.metadata, flujo:['Texto','Extracción','Validación','Confirmación','Cálculo','Escenario'], confirmado:result.human_confirmed, correcciones:result.corregidos, excluidos:result.excluidos, movimientos:result.movimientos_confirmados, output}, null, 2);
  $('save-budget').hidden = !config?.active_profile; show(3);
}
$('extract').addEventListener('click',()=>task(async()=>{
  if(!config.active_profile)throw new Error('Selecciona un perfil.');
  if(!$('input').value.trim())throw new Error('Escribe tus ingresos y gastos.');
  if(!$('consent').checked)throw new Error('Autoriza el envío a Gemini.');
  await forget();say('');
  review=await analyze('/api/extract',{input:$('input').value,consent:true});
  say('Revisa los datos.');renderReview();
}));
$('confirm').addEventListener('click', () => task(async () => { if (!$('confirmed').checked) throw new Error('Confirma que revisaste los datos.'); const rows = [...$('rows').children]; const movements = rows.map(row => ({id:row.dataset.id, descripcion:row.querySelector('.description').value, valor:row.querySelector('.amount').value === '' ? null : Number(row.querySelector('.amount').value), categoria:row.querySelector('.category').value, incluir:row.querySelector('.include').checked})); result = await post('/api/confirm', {token:review.token, confirmed:true, ingreso_total:$('income').value === '' ? null : Number($('income').value), movimientos:movements, selected_ids:rows.filter(row => row.querySelector('.simulate').checked).map(row => row.dataset.id)}); say('Presupuesto calculado.'); renderResult(); }));
$('back').addEventListener('click', () => task(async () => { await forget(); show(1); say('Edita la entrada.'); }));
$('edit-review').addEventListener('click', () => { $('confirmed').checked = false; show(2); say('Ajusta los movimientos.'); });
$('income').addEventListener('input', () => { $('confirmed').checked = false; });
$('restart').addEventListener('click', () => task(async () => { await forget(); show(1); say('Revisión eliminada.'); $('trace').textContent = ''; $('rows').replaceChildren(); }));
$('download').addEventListener('click', () => { if (!result) return; const url = URL.createObjectURL(new Blob([JSON.stringify(result, null, 2)], {type:'application/json'})); const a = node('a'); a.href = url; a.download = 'spendwise-' + result.metadata.mode + '.json'; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000); });
$('save-budget').addEventListener('click', () => task(async () => {
  budgetCache=null; if (!result || !config?.active_profile) { say('Necesitas perfil y presupuesto.'); return; }
  const year = Number($('period-year').value), month = Number($('period-month').value);
  if (!year || !month || year < 2000 || year > 2200 || month < 1 || month > 12) { say('Selecciona año y mes.'); return; }
  const movements = result.movimientos_confirmados.map(m => ({description:m.descripcion, amount:m.valor, category:m.categoria, source_quote:m.fuente||null, origin:'interpreted'}));
  try { await post('/api/budgets', {year, month, income:result.output.ingreso_total, movements, source_mode:result.metadata.mode||'manual', replace:false}); say(`${monthNames[month-1]} ${year} guardado.`); }
  catch (e) { if (e.message.includes('Ya existe')) { if (confirm(`¿Reemplazar ${monthNames[month-1]} ${year}?`)) { await post('/api/budgets', {year, month, income:result.output.ingreso_total, movements, source_mode:result.metadata.mode||'manual', replace:true}); say('Reemplazado.'); } } else throw e; }
}));
async function loadHistory() {
  if (!config?.active_profile) return;
  try { const res = await getBudgets(); const budgets = res.budgets || [];
    if (!budgets.length) { $('history-empty').hidden = false; $('history-list').hidden = true; return; }
    $('history-empty').hidden = true; $('history-list').hidden = false; $('history-rows').replaceChildren();
    budgets.forEach(b => { const row = node('tr'); row.append(node('td', `${monthNames[(b.month||1)-1]} ${b.year}`), node('td', b.income ? money(Number(b.income)) : 'Sin dato'), node('td', money(b.total_expense||0)), node('td', String(b.movement_count||0)), node('td', b.source_mode||'—'), node('td', b.updated_at ? b.updated_at.substring(0,10) : '—'));
      const actions = node('td'); const viewBtn = node('button', 'Ver', 'small-btn'); viewBtn.addEventListener('click', () => task(async () => { await showBudgetDetail(b.id); }));
      const delBtn = node('button', 'Eliminar', 'small-btn danger-text'); delBtn.addEventListener('click', () => task(async () => { if (!confirm(`¿Eliminar ${monthNames[(b.month||1)-1]} ${b.year}?`)) return; budgetCache=null; await api('DELETE', `/api/budgets/${b.id}`); say('Eliminado.'); budgetCache=null; await loadHistory(); }));
      actions.append(viewBtn, delBtn); row.append(actions); $('history-rows').append(row); });
  } catch (e) { if(e.name!=='AbortError')say(e.message); }
}
async function showBudgetDetail(bid) { const res = await api('GET', `/api/budgets/${bid}`); const b = res.budget; detailedBudget=b; ['saved-income-holder','detail-save','detail-cancel'].forEach(id=>$(id).hidden=true); $('detail-edit').hidden=false; $('detail-title').textContent = `${monthNames[(b.month||1)-1]} ${b.year}`; $('detail-mode').textContent = (b.source_mode||'manual').toUpperCase(); const movs = b.movements||[]; const expense = res.summary.gasto_total; const inc = res.summary.ingreso_total; $('detail-income').textContent = money(inc); $('detail-expense').textContent = money(expense); $('detail-balance').textContent = inc !== null ? money(res.summary.saldo_disponible) : 'Sin dato'; $('detail-movements').replaceChildren(); movs.forEach(m => { const row = node('tr'); row.append(node('td',m.description), node('td',money(Number(m.amount))), node('td',labels[m.category]||m.category), node('td',m.origin||'—')); $('detail-movements').append(row); }); $('budget-detail').hidden = false; $('budget-detail').dataset.budgetId = bid; }
$('detail-edit').onclick=()=>{
  if(!detailedBudget)return;
  $('saved-income').value=detailedBudget.income??'';$('saved-income-holder').hidden=false;
  $('detail-movements').replaceChildren();
  detailedBudget.movements.forEach(m=>{
    const row=node('tr');
    const description=node('input');description.value=m.description;description.className='saved-description';description.setAttribute('aria-label','Editar '+m.description);
    const amount=node('input');amount.type='number';amount.min='0';amount.step='.01';amount.value=m.amount;amount.className='saved-amount';amount.setAttribute('aria-label','Nuevo monto '+m.description);
    const category=node('select');category.className='saved-category';Object.entries(labels).forEach(([value,text])=>{const option=node('option',text);option.value=value;category.append(option);});category.value=m.category;
    [description,amount,category].forEach(input=>{const cell=node('td');cell.append(input);row.append(cell);});row.append(node('td','Manual'));$('detail-movements').append(row);
  });
  $('detail-edit').hidden=true;$('detail-save').hidden=false;$('detail-cancel').hidden=false;
};
$('detail-cancel').onclick=()=>task(async()=>{await showBudgetDetail(detailedBudget.id);});
$('detail-save').onclick=()=>task(async()=>{
  const id=detailedBudget.id;
  const movements=[...$('detail-movements').children].map(row=>{
    const value=row.querySelector('.saved-amount').value;if(value==='')throw new Error('Completa los montos.');
    return {description:row.querySelector('.saved-description').value,amount:Number(value),category:row.querySelector('.saved-category').value,origin:'manual'};
  });
  await api('PUT','/api/budgets/'+id,{income:$('saved-income').value===''?null:Number($('saved-income').value),movements});
  budgetCache=null;await showBudgetDetail(id);await loadHistory();say('Cambios guardados y presupuesto recalculado.');
});
$('detail-back').addEventListener('click', () => { $('budget-detail').hidden = true; });
$('detail-delete').addEventListener('click', () => task(async () => { const bid = $('budget-detail').dataset.budgetId; if (!bid || !confirm('¿Eliminar?')) return; budgetCache=null; await api('DELETE', `/api/budgets/${bid}`); $('budget-detail').hidden = true; say('Eliminado.'); budgetCache=null; await loadHistory(); }));
$('refresh-history').addEventListener('click', () => task(async () => { budgetCache=null; await loadHistory(); }));
async function loadCompareOptions() { if (!config?.active_profile) return; try { const res = await getBudgets(); const budgets = res.budgets||[]; [$('compare-a'), $('compare-b')].forEach(sel => { const cur = sel.value; sel.replaceChildren(node('option', 'Selecciona un mes')); sel.querySelector('option').value = ''; budgets.forEach(b => { const opt = node('option', `${monthNames[(b.month||1)-1]} ${b.year}`); opt.value = b.id; sel.append(opt); }); if (cur) sel.value = cur; }); } catch (e) {if(e.name!=='AbortError')say(e.message);} }
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
  if (c.movements_unmatched?.length) { md.append(node('h4','Posibles coincidencias')); c.movements_unmatched.forEach(mu => md.append(node('p',`${mu.a?.description || "Sin coincidencia"} ↔ ${mu.b?.description || "Sin coincidencia"}`,'movement-partial'))); }
  $('compare-result').hidden = false; $('explanation-result').hidden = true;
}
$('explain-changes').addEventListener('click', () => task(async () => { if (!currentComparison) throw new Error('Compara primero.'); if (!$('compare-consent').checked) throw new Error('Autoriza envío.'); say('Pidiendo explicación…'); const res = await analyze('/api/compare/explanation', { budget_a_id:currentComparison._aId, budget_b_id:currentComparison._bId, consent:true}); renderExplanation(res.explanation); }));
function renderExplanation(exp) { const od = $('explanation-observations'); od.replaceChildren(); if (exp.observaciones) exp.observaciones.forEach(o => { const card = node('div',undefined,'observation-card'); card.append(node('h4',o.titulo), node('p',o.explicacion), node('p',`Diferencia: ${money(o.diferencia_calculada)}`,'hint')); if (o.needs_review) card.append(node('span','Verificar','tag scenario-tag')); card.append(node('span',`Confianza: ${o.confidence}`,'tag')); od.append(card); }); const ld = $('explanation-limitations'); ld.replaceChildren(); if (exp.limitaciones?.length) { ld.append(node('h4','Limitaciones')); const l = node('ul'); exp.limitaciones.forEach(li => l.append(node('li',li))); ld.append(l); } $('explanation-result').hidden = false; }
async function loadPlanOptions() { if (!config?.active_profile) return; try { const res = await getBudgets(); const sel = $('plan-budget'); sel.replaceChildren(node('option','Selecciona un mes')); sel.querySelector('option').value = ''; (res.budgets||[]).forEach(b => { const opt = node('option',`${monthNames[(b.month||1)-1]} ${b.year}`); opt.value = b.id; sel.append(opt); }); } catch(e){if(e.name!=='AbortError')say(e.message);} }
document.querySelectorAll('input[name="plan-type"]').forEach(r => { r.addEventListener('change', () => { currentScenarioType = r.value; $('plan-text').placeholder = r.value==='goal' ? 'Quiero liberar 150.000 pesos.' : 'Quiero planear un viaje.'; }); });
$('plan-interpret').addEventListener('click',()=>task(async()=>{
  if(!$('plan-consent').checked)throw new Error('Autoriza el envío a Gemini.');
  const text=$('plan-text').value, budgetId=$('plan-budget').value, kind=currentScenarioType;
  if(!text.trim()||!budgetId)throw new Error('Selecciona un presupuesto y describe tu plan.');
  const budgetResponse=await api('GET','/api/budgets/'+budgetId);
  const res=await analyze('/api/scenarios/interpret',{text,type:kind,budget_id:budgetId,consent:true});
  currentScenario=res.scenario;scenarioBudget=budgetResponse.budget;scenarioKind=kind;scenarioResult=null;
  renderPlanAssumptions(currentScenario,kind);
}));
function renderPlanAssumptions(scenario,type){
  $('plan-confirmed').checked=false;
  $('plan-assumptions-title').textContent=type==='goal'?'Meta de ajuste':'Plan de evento';
  const questions=$('plan-questions');questions.replaceChildren();
  if(scenario.questions?.length){const list=node('ul');scenario.questions.forEach(q=>list.append(node('li',q)));questions.append(list);}
  const container=$('plan-items');container.replaceChildren();
  if(type==='goal'){
    const label=node('label','Meta de ahorro (COP)');label.htmlFor='goal-target';
    const target=node('input');target.id='goal-target';target.type='number';target.min='0';target.step='.01';target.value=scenario.target_amount??'';
    container.append(label,target,node('p','Elige cuánto reducir en cada movimiento. Las categorías protegidas quedan sin reducción.','hint'));
    const table=node('table'),head=node('tr');['Gasto','Monto actual','Reducción COP'].forEach(t=>head.append(node('th',t)));table.append(head);
    scenarioBudget.movements.forEach(m=>{
      const row=node('tr');row.dataset.movementId=m.id;
      const value=node('input');value.type='number';value.min='0';value.max=m.amount;value.step='.01';value.value='0';value.className='goal-reduction';value.setAttribute('aria-label','Reducir '+m.description);
      value.disabled=(scenario.protected_categories||[]).includes(m.category);
      const cell=node('td');cell.append(value);row.append(node('td',m.description+(value.disabled?' (protegido)':'')),node('td',money(Number(m.amount))),cell);table.append(row);
    });container.append(table);
  }else{
    container.append(node('p','Evento: '+scenario.name));
    const table=node('table'),head=node('tr');['Rubro','Monto estimado COP','Origen'].forEach(t=>head.append(node('th',t)));table.append(head);
    (scenario.items||[]).forEach((item,index)=>{
      const row=node('tr');row.dataset.index=index;
      const description=node('input');description.value=item.description;description.className='plan-item-desc';description.setAttribute('aria-label','Rubro '+(index+1));
      const amount=node('input');amount.type='number';amount.min='0';amount.step='.01';amount.value=item.estimated_amount??'';amount.className='plan-item-amt';amount.setAttribute('aria-label','Monto del rubro '+(index+1));
      const dc=node('td'),ac=node('td');dc.append(description);ac.append(amount);row.append(dc,ac,node('td',item.source||'Por confirmar'));table.append(row);
    });container.append(table);
    if(!scenario.items?.length)container.append(node('p','Describe los rubros del evento y vuelve a interpretar.'));
  }
  container.querySelectorAll('input').forEach(input=>input.addEventListener('input',()=>{$('plan-confirmed').checked=false;$('plan-result').hidden=true;}));
  $('plan-assumptions').hidden=false;$('plan-result').hidden=true;
}
$('plan-calculate').addEventListener('click',()=>task(async()=>{
  if(!currentScenario||!scenarioBudget)throw new Error('Interpreta primero el plan.');
  if(!$('plan-confirmed').checked)throw new Error('Confirma los montos y supuestos.');
  const payload={type:scenarioKind,budget_id:scenarioBudget.id,confirmed:true};
  if(scenarioKind==='goal'){
    if($('goal-target').value==='')throw new Error('Indica tu meta.');
    payload.target_amount=Number($('goal-target').value);
    payload.reductions=[...$('plan-items').querySelectorAll('tr[data-movement-id]')].map(row=>({movement_id:row.dataset.movementId,reduce_by:Number(row.querySelector('input').value)})).filter(r=>r.reduce_by!==0);
  }else{
    payload.items=[...$('plan-items').querySelectorAll('tr[data-index]')].map(row=>{
      const value=row.querySelector('.plan-item-amt').value;
      if(value==='')throw new Error('Completa todos los montos. Un dato faltante no equivale a cero.');
      return {description:row.querySelector('.plan-item-desc').value,estimated_amount:Number(value),source:'Confirmado por el usuario'};
    });
  }
  const response=await post('/api/scenarios/calculate',payload);scenarioResult=response;
  renderPlanResult(response.result,scenarioKind);
}));
function createMetric(label, value, cls) { const a = node('article', undefined, cls||''); a.append(node('span',label), node('strong',value)); return a; }
function renderPlanResult(r, type) {
  $('plan-result-title').textContent = type==='goal' ? 'Meta de ajuste' : 'Evento'; const c=$('plan-result-content'); c.replaceChildren();
  if (type==='goal') { const m=node('div',undefined,'metrics'); m.append(createMetric('Meta',money(r.target_amount)), createMetric('Reducido',money(r.total_reduced)), createMetric('Brecha',money(r.remaining_gap), r.feasible?'balance':'')); c.append(m); c.append(node('p',r.feasible?'✅ Meta alcanzable.':'⚠️ No alcanza.','state')); if (r.new_balance!==null) c.append(node('p',`Saldo: ${money(r.new_balance)}`,'hint')); }
  else { const m=node('div',undefined,'metrics'); m.append(createMetric('Costo',money(r.event_total)), createMetric('Saldo',money(r.budget_balance)), createMetric('Restante',money(r.remaining_after_event), r.affordable?'balance':'')); c.append(m); if (r.affordable===true) c.append(node('p','✅ Cabe en presupuesto.','state')); else if (r.affordable===false) c.append(node('p','⚠️ Excede saldo.','state')); else c.append(node('p','Sin ingreso.','state')); if (r.items) { const t=document.createElement('table'); const h=node('tr'); ['Rubro','Monto','Fuente'].forEach(x=>h.append(node('th',x))); t.append(h); r.items.forEach(i => { const ro=node('tr'); ro.append(node('td',i.description), node('td',money(i.estimated_amount)), node('td',i.source)); t.append(ro); }); c.append(t); } }
  if (r.warnings?.length) { const wd=node('div',undefined,'issues'); const wl=node('ul'); r.warnings.forEach(w=>wl.append(node('li',w))); wd.append(wl); c.append(wd); }
  $('plan-result').hidden = false;
}
$('plan-discard').addEventListener('click', () => { currentScenario=null; $('plan-assumptions').hidden=true; $('plan-result').hidden=true; say('Descartado.'); });
$('plan-edit').addEventListener('click', () => { $('plan-result').hidden=true; $('plan-assumptions').hidden=false; });
$('plan-new').addEventListener('click', () => { currentScenario=null; $('plan-assumptions').hidden=true; $('plan-result').hidden=true; $('plan-text').value=''; say(''); });
$('plan-download-scenario').addEventListener('click', () => { if (!currentScenario) return; const url=URL.createObjectURL(new Blob([JSON.stringify({interpretation:currentScenario,calculation:scenarioResult},null,2)],{type:'application/json'})); const a=node('a'); a.href=url; a.download='spendwise-scenario.json'; a.click(); setTimeout(()=>URL.revokeObjectURL(url),1000); });
(async()=>{try{
  config=await api('GET','/api/config');
  $('mode-note').textContent=config.live_available?'Gemini configurado.':'Inicia el servidor con --ask-key para analizar.';
  const now=new Date();$('period-year').value=now.getFullYear();$('period-month').value=now.getMonth()+1;
  const response=await api('GET','/api/profiles');
  response.profiles.forEach(p=>{const option=node('option',p.display_name);option.value=p.id;$('profile-select').append(option);});
  if(config.active_profile){$('profile-select').value=config.active_profile;const p=response.profiles.find(p=>p.id===config.active_profile);$('profile-label').textContent=p?.display_name||'PERFIL';}
}catch(e){say('Error al iniciar: '+e.message);}})();
