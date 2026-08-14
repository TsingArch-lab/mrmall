const APP_VERSION='0.1.6.1';
const $ = (id) => document.getElementById(id);
const apiInput = $('apiBase');
apiInput.value = localStorage.getItem('mall_api_base') || 'http://localhost:8000';
const tokenInput = $('accessToken');
tokenInput.value = localStorage.getItem('mall_access_token') || '';

$('reviewBtn').addEventListener('click', async () => {
  const article = $('article').value.trim();
  const base = apiInput.value.trim().replace(/\/$/, '');
  if (!article) return alert('请先粘贴文章。');
  if (!base) return alert('请填写后端 API 地址。');
  localStorage.setItem('mall_api_base', base);
  localStorage.setItem('mall_access_token', tokenInput.value.trim());
  $('reviewBtn').disabled = true;
  $('status').textContent = '正在执行 Rules…';
  try {
    const resp = await fetch(base + '/api/review', {
      method: 'POST',
      headers: Object.assign({'Content-Type':'application/json'}, tokenInput.value.trim() ? {'Authorization':'Bearer '+tokenInput.value.trim()} : {}),
      body: JSON.stringify({article, content_type:$('contentType').value, verify_facts:false})
    });
    const data = await resp.json();
    if (!resp.ok) {
      const detail = data && data.detail ? data.detail : ('HTTP ' + resp.status + ' 审核失败');
      throw new Error(detail);
    }
    render(data);
    $('status').textContent = '完成';
  } catch (e) {
    $('status').textContent = '失败';
    alert(e.message);
  } finally {
    $('reviewBtn').disabled = false;
  }
});

function render(d){
  $('result').classList.remove('hidden');
  $('judgement').textContent = d.final_judgement;
  $('meta').innerHTML = `类型 ${esc(d.content_type)}<br>Provider ${esc(d.model_provider)} / ${esc(d.model)}<br>Rules ${esc(d.registry_hash.slice(0,22))}…<br>Web ${esc(APP_VERSION)}`;
  $('dimensions').innerHTML = Object.entries(d.dimension_states).map(([k,v])=>`<div class="dim"><b>${esc(k)}</b>${esc(v)}</div>`).join('');
  if(d.core_diagnosis){$('diagnosisWrap').classList.remove('hidden');$('diagnosis').textContent=d.core_diagnosis}else{$('diagnosisWrap').classList.add('hidden')}
  $('issues').innerHTML = d.issues.length ? d.issues.map((x,i)=>`<div class="issue"><strong>${i+1}. ${esc(x.text)}</strong><div class="rule">Rule: ${esc((x.supporting_rule_ids||[]).join(', '))}</div>${(x.article_evidence||[]).map(ev=>`<div class="evidence">${esc(ev)}</div>`).join('')}</div>`).join('') : '<p>当前 Rules 未生成负面问题。</p>';
  const strengthHtml=(d.strengths||[]).map(x=>{
    if(typeof x === 'string') return x.trim() ? `<li>${esc(x)}</li>` : '';
    if(!x || typeof x !== 'object') return '';
    const text=String(x.text||x.summary||x.title||'').trim();
    if(!text) return '';
    const rules=Array.isArray(x.supporting_rule_ids)&&x.supporting_rule_ids.length ? `<div class="rule">Rule: ${esc(x.supporting_rule_ids.join(', '))}</div>` : '';
    const evs=Array.isArray(x.article_evidence)?x.article_evidence:[];
    const evidence=evs.map(ev=>`<div class="evidence">${esc(ev)}</div>`).join('');
    return `<li><strong>${esc(text)}</strong>${rules}${evidence}</li>`;
  }).filter(Boolean).join('');
  $('strengths').innerHTML = strengthHtml || '<li>当前 PASS Rules 未提取出足以在后续修改中主动保护的内容资产。</li>';
  if(d.verification_note){$('verifyNote').classList.remove('hidden');$('verifyNote').textContent=d.verification_note}else{$('verifyNote').classList.add('hidden')}
  $('result').scrollIntoView({behavior:'smooth',block:'start'});
}
function esc(v){return String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
