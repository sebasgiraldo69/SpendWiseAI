'use strict';
const $ = id => document.getElementById(id);
const money = value => value === null ? 'Sin dato' : new Intl.NumberFormat('es-CO',{style:'currency',currency:'COP',maximumFractionDigits:2}).format(value);
const labels = {vivienda:'Vivienda',alimentacion:'Alimentación',transporte:'Transporte',educacion:'Educación',entretenimiento:'Entretenimiento',otros:'Otros'};
const caseLabels = ['Un mes completo','Sin ingreso registrado','Dos arriendos ambiguos','Instrucción maliciosa','Gastos mayores al ingreso','Ingreso de cero','Montos coloquiales','COP y USD mezclados','Un gasto sin monto','Una devolución','Categoría desconocida'];
let config, review, result, busy = false;
const say = message => { $('notice').textContent = message; };
function node(tag,text,cls){const el=document.createElement(tag);if(text!==undefined)el.textContent=text;if(cls)el.className=cls;return el;}
function show(step){['entry','review','result'].forEach((id,i)=>{$(id).hidden=i!==step-1;$('step'+(i+1)).classList.toggle('active',i===step-1);});}
async function post(path,payload){const controller=new AbortController();const timeout=setTimeout(()=>controller.abort(),50000);try{const response=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload),signal:controller.signal});const body=await response.json();if(!response.ok)throw new Error(body.error||'No se pudo completar la solicitud.');return body;}finally{clearTimeout(timeout);}}
async function task(fn){if(busy)return;busy=true;document.querySelectorAll('button').forEach(b=>b.disabled=true);try{await fn();}catch(e){say(e.name==='AbortError'?'La solicitud tardó demasiado. Vuelve a intentarlo.':e.message);}finally{busy=false;document.querySelectorAll('button').forEach(b=>b.disabled=false);}}
async function forget(){if(review){await post('/api/forget',{token:review.token});review=null;}result=null;}
function modeChanged(){const live=$('mode').value==='live';$('consent-wrap').hidden=!live;$('input').readOnly=!live;$('mode-note').textContent=live?(config.live_available?'Gemini está configurado. Revisa siempre su interpretación.':'Gemini aún no está configurado. Inicia el servidor con --ask-key.'):'Extracciones preparadas manualmente para ensayar la presentación.';}
function exampleChanged(){$('input').value=config.examples[Number($('example').value)].input;}
function renderReview(){
  $('income').value=review.ingreso_total??'';$('confirmed').checked=false;$('rows').replaceChildren();$('issues').replaceChildren();
  $('review-mode').textContent=review.metadata.mode==='fixture'?'ENSAYO SIMULADO':'INTERPRETADO CON GEMINI';
  if(review.incidencias.length){const list=node('ul');review.incidencias.forEach(i=>list.append(node('li',i.detalle)));$('issues').append(list);}
  review.movimientos.forEach(m=>{
    const row=node('tr');row.dataset.id=m.id;
    const include=node('input');include.type='checkbox';include.checked=m.incluir;include.className='include';include.setAttribute('aria-label','Incluir '+m.descripcion);include.disabled=m.tipo==='refund'||m.moneda!=='COP';
    const description=node('input');description.type='text';description.value=m.descripcion;description.className='description';description.maxLength=200;description.setAttribute('aria-label','Descripción de '+m.descripcion);
    const amount=node('input');amount.type='number';amount.min='0';amount.max='1000000000000';amount.step='.01';amount.value=m.valor??'';amount.className='amount';amount.setAttribute('aria-label','Monto de '+m.descripcion);amount.disabled=include.disabled;
    const category=node('select');category.className='category';category.setAttribute('aria-label','Categoría de '+m.descripcion);Object.entries(labels).forEach(([value,text])=>{const opt=node('option',text);opt.value=value;category.append(opt);});category.value=m.categoria;
    const simulate=node('input');simulate.type='checkbox';simulate.className='simulate';simulate.setAttribute('aria-label','Simular reducción de '+m.descripcion);simulate.disabled=!include.checked;
    include.addEventListener('change',()=>{simulate.disabled=!include.checked;if(!include.checked)simulate.checked=false;$('confirmed').checked=false;});
    [description,amount,category,simulate].forEach(el=>el.addEventListener('change',()=>{$('confirmed').checked=false;}));
    [include,description,amount,category,simulate].forEach((el,index)=>{const cell=node('td');cell.append(el);if(index===1){cell.append(node('div','“'+m.fuente+'”','source'));if(m.moneda!=='COP')cell.append(node('div','Moneda original: '+m.moneda,'source'));}row.append(cell);});$('rows').append(row);
  });
  show(2);
}
function renderResult(){
  const output=result.output;$('total-income').textContent=money(output.ingreso_total);$('total-expense').textContent=money(output.gasto_total);$('total-balance').textContent=money(output.saldo_disponible);$('state').textContent=output.estado_financiero;
  $('result-mode').textContent=result.metadata.mode==='fixture'?'ENSAYO SIMULADO · REVISADO POR TI':'DATOS REVISADOS POR TI';
  $('chart').replaceChildren();Object.entries(output.categorias).forEach(([category,value])=>{const row=node('div',undefined,'bar-row');row.append(node('span',labels[category]));const progress=node('progress');progress.max=output.gasto_total||1;progress.value=value;progress.setAttribute('aria-label',labels[category]);row.append(progress,node('span',money(value)));$('chart').append(row);});
  $('percentage').textContent=output.porcentaje_gastado===null?'No hay un ingreso positivo para calcular el porcentaje.':`Gastaste el ${output.porcentaje_gastado.toLocaleString('es-CO')}% de tu ingreso registrado.`;
  $('saving').textContent=money(output.ahorro_potencial);$('recommendation').textContent=output.recomendacion_principal||'No seleccionaste un escenario. Puedes volver y elegir gastos sobre los que quieras simular una reducción.';
  $('opportunities').replaceChildren();output.oportunidades_ahorro.forEach(o=>{const m=result.movimientos_confirmados.find(m=>m.id===o.id);$('opportunities').append(node('li',m.descripcion+': '+money(o.ahorro)+' al reducir 10%.'));});
  $('trace').textContent=JSON.stringify({modo:result.metadata,flujo:['Texto','Extracción estructurada','Validación y dudas','Confirmación humana','Cálculo determinista','Escenario elegido por el usuario'],confirmado:result.human_confirmed,correcciones:result.corregidos,excluidos:result.excluidos,movimientos:result.movimientos_confirmados,output},null,2);show(3);
}
$('extract').addEventListener('click',()=>task(async()=>{await forget();say('Interpretando los movimientos…');const selected=config.examples[Number($('example').value)];review=await post('/api/extract',{input:$('input').value,mode:$('mode').value,case_id:selected.id,consent:$('consent').checked});say('Revisa los datos antes de generar el presupuesto.');renderReview();}));
$('confirm').addEventListener('click',()=>task(async()=>{if(!$('confirmed').checked)throw new Error('Confirma que revisaste los datos y las exclusiones.');const rows=[...$('rows').children];const movements=rows.map(row=>({id:row.dataset.id,descripcion:row.querySelector('.description').value,valor:row.querySelector('.amount').value===''?null:Number(row.querySelector('.amount').value),categoria:row.querySelector('.category').value,incluir:row.querySelector('.include').checked}));result=await post('/api/confirm',{token:review.token,confirmed:true,ingreso_total:$('income').value===''?null:Number($('income').value),movimientos:movements,selected_ids:rows.filter(row=>row.querySelector('.simulate').checked).map(row=>row.dataset.id)});say('Presupuesto calculado y validado.');renderResult();}));
$('back').addEventListener('click',()=>task(async()=>{await forget();show(1);say('Edita la entrada y vuelve a interpretarla.');}));
$('edit-review').addEventListener('click',()=>{$('confirmed').checked=false;show(2);say('Confirma de nuevo después de ajustar los movimientos.');});
$('income').addEventListener('input',()=>{$('confirmed').checked=false;});
$('restart').addEventListener('click',()=>task(async()=>{await forget();show(1);say('Se eliminó la revisión del servidor.');$('trace').textContent='';$('rows').replaceChildren();}));
$('download').addEventListener('click',()=>{if(!result)return;const url=URL.createObjectURL(new Blob([JSON.stringify(result,null,2)],{type:'application/json'}));const a=node('a');a.href=url;a.download='spendwise-'+result.metadata.mode+'.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);});
$('mode').addEventListener('change',modeChanged);$('example').addEventListener('change',exampleChanged);
(async()=>{try{const response=await fetch('/api/config');if(!response.ok)throw new Error('No se pudo cargar la configuración.');config=await response.json();config.examples.forEach((example,index)=>{const option=node('option',caseLabels[index]||example.id);option.value=index;$('example').append(option);});exampleChanged();modeChanged();}catch(e){say('No se pudo iniciar la aplicación: '+e.message);$('extract').disabled=true;}})();
