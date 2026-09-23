"""Bounded in-process AI jobs; all state is owned by the ASGI event loop."""
import asyncio
import hashlib
import json
import secrets
import time
from spendwise_provider import ProviderError

class JobManager:
    def __init__(self, concurrency=2, capacity=8, deadline=40):
        self.jobs = {}
        self.semaphore = asyncio.Semaphore(concurrency)
        self.capacity, self.deadline = capacity, deadline

    def submit(self, owner, kind, payload, operation):
        self.prune()
        fingerprint=hashlib.sha256(json.dumps([kind,payload],sort_keys=True).encode()).hexdigest()
        for job in self.jobs.values():
            if job['owner']==owner and job['fingerprint']==fingerprint and job['status'] in ('queued','running','done') and time.monotonic()-job['created']<120:
                return self.public(job)
        if sum(j['status'] in ('queued','running') for j in self.jobs.values())>=self.capacity:
            raise ProviderError('Hay varios análisis en curso. Intenta en unos segundos.', 'queue_full', True)
        if sum(j['owner']==owner and j['status'] in ('queued','running') for j in self.jobs.values())>=2:
            raise ProviderError('Ya tienes dos análisis en curso. Espera o cancela uno.', 'queue_full', True)
        identifier=secrets.token_urlsafe(24)
        job={'id':identifier,'owner':owner,'kind':kind,'fingerprint':fingerprint,
             'created':time.monotonic(),'status':'queued','result':None,'error':None}
        self.jobs[identifier]=job
        job['task']=asyncio.create_task(self._run(job,operation))
        return self.public(job)

    async def _run(self,job,operation):
        try:
            async def execute():
                async with self.semaphore:
                    job['status']='running'
                    job['result']=await operation()
                    job['status']='done'
            await asyncio.wait_for(execute(),timeout=self.deadline)
        except asyncio.CancelledError:
            job.update(status='cancelled',result=None)
        except asyncio.TimeoutError:
            job.update(status='error',error={'code':'job_timeout','message':'El análisis superó el tiempo disponible. Reintenta con menos texto.','retryable':True})
        except ProviderError as exc:
            job.update(status='error',error={'code':exc.code,'message':str(exc),'retryable':exc.retryable})
        except (ValueError,TypeError,KeyError):
            job.update(status='error',error={'code':'invalid_response','message':'La interpretación no cumple el contrato. Revisa la entrada e intenta de nuevo.','retryable':True})
        except Exception:
            job.update(status='error',error={'code':'internal_error','message':'No se pudo completar el análisis.','retryable':False})

    def public(self,job):
        return {k:job[k] for k in ('id','kind','status','result','error')} | {'elapsed_ms':round((time.monotonic()-job['created'])*1000)}

    def get(self,identifier,owner):
        self.prune()
        job=self.jobs.get(identifier)
        if not job or job['owner']!=owner: return None
        return self.public(job)

    def cancel(self,identifier,owner):
        job=self.jobs.get(identifier)
        if not job or job['owner']!=owner: return False
        job['task'].cancel()
        job.update(status='cancelled',result=None)
        return True

    def clear_owner(self,owner):
        for identifier in list(self.jobs):
            if self.jobs[identifier]['owner']==owner:
                self.cancel(identifier,owner)
                del self.jobs[identifier]

    def prune(self):
        for identifier in list(self.jobs):
            job=self.jobs[identifier]
            if time.monotonic()-job['created']>300:
                job['task'].cancel()
                del self.jobs[identifier]

    async def close(self):
        tasks=[j['task'] for j in self.jobs.values()]
        for task in tasks:task.cancel()
        await asyncio.gather(*tasks,return_exceptions=True)
        self.jobs.clear()
