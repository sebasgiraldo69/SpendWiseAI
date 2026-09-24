// Conversation stays in this page; nothing is saved to browser storage.
let chatHistory = [], chatController = null, chatEpoch = 0;
async function loadPlanOptions() {
  try {
    const selected = $('plan-budget').value;
    const data = await api('GET', '/api/budgets');
    const select = $('plan-budget');
    select.replaceChildren(new Option('Sin presupuesto seleccionado', ''));
    for (const b of data.budgets || []) select.add(new Option(`${monthNames[b.month-1]} ${b.year}`, b.id));
    select.value = selected;
    if (!select.value && selected) resetChat();
  } catch (e) { $('chat-status').textContent = 'No se pudieron cargar los presupuestos. Puedes conversar sin seleccionar uno.'; }
}
function chatBubble(role, text) {
  const bubble = node('article', undefined, 'chat-message chat-' + role);
  bubble.append(node('strong', role === 'user' ? 'Tú' : 'SpendWise'), node('p', text));
  $('chat-messages').append(bubble);
  bubble.scrollIntoView({block:'nearest', behavior:'smooth'});
  return bubble;
}
function setChatBusy(value) {
  $('chat-send').disabled = value;
  $('chat-cancel').hidden = !value;
  $('chat-text').disabled = value;
  $('chat-messages').setAttribute('aria-busy', String(value));
}
function resetChat() {
  chatEpoch++;
  chatController?.abort(); chatController = null;
  chatHistory = [];
  $('chat-messages').replaceChildren();
  $('chat-text').value = ''; $('chat-status').textContent = '';
  setChatBusy(false);
  chatBubble('assistant', 'Cuéntame qué te gustaría mejorar: ahorrar más, ajustar algún gasto o preparar un evento. Podemos ir paso a paso. Si seleccionas un mes, usaré sus gastos para proponerte ajustes concretos.');
}
function showProposal(bubble, proposal) {
  const card = node('div', undefined, 'chat-proposal');
  card.append(node('strong', 'Propuesta para revisar'));
  proposal.reductions.forEach(r => card.append(node('p', `${r.description}: reducir ${money(r.reduce_by)} de ${money(r.current_amount)}.`)));
  proposal.event_items.forEach(i => card.append(node('p', `${i.description}: ${money(i.estimated_amount)} (estimación por confirmar).`)));
  const button = node('button', 'Revisar simulación'); button.type = 'button';
  button.addEventListener('click', () => {
    const result = node('div');
    result.append(node('p', `Ahorro adicional propuesto: ${money(proposal.saving)}.`));
    if (proposal.estimated) result.append(node('p', `Costo estimado del evento: ${money(proposal.event_total)}.`));
    result.append(node('p', `Saldo del mes tras estos ajustes${proposal.estimated ? ' y el evento' : ''}: ${money(proposal.remaining)}.`));
    if (proposal.remaining !== null && proposal.remaining < 0) result.append(node('p', 'La propuesta deja un saldo negativo. Podemos ajustar el plan.'));
    result.append(node('p', 'Simulación calculada con el presupuesto de referencia. No se han modificado tus datos guardados.', 'hint'));
    button.replaceWith(result);
  });
  card.append(button); bubble.append(card);
}
$('chat-form').addEventListener('submit', async event => {
  event.preventDefault();
  if (chatController) return;
  const text = $('chat-text').value.trim();
  if (!text) return;
  if (!$('chat-consent').checked) { $('chat-status').textContent = 'Autoriza el envío antes de conversar.'; return; }
  if (chatHistory.length >= 20) { $('chat-status').textContent = 'Llegaste a 10 intercambios. Inicia una nueva conversación para continuar.'; return; }
  const controller = new AbortController(), epoch = chatEpoch;
  chatController = controller; setChatBusy(true);
  const pending = chatBubble('user', text);
  $('chat-status').textContent = 'SpendWise está preparando una respuesta…';
  const timer = setTimeout(() => controller.abort(), 45000);
  try {
    const response = await fetch('/api/plan/chat', {method:'POST', headers:{'Content-Type':'application/json'},
      signal:controller.signal, body:JSON.stringify({text, history:chatHistory, budget_id:$('plan-budget').value || null, consent:true})});
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'No se pudo completar la respuesta.');
    if (epoch !== chatEpoch) return;
    chatHistory.push({role:'user',content:text}, {role:'assistant',content:data.history_reply || data.reply});
    const bubble = chatBubble('assistant', data.reply);
    if (data.proposal) showProposal(bubble, data.proposal);
    $('chat-text').value = ''; $('chat-status').textContent = '';
  } catch (e) {
    if (epoch !== chatEpoch) return;
    pending.remove();
    $('chat-status').textContent = e.name === 'AbortError' ? 'Solicitud cancelada o sin respuesta a tiempo. Tu mensaje sigue listo para reenviar.' : e.message;
  } finally {
    clearTimeout(timer);
    if (epoch === chatEpoch) { chatController = null; setChatBusy(false); $('chat-text').focus(); }
  }
});
$('chat-new').addEventListener('click', resetChat);
$('plan-budget').addEventListener('change', resetChat);
$('chat-cancel').addEventListener('click', () => chatController?.abort());
resetChat();
