'use strict';
const screen = document.querySelector('#screen'), error = document.querySelector('#error');
let info, token = '', state, busy = false, pendingAnswer = null;
const node = (tag, text, cls) => { const el = document.createElement(tag); if (text !== undefined) el.textContent = text; if (cls) el.className = cls; return el; };
const button = (text, action, cls) => { const el = node('button', text, cls); el.type = 'button'; el.onclick = action; return el; };
function showError(e) { error.hidden = false; error.textContent = e.message; }
function clearError() { error.hidden = true; }
async function api(path, data, retryCsrf = true) {
  const headers = {'Content-Type':'application/json','X-CSRF-Token':info.csrf};
  if (token) headers['X-Session-Token'] = token;
  let r;
  try { r = await fetch(path, {method:'POST',headers,body:JSON.stringify(data)}); }
  catch (_) { document.querySelector('#connection').textContent = '本机服务暂时不可达 · 此题尚未确认保存'; throw Error('未收到保存确认。请保持页面打开、恢复本机服务后重试。不会跳到下一题。'); }
  const result = await r.json();
  if (!r.ok && retryCsrf && r.status === 400 && result.error === '请求来源或 CSRF 校验失败') {
    const refreshed = await fetch('/api/info');
    if (refreshed.ok) { info = await refreshed.json(); return api(path, data, false); }
  }
  if (!r.ok) throw Error(result.error);
  document.querySelector('#connection').textContent = '本机 SQLite 在线 · 每题收到保存确认后继续';
  return result;
}
async function act(action) {
  if (busy) return; busy = true; clearError();
  document.querySelectorAll('button').forEach(b => b.disabled = true);
  try { await action(); } catch (e) { if (pendingAnswer && state?.question) render(); showError(e); }
  finally { busy = false; document.querySelectorAll('button').forEach(b => b.disabled = false); }
}
function check(text) {
  const l = node('label', undefined, 'check'), c = document.createElement('input'); c.type = 'checkbox'; l.append(c,node('span',text)); return [l,c];
}
function landing() {
  state = null; token = ''; pendingAnswer = null;
  screen.replaceChildren(); document.querySelector('#actions').hidden = true;
  const panel = node('div', undefined, 'panel'); panel.append(node('h2','开始前，请阅读体验说明'));
  panel.append(node('p', info.consent.text, 'consent'));
  const [a,adult] = check('我已年满 18 岁'), [v,voluntary] = check('我自愿体验，可以跳过、暂停或撤回'), [d,demo] = check('我理解这是合成演示，不是正式真人研究');
  panel.append(a,v,d,button('建立匿名演示会话', () => act(async () => {
    if (!adult.checked || !voluntary.checked || !demo.checked) throw Error('请确认全部体验条件后继续。');
    const result = await api('/api/session',{adult:true,voluntary:true,demo_understood:true,consent_hash:info.consent_hash});
    token = result.token; showToken('已建立匿名会话。先保存恢复/撤回码，再开始。',true);
  })));
  const resume = node('div', undefined, 'panel'), input = document.createElement('input'); input.type='password'; input.autocomplete='off'; input.id='resume-code';
  const label = node('label','已有会话？输入恢复/撤回码'); label.htmlFor=input.id;
  resume.append(node('h2','从上次继续'),label,input,button('恢复会话', () => act(async () => {
    token = input.value.trim(); state = await api('/api/state',{resume:true}); pendingAnswer=null; render();
  }), 'secondary'),button('用此码撤回并删除', () => act(async () => {
    token = input.value.trim(); await removeSession();
  }), 'danger'));
  screen.append(panel,resume);
}
function downloadToken() {
  const blob = new Blob([`BITE Collect SYNTHETIC DEMO\n恢复/撤回码：${token}\n仅用于本机数据库；请私下保存，勿交给下一位体验者。\n`],{type:'text/plain;charset=utf-8'});
  const a = document.createElement('a'), url = URL.createObjectURL(blob); a.href=url; a.download='bite-collect-private-resume-code.txt'; a.click(); setTimeout(()=>URL.revokeObjectURL(url),1000);
}
function showToken(title, start=false) {
  screen.replaceChildren(); document.querySelector('#actions').hidden=false;
  const p=node('div',undefined,'panel'); p.append(node('h2',title),node('p','此码用于恢复和撤回。浏览器刷新后请重新输入；不要把它留给下一位体验者。','small'),node('p',token,'token'),button('下载恢复码',downloadToken,'secondary'));
  if (!state || state.status !== 'complete') p.append(button(start?'已保存恢复码，开始比较':'继续此会话',()=>act(load)));
  if (state?.status === 'complete') p.append(node('p',`匿名会话：${state.user_id} · 58 / 58 已保存`));
  screen.append(p);
}
async function load() { state=await api('/api/state',{resume:true}); render(); }
function food(f,label) {
  const card=node('div',undefined,'food'); card.append(node('div',label,'letter'),node('h3',f.name_zh),node('div',f.serving_description,'portion'),node('p',f.description)); return card;
}
function seen(label,id) {
  const l=node('label',label), s=document.createElement('select'); s.id=id; l.htmlFor=id;
  for (const [value,text] of [['','不回答 / 不确定'],['yes','吃过'],['no','没吃过']]) { const o=node('option',text); o.value=value; s.append(o); }
  l.append(s); return [l,s];
}
async function save(answer) {
  // Retain the exact payload for retry if commit succeeded but acknowledgement was lost.
  if (!pendingAnswer) pendingAnswer={question_id:state.question.question_id,answer};
  await api('/api/answer',pendingAnswer);
  const fresh=await api('/api/state',{}); state=fresh; pendingAnswer=null; render();
}
function render() {
  screen.replaceChildren(); document.querySelector('#actions').hidden=false;
  if (state.status === 'complete') { showToken('全部完成。谢谢你的演示体验。'); return; }
  if (state.status === 'paused') { showToken('会话已暂停，回答保存在本机。'); return; }
  const q=state.question, p=node('div',undefined,'panel');
  const progress=node('div',undefined,'progress'); progress.append(node('span',q.kind==='pair'?'预期美味 · 成对比较':'预期美味 · 直接评分'),node('span',`${state.answered} / 58 已保存`));
  const bar=document.createElement('progress'); bar.max=58; bar.value=state.answered; bar.setAttribute('aria-label','已保存进度');
  p.append(progress,bar);
  if (pendingAnswer) p.append(node('p','上一回答尚未收到完整确认。请先重试，原选择会被保留。','small'),button('重试保存原回答',()=>act(()=>save(pendingAnswer.answer))));
  else if (q.kind==='pair') {
    p.append(node('h2','只考虑预期好吃程度，你更想吃哪一种？'),node('p','不考虑热量、价格和健康；没有试吃。可选差不多 / 无法判断，也可跳过。','small'));
    const cards=node('div',undefined,'cards'), left=food(q.left,'左 · A'),right=food(q.right,'右 · B');
    const [ll,ls]=seen('左边的食物，你以前吃过吗？（自愿）','seen-left'),[rl,rs]=seen('右边的食物，你以前吃过吗？（自愿）','seen-right');
    const hunger=document.createElement('select'); hunger.id='hunger';
    const empty=node('option','不回答'); empty.value=''; hunger.append(empty);
    for(let i=0;i<=10;i++){const o=node('option',`${i}${i===0?' · 完全不饿':i===10?' · 很饿':''}`);o.value=String(i);hunger.append(o);}
    const hl=node('label','当下饥饿程度（自愿，0–10）');hl.htmlFor='hunger';hl.append(hunger);
    const answer=choice=>({choice,seen_left:ls.value===''?null:ls.value==='yes',seen_right:rs.value===''?null:rs.value==='yes',self_reported_hunger:hunger.value===''?null:Number(hunger.value)});
    left.append(ll,button('更想吃左边',()=>act(()=>save(answer('left')))));
    right.append(rl,button('更想吃右边',()=>act(()=>save(answer('right'))))); cards.append(left,right);
    p.append(hl,cards);const controls=node('div',undefined,'row'); controls.append(button('差不多 / 无法判断',()=>act(()=>save(answer('tie'))),'secondary'),button('跳过此题',()=>act(()=>save(answer('skip'))),'secondary')); p.append(controls);
  } else {
    p.append(node('h2','你预计它有多好吃？'),node('p','0 = 完全不想吃，10 = 极其期待。请主动选择一个分数，没有默认评分。','small'),food(q.food,'训练锚点 · 预期美味'));
    let rating=null; const options=node('div',undefined,'rating-options');
    for(let i=0;i<=10;i++) options.append(button(String(i),e=>{rating=i; options.querySelectorAll('button').forEach(b=>{b.classList.remove('selected');b.setAttribute('aria-pressed','false');});e.currentTarget.classList.add('selected');e.currentTarget.setAttribute('aria-pressed','true');},'secondary'));
    p.append(options,button('保存评分并继续',()=>act(async()=>{if(rating===null)throw Error('请选择 0–10 的分数，或跳过此题。'); await save({rating,skip:false});})),button('跳过评分',()=>act(()=>save({rating:null,skip:true})),'secondary'));
  }
  screen.append(p);
}
async function removeSession() {
  if (!confirm('删除此会话的本机回答与说明确认记录？已导出或备份的副本需要操作者另行删除。')) return;
  await api('/api/withdraw',{confirm:true}); token=''; pendingAnswer=null; landing(); document.querySelector('#connection').textContent='此会话的本机记录已删除';
}
document.querySelector('#pause').onclick=()=>act(async()=>{if(pendingAnswer)throw Error('请先重试未确认的回答，再暂停。');await api('/api/pause',{});state=await api('/api/state',{});showToken('会话已暂停，已确认的回答保存在本机。');});
document.querySelector('#next').onclick=()=>act(async()=>{if(pendingAnswer)throw Error('请先重试未确认的回答，再交给下一位。');if(token)await api('/api/pause',{});landing();});
document.querySelector('#withdraw').onclick=()=>act(removeSession);
(async()=>{try{const r=await fetch('/api/info'); if(!r.ok)throw Error('本机服务不可用');info=await r.json();document.querySelector('#connection').textContent='本机 SQLite 在线 · 正式真人采集关闭';landing();}catch(e){showError(e);}})();
