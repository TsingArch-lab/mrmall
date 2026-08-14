const $ = (id) => document.getElementById(id);
const apiInput = $('apiBase');
apiInput.value = localStorage.getItem('mall_api_base') || 'https://mrmall-api.onrender.com';
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
    if (!resp.ok) throw new Error(data.detail || '审核失败');
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
  $('meta').innerHTML = `类型 ${esc(d.content_type)}<br>Provider ${esc(d.model_provider)} / ${esc(d.model)}<br>Rules ${esc(d.registry_hash.slice(0,22))}…`;
  $('dimensions').innerHTML = Object.entries(d.dimension_states).map(([k,v])=>`<div class="dim"><b>${esc(k)}</b>${esc(v)}</div>`).join('');
  if(d.core_diagnosis){$('diagnosisWrap').classList.remove('hidden');$('diagnosis').textContent=d.core_diagnosis}else{$('diagnosisWrap').classList.add('hidden')}
  $('issues').innerHTML = d.issues.length ? d.issues.map((x,i)=>`<div class="issue"><strong>${i+1}. ${esc(x.text)}</strong><div class="rule">Rule: ${esc((x.supporting_rule_ids||[]).join(', '))}</div>${(x.article_evidence||[]).map(ev=>`<div class="evidence">${esc(ev)}</div>`).join('')}</div>`).join('') : '<p>当前 Rules 未生成负面问题。</p>';
  $('strengths').innerHTML = (d.strengths||[]).map(x=>`<li>${esc(x)}</li>`).join('') || '<li>暂无。</li>';
  if(d.verification_note){$('verifyNote').classList.remove('hidden');$('verifyNote').textContent=d.verification_note}else{$('verifyNote').classList.add('hidden')}
  $('result').scrollIntoView({behavior:'smooth',block:'start'});
}
function esc(v){return String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
