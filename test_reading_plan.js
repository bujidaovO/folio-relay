'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const ReadingPlan=require('./dist/reading-plan.js');

function locations(base='/moved/data/projects/demo/正在使用文件'){
  return {reading_files:[
    {key:'project',label:'项目概况',note:'结构、规则和当前进度',path:base+'/project.json',exists:true},
    {key:'current-week',label:'本周记录',note:'当前日最新报告和下一步',path:base+'/current/week03.json',exists:true},
    {key:'previous-handoff',label:'Week 02 周交接',note:'上周状态与遗留事项',path:base+'/history/week02-handoff.json',exists:true},
    {key:'roadmap',label:'目标',note:'长期目标和阶段成果',path:base+'/roadmap.json',exists:true},
    {key:'agent-guide',label:'记录读写说明',note:'记录维护方式',path:'/moved/app/记录读写说明.md',exists:true}
  ]};
}
const role={id:'execution',title:'执行对话',reads:['project','current-week'],sections:[{title:'规则',items:['只在项目 JSON 中维护这段规则']}],scenarios:[
  {id:'daily',title:'日常继续',description:'从最新报告继续',additionalReads:[],optionalReads:[{key:'previous-handoff',when:'需要跨周背景时'}]},
  {id:'new-week',title:'新周开始',description:'先承接上周遗留事项',additionalReads:['previous-handoff'],optionalReads:[{key:'roadmap',when:'需要核对阶段边界时'}]},
  {id:'resume',title:'同日续接',description:'读取最新总结，保持当前逻辑日',additionalReads:[],optionalReads:[]}
]};

test('daily and new-week require different files and retain optional timing',()=>{
  const daily=ReadingPlan.build(role,locations(),'daily'),newWeek=ReadingPlan.build(role,locations(),'new-week');
  assert.deepEqual(daily.required.map(x=>x.key),['project','current-week']);
  assert.equal(daily.optional[0].when,'需要跨周背景时');
  assert.deepEqual(newWeek.required.map(x=>x.key),['project','current-week','previous-handoff']);
  assert.equal(newWeek.optional[0].key,'roadmap');
});
test('same-day continuation keeps its distinct intent',()=>{
  const plan=ReadingPlan.build(role,locations(),'resume');
  assert.equal(plan.scenario.id,'resume');
  assert.equal(plan.required.length,2);
  assert.match(ReadingPlan.startupMessage({name:'测试项目'},role,plan),/保持当前逻辑日/);
});
test('first-week missing handoff is explicit, without inventing a path',()=>{
  const data=locations();data.reading_files=data.reading_files.filter(x=>x.key!=='previous-handoff');
  const plan=ReadingPlan.build(role,data,'new-week'),handoff=plan.required.at(-1);
  assert.equal(handoff.exists,false);
  assert.equal(handoff.path,undefined);
  assert.match(ReadingPlan.fileList(plan),/第一周可跳过/);
  assert.doesNotMatch(ReadingPlan.fileList(plan),/位置：undefined/);
});
test('required files win over duplicates in the optional list',()=>{
  const custom={...role,scenarios:[{id:'daily',title:'日常',description:'',additionalReads:['project'],optionalReads:[{key:'project',when:'可选'},{key:'roadmap',when:'规划时'},{key:'roadmap',when:'调整方向时'}]}]};
  const plan=ReadingPlan.build(custom,locations());
  assert.equal(plan.required.length,2);
  assert.deepEqual(plan.optional.map(x=>x.key),['roadmap']);
});
test('relocation uses resolved current paths and leaves role configuration portable',()=>{
  const before=JSON.stringify(role),plan=ReadingPlan.build(role,locations('/another/资料/demo/正在使用文件'),'new-week');
  const text=ReadingPlan.fileList(plan);
  assert.match(text,/\/another\/资料\/demo\/正在使用文件\/project.json/);
  assert.doesNotMatch(text,/\/moved\/data/);
  assert.equal(JSON.stringify(role),before);
});
test('copied startup states the scene, purpose, priority and selected role',()=>{
  const text=ReadingPlan.startupMessage({name:'测试项目'},role,ReadingPlan.build(role,locations(),'new-week'));
  for(const expected of ['新周开始','必读文件','按需文件','用途：','读取时机：','id="execution"','其他角色用于理解分工'])assert.ok(text.includes(expected));
  assert.doesNotMatch(text,/只在项目 JSON 中维护这段规则/);
});
test('roles without scenario configuration retain their basic reading list',()=>{
  const plain={id:'custom',title:'自定义角色',reads:['project']};
  const plan=ReadingPlan.build(plain,locations(),'removed-scene');
  assert.equal(plan.scenario.id,'daily');
  assert.deepEqual(plan.required.map(x=>x.key),['project']);
});
