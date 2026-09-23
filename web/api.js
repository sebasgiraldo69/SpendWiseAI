// One HTTP client, short local requests, cancellable AI jobs and stale-response protection.
let generation = 0;
const requests = new Set();
const jobs = new Map();
export class ApiError extends Error {
  constructor(message,status,code){super(message);this.status=status;this.code=code;}
}
export async function request(method,path,payload,signal){
  const epoch=generation, controller=new AbortController();requests.add(controller);
  const abort=()=>controller.abort();
  if(signal?.aborted)controller.abort();
  signal?.addEventListener('abort',abort,{once:true});
  const timeout=setTimeout(()=>controller.abort('timeout'),8000);
  try{
    const options={method,signal:controller.signal,headers:{'Content-Type':'application/json'}};
    if(payload!==undefined)options.body=JSON.stringify(payload);
    const response=await fetch(path,options);
    const data=await response.json();
    if(epoch!==generation)throw new DOMException('La sesión cambió.','AbortError');
    if(!response.ok)throw new ApiError(data.error||'No se pudo completar la solicitud.',response.status,data.code);
    return data;
  }catch(error){
    if(controller.signal.reason==='timeout')throw new ApiError('El servidor local no respondió. Comprueba que está encendido.',0,'local_timeout');
    throw error;
  }finally{clearTimeout(timeout);requests.delete(controller);signal?.removeEventListener('abort',abort);}
}
export function invalidate(){
  generation++;
  requests.forEach(c=>c.abort());
  jobs.forEach(c=>c.abort());
}
export function cancelAnalysis(){jobs.forEach(c=>c.abort());}
export async function analyze(path,payload,onProgress){
  const controller=new AbortController(),start=Date.now();
  const key=Symbol();jobs.set(key,controller);
  let id,completed=false;
  try{
    const initial=await request('POST',path,payload,controller.signal);id=initial.id;
    let state=initial;
    while(true){
      if(controller.signal.aborted)throw new DOMException('Cancelado.','AbortError');
      if(state.status==='done'){completed=true;return state.result;}
      if(state.status==='error')throw new ApiError(state.error.message,502,state.error.code);
      if(state.status==='cancelled')throw new DOMException('Cancelado.','AbortError');
      if(Date.now()-start>50000)throw new ApiError('El análisis excedió el tiempo disponible. Reintenta.',504,'job_timeout');
      onProgress?.(state.status,Math.floor((Date.now()-start)/1000));
      await new Promise(resolve=>setTimeout(resolve,700));
      state=await request('GET','/api/jobs/'+id,undefined,controller.signal);
    }
  }finally{
    jobs.delete(key);
    if(id&&!completed)request('DELETE','/api/jobs/'+id).catch(()=>{});
    onProgress?.(jobs.size?'running':'finished',0);
  }
}
