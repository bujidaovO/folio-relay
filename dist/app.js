'use strict';
const $=s=>document.querySelector(s);
const escapeHtml=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const e=escapeHtml;
const stamp=(week,day)=>`W${String(week).padStart(2,'0')}D${String(day).padStart(2,'0')}`;
const weekName=week=>`Week ${String(week).padStart(2,'0')}`;
const titles={overview:'项目概览',goals:'项目目标',week:'当前周',weeks:'周记录',collaboration:'协作说明',locations:'文件位置'};
const reportFields={completed:'实际完成',verification:'验证结果',understanding:'关键理解',issues:'问题与处理',codeState:'代码与 Git',nextStep:'下一步位置'};
const handoffFields={summary:'周交接概述',completed:'本周实际完成',verification:'验证结论',projectState:'周末项目状态',openItems:'未完成与遗留问题',notes:'需要保留的信息',nextStep:'下周起点'};
let workspace={schemaVersion:2,projects:[]},active='',selectedWeek=null,page='overview',bundleEtag=null,saving=false,toastTimer,focusDay=null,focusSection=null,focusStage=null;
const folds=new Map();
const roleScenes=new Map();
const locationCache=new Map();
let locationRequest=0,collaborationRequest=0;
const entry=()=>workspace.projects.find(p=>p.id===active);
const meta=()=>entry()?.files['project.json'].data;
const allWeeks=()=>Object.entries(entry()?.files||{}).filter(([,f])=>f.data.kind==='week').map(([path,f])=>({path,...f})).sort((a,b)=>b.data.week-a.data.week);
const weekEntry=(week=selectedWeek)=>allWeeks().find(f=>f.data.week===week);
const handoffEntry=(week=selectedWeek)=>{const w=weekEntry(week);if(!w)return null;const path=w.path.replace('.json','-handoff.json');return {path,...entry().files[path]};};
const currentWeek=()=>weekEntry(meta().current.week);
const currentDay=()=>currentWeek().data.days.find(d=>d.day===meta().current.day);
const roadmapEntry=()=>entry()?.files['roadmap.json'];
const stageFor=week=>roadmapEntry()?.data.stages.find(stage=>stage.id===week.stageId);
function allWeeklyGoals(){
  const plans=new Map((roadmapEntry()?.data.weeklyPlans||[]).map(plan=>[plan.week,{...plan,record:null,status:plan.condition?'按需计划':'计划'}]));
  for(const record of allWeeks()){
    const week=record.data.week,plan=plans.get(week)||{};
    plans.set(week,{...plan,week,title:plan.title||'周目标',goals:record.data.goals,stageId:record.data.stageId,status:record.data.status,record});
  }
  return Array.from(plans.values()).map(plan=>({...plan,current:plan.week===meta().current.week,ongoing:plan.status==='进行中'}));
}
function monthGoalGroups(plans=allWeeklyGoals()){
  const groups=new Map();
  for(const plan of plans){const month=Math.floor((plan.week-1)/4)+1;if(!groups.has(month))groups.set(month,{month,weeks:[],ongoing:false});const group=groups.get(month);group.weeks.push(plan);group.ongoing ||= plan.ongoing;}
  for(const group of groups.values())group.weeks.sort((a,b)=>Number(b.ongoing)-Number(a.ongoing)||Number(b.current)-Number(a.current)||b.week-a.week);
  return Array.from(groups.values()).sort((a,b)=>Number(b.ongoing)-Number(a.ongoing)||b.month-a.month);
}
const button=(label,action,primary=false)=>`<button type="button" class="${primary?'primary':''}" data-action="${action}">${label}</button>`;
const badge=status=>`<span class="badge ${status==='已完成'?'green':status==='进行中'?'blue':['休息','计划','按需计划'].includes(status)?'gray':'amber'}">${e(status)}</span>`;
function toast(message){$('#toast').textContent=message;$('#toast').classList.add('show');clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('#toast').classList.remove('show'),3600);}
function storageStatus(message,error=false){$('#storage-status').textContent=message;$('#storage-status').classList.toggle('error',error);}
async function api(path,options={}){const response=await fetch(path,options);const result=await response.json();if(!response.ok)throw Error(result.error||'本地资料操作失败');return {data:result,etag:response.headers.get('ETag')};}
async function load(quiet=false){
  const requested=bundleEtag;
  const response=await fetch('/api/workspace',{cache:'no-store',headers:quiet&&bundleEtag?{'If-None-Match':bundleEtag}:{}});
  if(response.status===304){storageStatus('已连接本地 JSON');return;}
  const data=await response.json();if(!response.ok)throw Error(data.error||'无法读取 JSON');
  if(data.schemaVersion!==2||!Array.isArray(data.projects))throw Error('本地资料结构不是版本 2');
  if(quiet&&(saving||$('#modal').open||requested!==bundleEtag))return;
  workspace=data;bundleEtag=response.headers.get('ETag');
  if(!entry())active=workspace.projects[0]?.id||'';
  if(meta()&&!weekEntry())selectedWeek=meta().current.week;
  storageStatus('已连接本地 JSON');render();if(quiet)toast('已读取文件中的新记录');
}
async function saveFile(path,data,expected){
  saving=true;storageStatus('正在保存 JSON…');
  try{await api(`/api/projects/${active}/files/${path}`,{method:'PUT',headers:{'Content-Type':'application/json','If-Match':expected},body:JSON.stringify(data)});await load();storageStatus('已保存到本地 JSON');return true;}
  catch(error){storageStatus('保存未完成',true);toast(error.message);return false;}finally{saving=false;}
}
function route(target,week=null){if(week!==null)selectedWeek=Number(week);const hash='#'+target;if(location.hash===hash)render();else location.hash=hash;}
function foldAttrs(key,initial=false,week=selectedWeek){const full=JSON.stringify([active,page,week,key]);return `data-fold="${e(full)}" ${folds.has(full)?folds.get(full)?'open':'':initial?'open':''}`;}
function plain(value){return e(value||'尚未记录').replace(/\n/g,'<br>');}
function goals(items){return items.length?`<ol class="goals">${items.map(goal=>`<li>${e(goal)}</li>`).join('')}</ol>`:'<p class="muted">尚未填写目标</p>';}
function render(){
  const aliases={requirements:'week',changes:'week',structure:'overview',context:'overview',history:'weeks',handoff:'weeks'};
  const hash=location.hash.slice(1);page=aliases[hash]|| (titles[hash]?hash:'overview');
  $('#project-select').innerHTML=workspace.projects.map(p=>`<option value="${e(p.id)}" ${p.id===active?'selected':''}>${e(p.name)}</option>`).join('');
  $('#nav').innerHTML=Object.entries(titles).map(([id,title])=>`<a href="#${id}" data-nav="${id}" class="${page===id?'active':''}">${title}</a>`).join('');
  $('#breadcrumb').textContent=meta()?.name||'本地项目';$('#page-title').textContent=titles[page];$('#page-actions').innerHTML='';
  $('#notice').hidden=!meta()?.readOnly;$('#notice').innerHTML=meta()?.readOnly?'只读试用项目':'';
  if(!meta()){$('#view').innerHTML=`<div class="card empty"><h2>开始一个本地项目</h2><p>计划、日交接和周交接都保存为 JSON 文件。</p>${button('新建项目','new-project',true)}</div>`;return;}
  if(!weekEntry())selectedWeek=meta().current.week;
  ({overview:renderOverview,goals:renderGoals,week:renderWeek,weeks:renderWeeks,collaboration:renderCollaboration,locations:renderLocations})[page]();
}
async function renderCollaboration(){
  const id=active,p=meta(),roles=p.agentRoles||[],request=++collaborationRequest;
  $('#view').innerHTML='<div class="card padded"><p>正在读取角色文件位置…</p></div>';
  try{
    const result=await api(`/api/projects/${id}/locations`);
    if(active!==id||page!=='collaboration'||request!==collaborationRequest)return;
    locationCache.set(id,result.data);
    $('#view').innerHTML=`<p class="collaboration-intro">选好角色和本次场景，文件清单会标明必读、按需、用途与读取时机。</p>${roles.length?`<div class="role-list">${roles.map(role=>{
      const plan=ReadingPlan.build(role,result.data,roleScenes.get(JSON.stringify([id,role.id])));
      const groups=[['必读文件',plan.required],['按需文件',plan.optional]].filter(([,items])=>items.length);
      return `<article class="card padded role-card"><div class="card-heading"><h2>${e(role.title)}</h2></div><p>${e(role.summary)}</p><label class="role-scene">本次场景<select data-role-scenario="${e(role.id)}" aria-label="${e(role.title)}的使用场景">${ReadingPlan.scenarios(role).map(scene=>`<option value="${e(scene.id)}" ${scene.id===plan.scenario.id?'selected':''}>${e(scene.title)}</option>`).join('')}</select></label><p class="scene-description">${e(plan.scenario.description)}</p><div class="role-actions">${button('复制启动消息','copy-role:'+role.id,true)}${button('复制文件位置','copy-role-paths:'+role.id)}</div><details class="role-files" ${foldAttrs('role-files:'+role.id,false,0)}><summary>所需文件 · 必读 ${plan.required.length}${plan.optional.length?' / 按需 '+plan.optional.length:''}</summary><div>${groups.map(([title,items])=>`<div class="reading-group-title">${title}</div>${items.map(locationRow).join('')}`).join('')}</div></details><details ${foldAttrs('role:'+role.id,false,0)}><summary>查看职责与流程</summary><div class="role-sections">${role.sections.map(section=>`<section><h3>${e(section.title)}</h3>${goals(section.items)}</section>`).join('')}</div></details></article>`;
    }).join('')}</div>`:'<div class="card empty"><h2>还没有角色说明</h2><p>可在项目 JSON 的 agentRoles 中整理执行、管理或其他协作角色。</p></div>'}${p.collaboration?.length?`<details class="card padded common-collaboration" ${foldAttrs('common-collaboration',false,0)}><summary>通用协作约定</summary>${goals(p.collaboration)}</details>`:''}`;
  }catch(error){
    if(active!==id||page!=='collaboration'||request!==collaborationRequest)return;
    $('#view').innerHTML=`<div class="card padded"><h2>无法读取角色文件位置</h2><p>${e(error.message)}</p></div>`;
  }
}
async function roleContext(id){
  const projectId=active,p=meta(),role=p.agentRoles?.find(role=>role.id===id);
  if(!role)throw Error('请先选择有效的角色');
  const sceneId=roleScenes.get(JSON.stringify([projectId,role.id]));
  const result=await api(`/api/projects/${projectId}/locations`);
  return {p,role,plan:ReadingPlan.build(role,result.data,sceneId)};
}
async function copyRolePaths(id){
  const {plan}=await roleContext(id);
  return copyText(ReadingPlan.fileList(plan),'文件用途与位置已复制');
}
async function copyRole(id){
  const {p,role,plan}=await roleContext(id);
  return copyText(ReadingPlan.startupMessage(p,role,plan),'场景、文件用途与启动消息已复制');
}
async function renderLocations(){
  const id=active,request=++locationRequest;
  $('#page-actions').innerHTML=button('刷新位置','refresh-locations');
  $('#view').innerHTML='<div class="card padded"><p>正在读取实际文件位置…</p></div>';
  try{
    const result=await api(`/api/projects/${id}/locations`);
    if(active!==id||page!=='locations'||request!==locationRequest)return;
    locationCache.set(id,result.data);
    paintLocations(result.data);
  }catch(error){
    if(active!==id||page!=='locations'||request!==locationRequest)return;
    $('#view').innerHTML=`<div class="card padded"><h2>无法读取文件位置</h2><p>${e(error.message)}</p></div>`;
  }
}
function locationRow(item){
  const priority=item.requirement?`<span class="reading-priority ${item.requirement==='必读'?'required':'optional'}">${e(item.requirement)}</span>`:'';
  return `<article class="location-row" data-location="${e(item.key)}"><div class="location-description"><h3>${e(item.label)}${priority}</h3><p>用途：${e(item.note)}</p>${item.requirement==='按需'?`<p class="reading-when">何时读：${e(item.when)}</p>`:''}</div><div class="location-path-line">${item.path?`<code>${e(item.path)}</code>`:''}${item.exists?`<div class="location-buttons">${button(item.kind==='directory'?'打开文件夹':'打开文件','open-location:'+item.key)}${button('复制路径','copy-location:'+item.key)}</div>`:`<span class="muted">${e(item.unavailable||'目前不存在')}</span>`}</div></article>`;
}
function paintLocations(data){
  $('#page-actions').innerHTML=button('刷新位置','refresh-locations')+button('复制交接路径','copy-handoff-paths',true);
  const previous=data.reading_files.some(item=>item.key==='previous-handoff');
  const folders=data.other_locations.filter(item=>['active-directory','backup-directory'].includes(item.key));
  const others=data.other_locations.filter(item=>!folders.includes(item));
  $('#view').innerHTML=`<div class="card padded location-root"><div class="card-heading"><h2>项目资料目录</h2><div class="location-buttons">${button('打开文件夹','open-location:project-directory')}${button('复制目录','copy-record-directory')}</div></div><code class="root-path">${e(data.project_directory)}</code><p>整项目迁移时复制此目录，包含正在使用文件和备份资料。</p></div><div class="card location-list">${folders.map(locationRow).join('')}</div><div class="section-heading"><h2>交接常用文件</h2></div><div class="card location-list">${data.reading_files.map(locationRow).join('')}${previous?'':'<div class="location-empty"><h3>上周最终交接</h3><p>当前没有已完成的历史周交接。</p></div>'}</div>${others.length?`<details class="card padded additional-locations" ${foldAttrs('additional-locations',false,0)}><summary>其他资料位置</summary><div>${others.map(locationRow).join('')}</div></details>`:''}`;
}
async function copyText(value,message='已复制'){
  try{if(window.pywebview?.api)await window.pywebview.api.copy_text(value);else await navigator.clipboard.writeText(value);toast(message);}catch{modal('手动复制',`<textarea class="copy-text-view" readonly aria-label="待复制内容">${e(value)}</textarea>`);}
}
function locationData(){const data=locationCache.get(active);if(!data)throw Error('请等待文件位置读取完成');return data;}
function copyLocation(key){const data=locationData(),item=[...data.reading_files,...data.other_locations].find(item=>item.key===key);if(item?.exists)return copyText(item.path,'文件路径已复制');}
async function openLocation(key){
  const result=await api(`/api/projects/${active}/open-location`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({key})});
  toast(result.data.kind==='directory'?'已打开文件夹':'已用默认应用打开文件');
}
function copyHandoffPaths(){
  const data=locationData();
  const value=`请从以下现有文件接续项目「${data.project_name}」：\n\n${data.reading_files.map((item,index)=>`${index+1}. ${item.label}\n${item.path}\n${item.note}`).join('\n\n')}\n\n当前状态以本周最新确认记录为准，上周交接提供承接背景。${data.read_only?'\n该项目当前设为只读试用。':''}`;
  return copyText(value,'交接读取路径已复制');
}
function renderOverview(){
  const p=meta(),day=currentDay(),week=currentWeek().data;
  $('#view').innerHTML=`<div class="card progress"><div><span class="section-label">目前进度</span><h2>${weekName(p.current.week)} <span>/ Day ${String(p.current.day).padStart(2,'0')}</span></h2>${badge(day.status)}</div><div><h3>今日目标</h3>${goals(day.goals)}</div></div><div class="two-column"><div class="card padded"><div class="card-heading"><h2>${stamp(p.current.week,p.current.day)} · 核心任务与结果</h2>${button('展开今日记录 →','today')}</div><p>${plain(day.summary)}</p>${day.reports.length?`<details class="criteria"><summary>最新交接的位置</summary><p>${plain(day.reports.at(-1).nextStep)}</p></details>`:'<p class="muted" style="margin-top:16px">当前逻辑日还没有详细交接。</p>'}</div><div class="card padded"><div class="card-heading"><h2>本周目标</h2>${button('长期目标 →','project-goals')}</div>${goals(week.goals)}<div class="button-stack">${button('查看每日计划','current-week')}${button('查看本周交接','current-handoff')}</div></div></div>`;
  $('#page-actions').innerHTML=button('项目结构','project-context')+(!p.readOnly?button('记录今日交接','today-report',true):'');
}
function weeklyGoalCard(w){
  const stage=stageFor(w.data);
  return `<div class="card padded week-goal"><h2>本周目标</h2>${goals(w.data.goals)}${stage?`<div class="goal-stage"><span>关联阶段</span>${button(stage.title+' →','stage:'+stage.id)}</div>`:''}</div>`;
}
function applicabilityView(item){
  return item.condition?`<div class="applicability-note"><strong>适用条件</strong><p>${plain(item.condition)}</p></div>`:'';
}
function monthlyGoalView(){
  return `<div class="section-heading weekly-goals-heading"><h2>每周目标</h2><span class="muted">每 4 个逻辑周为 1 个月</span></div><div class="goal-months">${monthGoalGroups().map(group=>{
    const first=(group.month-1)*4+1,last=first+3;
    return `<details class="goal-month ${group.ongoing?'ongoing-month':''}" data-month="${group.month}" ${foldAttrs('goal-month:'+group.month,group.ongoing,0)}><summary><span class="caret">›</span><span class="goal-month-title">第 ${group.month} 个月 <span>${weekName(first)}–${String(last).padStart(2,'0')}</span></span>${group.ongoing?badge('进行中'):''}</summary><div class="goal-month-content">${group.weeks.map(plan=>{
      const stage=stageFor(plan);
      return `<details class="weekly-plan ${plan.ongoing?'ongoing-plan':''}" data-goal-week="${plan.week}" ${foldAttrs('weekly-goal:'+plan.week,plan.ongoing,0)}><summary><span class="caret">›</span><span class="weekly-plan-heading"><strong>${weekName(plan.week)}${plan.current?' · 当前周':''}</strong><span>${e(plan.title)}</span></span>${badge(plan.status)}</summary><div class="weekly-plan-content">${applicabilityView(plan)}<section><h3>周目标</h3>${goals(plan.goals||[])}</section>${Object.entries({outcome:'预期成果',acceptance:'验收标准',scope:'范围边界'}).filter(([key])=>plan[key]).map(([key,title])=>`<section><h3>${title}</h3><p>${plain(plan[key])}</p></section>`).join('')}${stage?`<div class="goal-stage"><span>关联阶段</span>${button(stage.title+' →','stage:'+stage.id)}</div>`:''}${plan.record?`<div class="button-stack">${button('查看每日记录','week-record:'+plan.week)}${button('查看周交接','week-handoff:'+plan.week)}</div>`:''}</div></details>`;
    }).join('')}</div></details>`;
  }).join('')}</div>`;
}
function renderGoals(){
  const roadmap=roadmapEntry()?.data,w=currentWeek();
  if(roadmapEntry())$('#page-actions').innerHTML=button('查看目标 JSON','roadmap-json');
  const goal=roadmap?.goal;
  const goalView=goal?.title?`<div class="card padded long-term-goal"><span class="section-label">项目长期目标</span><h2>${e(goal.title)}</h2><p>${plain(goal.summary)}</p>${goal.outcomes.length?`<details class="goal-outcomes" ${foldAttrs('outcomes',false,0)}><summary>目标达成时应具备什么</summary>${goals(goal.outcomes)}</details>`:''}</div>`:'<div class="card empty"><h2>还没有长期目标</h2><p>整理项目的最终成果与阶段目标后，可以在这里查看。</p></div>';
  const stages=(roadmap?.stages||[]).map((stage,index)=>({stage,index})).sort((a,b)=>Number(b.stage.status==='进行中')-Number(a.stage.status==='进行中'));
  $('#view').innerHTML=`${goalView}${monthlyGoalView()}<div class="section-heading"><h2>阶段成果</h2></div><div class="stage-list">${stages.map(({stage,index})=>{
    const linked=allWeeks().filter(week=>week.data.stageId===stage.id).reverse();
    const current=w.data.stageId===stage.id;
    const planned=stage.plannedWeeks||[];
    const window=planned.length?`${weekName(planned[0])}${planned.at(-1)!==planned[0]?'–'+String(planned.at(-1)).padStart(2,'0'):''}`:'';
    return `<details class="stage-card ${current?'current-stage':''}" data-stage="${e(stage.id)}" ${foldAttrs('stage:'+stage.id,stage.status==='进行中',0)}><summary><span class="caret">›</span><span class="stage-title"><strong>阶段 ${index+1} · ${e(stage.title)}</strong><span>${current?'当前阶段':e(window)}</span></span>${badge(stage.condition&&stage.status==='未完成'?'按需计划':stage.status)}</summary><div class="stage-content">${applicabilityView(stage)}<section><h3>阶段成果</h3><p>${plain(stage.outcome)}</p></section><section><h3>验收标准</h3><p>${plain(stage.acceptance)}</p></section>${linked.length?`<section><h3>关联周记录</h3><div class="stage-weeks">${linked.map(week=>button(weekName(week.data.week),'week-record:'+week.data.week)).join('')}</div></section>`:''}${stage.sections?.length?`<details class="criteria"><summary>更多阶段说明${current&&window?' · '+e(window):''}</summary>${stage.sections.map(part=>`<section><h3>${e(part.title)}</h3><p>${plain(part.body)}</p></section>`).join('')}</details>`:''}</div></details>`;
  }).join('')||'<p class="muted">阶段成果尚未整理。</p>'}</div>`;
  if(focusStage){const target=document.querySelector(`[data-stage="${CSS.escape(focusStage)}"]`);if(target){target.open=true;folds.set(target.dataset.fold,true);requestAnimationFrame(()=>target.scrollIntoView({block:'start'}));}focusStage=null;}
}
function reportView(report,index,total,week){
  return `<details class="report" ${foldAttrs('report:'+report.id,index===total-1,week)}><summary>交接 ${index+1}${index===total-1?' · 最近一份':''}</summary><div class="report-content">${Object.entries(reportFields).filter(([key])=>report[key]).map(([key,title])=>`<section><h3>${title}</h3><p>${plain(report[key])}</p></section>`).join('')}</div></details>`;
}
function renderWeek(){
  const w=weekEntry(),historical=w.path.startsWith('history/'),editable=!meta().readOnly&&!historical;
  $('#page-title').textContent=`${weekName(w.data.week)} · ${historical?'历史周记录':'每日计划与状态'}`;
  $('#page-actions').innerHTML=button('本周交接','selected-handoff')+button('查看周 JSON','week-json')+(editable?button('新增逻辑日','add-day',true):'');
  $('#view').innerHTML=dailyRecords(w);
  focusDailyRecord();
}
function dailyRecords(w){
  const editable=!meta().readOnly&&w.path.startsWith('current/');
  return `<div class="daily-records" data-week="${w.data.week}">${weeklyGoalCard(w)}<div class="list-tools"><span>逻辑日 · 新到旧</span><div>${button('展开全部','expand')}${button('收起全部','collapse')}</div></div><div class="day-list">${w.data.days.slice().sort((a,b)=>b.day-a.day).map(d=>{
    const current=w.data.week===meta().current.week&&d.day===meta().current.day;
    return `<details class="day-card" data-day="${d.day}" ${foldAttrs('day:'+d.day,focusDay===d.day&&selectedWeek===w.data.week,w.data.week)}><summary><span class="caret">›</span><span class="day-number">${stamp(w.data.week,d.day)}${current?'<small>当前逻辑日</small>':''}</span><span class="day-task">${e(d.summary||d.goals[0]||'尚未填写核心任务')}</span>${badge(d.status)}</summary><div class="day-content"><div class="card-heading"><h3>当天目标</h3>${editable?`<div>${button('编辑计划与状态','edit-day:'+d.day)}${!current?button('设为当前日','set-current:'+d.day):''}</div>`:''}</div>${goals(d.goals)}${d.completionCriteria?`<details class="criteria"><summary>完成标准</summary><p>${plain(d.completionCriteria)}</p></details>`:''}<div class="card-heading report-heading"><h3>详细交接</h3>${editable?button('新增阶段交接','report:'+d.day):''}</div>${d.reports.length?d.reports.map((r,i)=>reportView(r,i,d.reports.length,w.data.week)).join(''):`<p class="muted">${d.status==='休息'?'休息安排；没有额外开发记录。':'尚未提交详细交接。进行中的逻辑日也可以保存阶段记录。'}</p>`}</div></details>`;
  }).join('')}</div></div>`;
}
function focusDailyRecord(){
  if(focusDay===null)return;
  const target=document.querySelector(`.daily-records[data-week="${selectedWeek}"] [data-day="${focusDay}"]`);
  if(target){target.open=true;folds.set(target.dataset.fold,true);requestAnimationFrame(()=>target.scrollIntoView({block:'nearest'}));}
  focusDay=null;
}
function openWeekSection(week,section){selectedWeek=Number(week);focusSection={week:selectedWeek,section};route('weeks');}
function renderWeeks(){
  $('#page-actions').innerHTML=button('收起全部','collapse');
  $('#view').innerHTML=`<div class="week-list">${allWeeks().map(w=>{
    const h=handoffEntry(w.data.week),current=w.path.startsWith('current/');
    return `<article class="week-row" data-week="${w.data.week}"><header class="week-row-heading"><h2>${weekName(w.data.week)} <span class="week-location">${current?'当前周':'历史周'}</span></h2><span class="muted">${w.data.days.length} 个逻辑日</span></header><details class="week-section" data-section="handoff" ${foldAttrs('section:handoff',false,w.data.week)}><summary><span class="caret">›</span><span>周交接${h.data.status==='已完成'?'':'草稿'}</span>${badge(h.data.status)}</summary><div class="week-section-body">${handoffContent(h,current)}</div></details><details class="week-section" data-section="days" ${foldAttrs('section:days',false,w.data.week)}><summary><span class="caret">›</span><span>每日详细记录</span></summary><div class="week-section-body"><div class="week-tools">${button('查看周 JSON','week-json')}${current&&!meta().readOnly?button('新增逻辑日','add-day',true):''}</div>${dailyRecords(w)}</div></details></article>`;
  }).join('')}</div>`;
  if(focusSection){const target=document.querySelector(`.week-row[data-week="${focusSection.week}"] [data-section="${focusSection.section}"]`);if(target){target.open=true;folds.set(target.dataset.fold,true);requestAnimationFrame(()=>target.scrollIntoView({block:'start'}));}focusSection=null;}
  focusDailyRecord();
}
function showProjectContext(){
  const p=meta();
  modal('项目结构与运行方式',`<p>${plain(p.description)}</p><div class="module-list">${(p.structure||[]).map(f=>`<div><code>${e(f.path)}</code><p>${e(f.description)}</p></div>`).join('')||'<p class="muted">尚未记录项目结构。</p>'}</div><div class="context-sections">${Object.entries({start:'启动',test:'测试',configuration:'配置'}).map(([key,label])=>`<section><h3>${label}</h3><pre>${e(p.runtime?.[key]||'尚未记录')}</pre></section>`).join('')}${p.contextNotes?`<section><h3>当前状态与待办</h3><p>${plain(p.contextNotes)}</p></section>`:''}${p.constraints?`<section><h3>项目约束</h3><p>${plain(p.constraints)}</p></section>`:''}${p.collaboration?.length?`<section><h3>协作约定</h3>${goals(p.collaboration)}</section>`:''}</div>`);
}
function handoffContent(h,current){
  const draft=h.data.status!=='已完成',canEdit=!meta().readOnly&&current;
  return `<div class="week-tools">${button('复制 JSON','copy-handoff')}${button('导出周交接 JSON','download-handoff')}${canEdit?button('编辑周交接','edit-handoff',true):''}</div>${draft?'<p class="draft-note">本周尚未结束，这份草稿不代表阶段验收已完成。</p>':''}<div class="handoff-document">${Object.entries(handoffFields).filter(([key])=>h.data[key]).map(([key,title])=>`<section><h2>${title}</h2><p>${plain(h.data[key])}</p></section>`).join('')||'<p class="muted">尚未整理周交接。它应汇总本周成果、当前状态、遗留问题和下周起点。</p>'}</div>${canEdit?`<div class="next-week">${button('归档本周并开始下一周','next-week')}</div>`:''}`;
}
function modal(title,html,onSubmit=null,submitLabel='保存'){const dialog=$('#modal');$('#modal-title').textContent=title;$('#modal-body').innerHTML=html;$('#modal-actions').innerHTML=button('关闭','close')+(onSubmit?`<button type="submit" class="primary">${submitLabel}</button>`:'');$('#modal-form').onsubmit=async event=>{event.preventDefault();if(!onSubmit||saving)return;const submit=event.submitter;if(submit)submit.disabled=true;try{await onSubmit(Object.fromEntries(new FormData(event.currentTarget)));}catch(error){toast(error.message);}finally{if(submit)submit.disabled=false;}};dialog.showModal();}
function field(title,name,value='',area=false,required=false){return `<label class="field">${title}${area?`<textarea name="${name}" ${required?'required':''}>${e(value)}</textarea>`:`<input name="${name}" value="${e(value)}" ${required?'required':''}>`}</label>`;}
function statusField(status,includeRest=true){return `<label class="field">状态<select name="status">${(includeRest?['未完成','进行中','已完成','休息']:['未完成','进行中','已完成']).map(s=>`<option ${s===status?'selected':''}>${s}</option>`).join('')}</select></label>`;}
const lines=value=>value.split('\n').map(s=>s.trim()).filter(Boolean);
function showJson(path){const data=entry().files[path].data;modal(path,`<textarea class="json-view" readonly aria-label="JSON 文件内容">${e(JSON.stringify(data,null,2))}</textarea>`);}
function editable(){if(meta().readOnly){toast('该项目当前为只读，请新建项目试写 JSON');return false;}return true;}
function editDay(dayNumber,isNew=false){if(!editable())return;const w=weekEntry(),copy=structuredClone(w.data);const d=isNew?{day:Math.max(...copy.days.map(d=>d.day))+1,status:'未完成',goals:[],summary:'',reports:[]}:copy.days.find(d=>d.day===dayNumber);modal(`${isNew?'新增':'编辑'} ${stamp(copy.week,d.day)}`,`${statusField(d.status)}${field('今日目标（每行一项）','goals',d.goals.join('\n'),true)}${field('核心任务与结果','summary',d.summary,true)}`,async values=>{Object.assign(d,{status:values.status,goals:lines(values.goals),summary:values.summary});if(isNew)copy.days.push(d);copy.status=copy.days.every(d=>['已完成','休息'].includes(d.status))?'已完成':copy.days.some(d=>['进行中','已完成'].includes(d.status))?'进行中':'未完成';if(await saveFile(w.path,copy,w.etag)){$('#modal').close();focusDay=d.day;render();toast('每日计划与状态已保存');}});}
function addReport(dayNumber){if(!editable())return;const w=weekEntry(),copy=structuredClone(w.data),d=copy.days.find(d=>d.day===dayNumber);modal(`${stamp(copy.week,d.day)} · 阶段交接`,`${statusField(d.status)}${field('核心任务与结果','summary',d.summary,true)}${Object.entries(reportFields).map(([key,title])=>field(title,key,'',true,key==='completed')).join('')}`,async values=>{d.status=values.status;d.summary=values.summary;d.reports.push({id:stamp(copy.week,d.day)+'-'+crypto.randomUUID().slice(0,8),submittedAt:new Date().toISOString(),...Object.fromEntries(Object.keys(reportFields).map(key=>[key,values[key]]))});copy.status=copy.days.every(d=>['已完成','休息'].includes(d.status))?'已完成':'进行中';if(await saveFile(w.path,copy,w.etag)){$('#modal').close();toast('已追加交接，之前的记录保留');}});}
function editHandoff(){if(!editable())return;const h=handoffEntry();modal(`${weekName(selectedWeek)} · 编辑周交接`,`${statusField(h.data.status,false)}${Object.entries(handoffFields).map(([key,title])=>field(title,key,h.data[key],true)).join('')}`,async values=>{if(values.status==='休息')throw Error('周交接请使用未完成、进行中或已完成');const data={...h.data,...values};if(await saveFile(h.path,data,h.etag)){$('#modal').close();toast('周交接 JSON 已保存');}});}
async function setCurrent(day){if(!editable())return;const f=entry().files['project.json'];if(await saveFile('project.json',{...f.data,current:{week:selectedWeek,day:Number(day)}},f.etag))toast('当前逻辑日已更新');}
function newProject(){modal('新建本地项目',field('项目名称','name','',false,true),async values=>{const result=await api('/api/projects',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(values)});active=result.data.id;selectedWeek=1;await load();$('#modal').close();route('overview');toast('已创建项目与第一周 JSON');},'创建');}
async function download(data,name){try{if(window.pywebview?.api){const result=await window.pywebview.api.save_json(name,data);if(result.saved)toast('JSON 已导出');return;}const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)+'\n'],{type:'application/json'}));const anchor=document.createElement('a');anchor.href=url;anchor.download=name;anchor.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}catch(error){toast('导出未完成：'+error.message);}}
async function copyJson(data){return copyText(JSON.stringify(data,null,2),'JSON 已复制');}
function exportProject(){download({schemaVersion:2,files:Object.fromEntries(Object.entries(entry().files).map(([path,f])=>[path,f.data]))},active+'-project.json');}
function dataTools(){modal('本地 JSON 资料',`<p>每个项目独立存放，分为“正在使用文件”和“备份资料”。具体路径见“文件位置”；JSON 导出只包含正式记录。</p><div class="button-stack">${button('新建项目','new-project')}${meta()?button('导出当前项目 JSON','export-project'):''}${button('导入项目 JSON','import')}${button('重新读取本地文件','reload')}</div>`);}
function nextWeek(){if(!editable())return;modal('归档本周并开始下一周',`<p>本周所有工作日和周交接均须完成。归档后保留完整日记录和独立周交接，再创建新的 Week ${selectedWeek+1}。</p>`,async()=>{const result=await api(`/api/projects/${active}/next-week`,{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});selectedWeek=result.data.week;await load();$('#modal').close();route('week');toast('已归档并建立下一周');},'归档并开始');}
function setFolds(open,scope=$('#view')){scope.querySelectorAll('details[data-fold]').forEach(el=>{el.open=open;folds.set(el.dataset.fold,open);});}
const actions={
 'refresh-locations':renderLocations,'copy-location':copyLocation,'copy-handoff-paths':copyHandoffPaths,'copy-record-directory':()=>copyText(locationData().project_directory,'记录目录已复制'),
 'new-project':()=>{$('#modal').close();newProject();},'data-tools':dataTools,'project-context':showProjectContext,'close':()=>$('#modal').close(),
 'project-goals':()=>route('goals'),'roadmap-json':()=>showJson('roadmap.json'),
 'today':()=>{focusDay=meta().current.day;route('week',meta().current.week);},'today-report':()=>{selectedWeek=meta().current.week;addReport(meta().current.day);},
 'current-week':()=>route('week',meta().current.week),'current-handoff':()=>openWeekSection(meta().current.week,'handoff'),'selected-handoff':()=>openWeekSection(selectedWeek,'handoff'),
 'week-json':()=>showJson(weekEntry().path),'add-day':()=>editDay(null,true),'edit-handoff':editHandoff,
 'copy-handoff':()=>copyJson(handoffEntry().data),'download-handoff':()=>download(handoffEntry().data,`week${String(selectedWeek).padStart(2,'0')}-handoff.json`),'next-week':nextWeek,
 'expand':()=>setFolds(true),'collapse':()=>setFolds(false),'export-project':exportProject,'import':()=>{$('#modal').close();$('#import-file').click();},'reload':async()=>{await load();$('#modal').close();toast('已重新读取 JSON');}
};
document.addEventListener('click',async event=>{const nav=event.target.closest('[data-nav]');if(nav){event.preventDefault();if(nav.dataset.nav==='week')selectedWeek=meta()?.current.week;route(nav.dataset.nav);return;}const action=event.target.closest('[data-action]');if(!action)return;event.preventDefault();const week=action.closest('[data-week]');if(week)selectedWeek=Number(week.dataset.week);const [name,arg]=action.dataset.action.split(':');try{if(name==='edit-day')editDay(Number(arg));else if(name==='report')addReport(Number(arg));else if(name==='set-current')await setCurrent(Number(arg));else if(name==='stage'){focusStage=arg;route('goals');}else if(name==='week-record')openWeekSection(Number(arg),'days');else if(name==='week-handoff')openWeekSection(Number(arg),'handoff');else if(name==='copy-role')await copyRole(arg);else if(name==='copy-role-paths')await copyRolePaths(arg);else if(name==='copy-location')await copyLocation(arg);else if(name==='open-location')await openLocation(arg);else if(name==='expand'||name==='collapse')setFolds(name==='expand',action.closest('.daily-records')||$('#view'));else await actions[name]?.();}catch(error){toast(error.message);}});
document.addEventListener('change',event=>{const id=event.target.dataset.roleScenario;if(!id)return;roleScenes.set(JSON.stringify([active,id]),event.target.value);renderCollaboration();});
document.addEventListener('toggle',event=>{if(event.target.isConnected&&event.target.dataset.fold)folds.set(event.target.dataset.fold,event.target.open);},true);
$('#project-select').onchange=event=>{active=event.target.value;selectedWeek=meta().current.week;render();};
$('#close-modal').onclick=()=>$('#modal').close();
$('#import-file').onchange=async event=>{const file=event.target.files[0];if(!file)return;try{if(file.size>5_000_000)throw Error('导入文件不能超过 5 MB');const bundle=JSON.parse(await file.text());if(bundle.schemaVersion!==2||!bundle.files?.['project.json'])throw Error('请选择版本 2 的项目 JSON 导出包');modal('导入本地项目',`<p>将导入 ${e(bundle.files['project.json'].name)}。已有相同 ID 的项目不会被覆盖。</p>`,async()=>{const result=await api('/api/import',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(bundle)});active=result.data.id;selectedWeek=null;await load();$('#modal').close();route('overview');},'导入');}catch(error){toast(error.message);}finally{event.target.value='';}};
window.addEventListener('hashchange',()=>{render();window.scrollTo(0,0);});
load().catch(error=>{storageStatus('JSON 读取失败',true);$('#view').innerHTML=`<div class="card empty"><h2>无法读取本地资料</h2><p>${e(error.message)}</p><p>修正 JSON 或启动本地服务后刷新即可。已有文件不会被重置。</p></div>`;});
setInterval(()=>{if(saving||$('#modal').open||document.hidden)return;load(true).catch(error=>storageStatus('文件读取失败：'+error.message,true));},5000);
