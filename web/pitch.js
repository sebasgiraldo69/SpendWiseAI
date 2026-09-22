'use strict';
const slides=[...document.querySelectorAll('.slide')];let current=0,remaining=360,running=false,last=0;
function show(index){current=Math.max(0,Math.min(slides.length-1,index));slides.forEach((s,i)=>s.hidden=i!==current);document.getElementById('page').textContent=`${current+1} / ${slides.length}`;}
document.getElementById('previous').onclick=()=>show(current-1);document.getElementById('next').onclick=()=>show(current+1);
document.addEventListener('keydown',e=>{if(e.target.tagName==='BUTTON')return;if(e.key==='ArrowRight'||e.key===' '){e.preventDefault();show(current+1);}if(e.key==='ArrowLeft')show(current-1);});
function display(){const seconds=Math.ceil(remaining);document.getElementById('timer').textContent=String(Math.floor(seconds/60)).padStart(2,'0')+':'+String(seconds%60).padStart(2,'0');document.getElementById('timer-toggle').textContent=running?'Pausar':'Iniciar / continuar';}
document.getElementById('timer-toggle').onclick=()=>{running=!running;last=Date.now();display();};document.getElementById('timer-reset').onclick=()=>{remaining=360;running=false;display();};
setInterval(()=>{if(running){const now=Date.now();remaining=Math.max(0,remaining-(now-last)/1000);last=now;if(!remaining)running=false;display();}},200);
document.getElementById('print').onclick=()=>window.print();
