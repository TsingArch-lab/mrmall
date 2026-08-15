const APP_VERSION='0.1.9.0-diagnostic';
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
  const startedAt=Date.now();
  const headers=Object.assign({'Content-Type':'application/json'}, tokenInput.value.trim() ? {'Authorization':'Bearer '+tokenInput.value.trim()} : {});
  const stageText={
    QUEUED:'正在排队', STARTING:'正在准备审核', ROUTING:'正在判断文章类型',
    FACT_CHECKING:'正在联网核验关键事实', EVALUATING:'正在执行规则审核', ADJUDICATING:'正在复核未决规则',
    AGGREGATING:'正在汇总规则结果', POSTPROCESSING:'正在整理问题清单与值得保留',
    COMPLETED:'审核完成', FAILED:'审核失败'
  };
  try {
    const createResp=await fetch(base + '/api/review/jobs', {
      method:'POST', headers,
      body:JSON.stringify({article, content_type:$('contentType').value, verify_facts:$('verifyFacts').checked})
    });
    const created=await createResp.json();
    if(!createResp.ok) throw new Error(created && created.detail ? created.detail : ('HTTP '+createResp.status+' 创建审核任务失败'));
    const jobId=created.job_id;
    $('status').textContent='审核任务已创建…';

    while(true){
      await sleep(2000);
      const poll=await fetch(base + '/api/review/jobs/' + encodeURIComponent(jobId), {headers});
      const state=await poll.json();
      if(!poll.ok) throw new Error(state && state.detail ? state.detail : ('HTTP '+poll.status+' 查询审核任务失败'));
      const sec=Math.floor((Date.now()-startedAt)/1000);
      $('status').textContent=`${stageText[state.stage]||state.message||'正在审核'}… ${sec}秒`;
      if(state.status==='completed'){
        render(state.result);
        $('status').textContent=`完成 · ${sec}秒`;
        break;
      }
      if(state.status==='failed') throw new Error(state.message||'审核失败');
    }
  } catch (e) {
    $('status').textContent = '失败';
    const msg=(e && e.message==='Failed to fetch') ? '暂时无法连接审核服务。请确认 Render 服务正常后重试。' : e.message;
    alert(msg);
  } finally {
    $('reviewBtn').disabled = false;
  }
});

function sleep(ms){return new Promise(resolve=>setTimeout(resolve,ms));}

function render(d){
  $('result').classList.remove('hidden');
  $('judgement').textContent = d.final_judgement;
  $('meta').innerHTML = `类型 ${esc(d.content_type)}<br>Provider ${esc(d.model_provider)} / ${esc(d.model)}<br>Rules ${esc(d.registry_hash.slice(0,22))}…<br>Web ${esc(APP_VERSION)}`;
  $('dimensions').innerHTML = Object.entries(d.dimension_states).map(([k,v])=>`<div class="dim"><b>${esc(k)}</b>${esc(v)}</div>`).join('');
  if(d.core_diagnosis){$('diagnosisWrap').classList.remove('hidden');$('diagnosis').textContent=d.core_diagnosis}else{$('diagnosisWrap').classList.add('hidden')}
  $('issues').innerHTML = d.issues.length ? d.issues.map((x,i)=>`<div class="issue"><strong>${i+1}. ${esc(x.text)}</strong><div class="rule">Rule: ${esc((x.supporting_rule_ids||[]).join(', '))}</div>${(x.article_evidence||[]).map(ev=>`<div class="evidence">${esc(ev)}</div>`).join('')}</div>`).join('') : '<p>当前 Rules 未生成负面问题。</p>';
  renderVerification(d);
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

function renderVerification(d){
  const wrap=$('verificationWrap');
  const box=$('verificationResults');
  const rows=Array.isArray(d.verification_results)?d.verification_results:[];
  if((d.verification_state||'NOT_RUN')==='NOT_RUN' && !rows.length){wrap.classList.add('hidden');box.innerHTML='';return;}
  wrap.classList.remove('hidden');
  const labels={confirmed:'已确认',basically_confirmed:'基本确认',questionable:'存疑',no_reliable_source:'未找到可靠依据',contradicted:'明确不符'};
  if(!rows.length){box.innerHTML='<p>已执行事实扫描，但没有需要优先展示的核验结果。</p>';return;}
  const body=rows.map((x,i)=>{
    const status=labels[x.status]||x.status||'未分类';
    const riskLabels={anchor:'基础锚点',named_story:'具名故事',quote:'人物引语',authority_attribution:'权威归属',operating_metric:'经营数据',extreme_claim:'极值表述',other:'其他'};
    const risk=riskLabels[x.risk_tag]||'';
    const warn=x.authority_warning ? '<div class="authority-warning">高风险：权威来源引用存疑/错误</div>' : '';
    const srcs=(Array.isArray(x.sources)?x.sources:[]).map(s=>{
      const url=safeUrl(s.url); const title=String(s.title||url||'来源');
      return url?`<a class="source-link" href="${attr(url)}" target="_blank" rel="noopener noreferrer">${esc(title)}</a>`:'';
    }).filter(Boolean).join('<br>');
    const note=[x.evidence,x.notes].filter(Boolean).map(esc).join('<br>');
    return `<tr class="${x.authority_warning?'verify-row-warning':''}"><td class="verify-index">${i+1}</td><td class="verify-status">${esc(status)}${risk?`<div class="verify-risk">${esc(risk)}</div>`:''}${warn}</td><td>${esc(x.claim||'')}</td><td>${note||'—'}</td><td class="verify-sources">${srcs||'—'}</td></tr>`;
  }).join('');
  box.innerHTML=`<div class="verify-table-wrap"><table class="verify-table"><thead><tr><th>#</th><th>结果</th><th>原文事实</th><th>核验说明</th><th>来源</th></tr></thead><tbody>${body}</tbody></table></div>`;
}
function attr(v){return esc(v).replace(/`/g,'&#96;')}
function safeUrl(v){try{const u=new URL(String(v||''));return (u.protocol==='http:'||u.protocol==='https:')?u.href:''}catch{return ''}}
