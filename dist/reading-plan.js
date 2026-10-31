'use strict';
var ReadingPlan=(()=>{
  const defaults={
    project:{label:'项目概况与结构',note:'了解结构、运行方式、协作约定和当前进度。'},
    'current-week':{label:'本周记录',note:'读取当前日最新报告和准确的下一步。'},
    'previous-handoff':{label:'最近完成周交接',note:'承接跨周状态、遗留问题和新周起点，当前周最新记录优先。'},
    roadmap:{label:'整体目标与阶段',note:'规划新周或调整方向时核对目标、阶段和周规划。'},
    'agent-guide':{label:'记录读写说明',note:'规定记录字段和保存方式，供负责写入的管理者使用。'}
  };
  function scenarios(role){
    return role.scenarios?.length?role.scenarios:[{id:'daily',title:'日常继续',description:'从当前已确认记录继续，按本角色职责处理当前任务。',additionalReads:[],optionalReads:[]}];
  }
  function build(role,locations,scenarioId){
    const choices=scenarios(role),scenario=choices.find(item=>item.id===scenarioId)||choices[0];
    const requiredKeys=[...new Set([...(role.reads?.length?role.reads:['project','current-week']),...(scenario.additionalReads||[])])];
    function resolve(key,requirement,when){
      const actual=locations.reading_files.find(item=>item.key===key),fallback=defaults[key]||{label:key,note:'按角色说明读取对应资料。'};
      return {...fallback,...actual,key,kind:'file',exists:actual?.exists===true,requirement,when,
        unavailable:actual?.exists?'':key==='previous-handoff'?'暂无已完成的历史周交接；第一周可跳过。':'当前未找到此文件，请确认资料是否齐全。'};
    }
    const required=requiredKeys.map(key=>resolve(key,'必读','本次场景必读'));
    const optional=[...new Map((scenario.optionalReads||[]).filter(item=>!requiredKeys.includes(item.key)).map(item=>[item.key,item])).values()].map(item=>resolve(item.key,'按需',item.when));
    return {scenario,required,optional};
  }
  function fileList(plan){
    return [['必读文件',plan.required],['按需文件',plan.optional]].filter(([,items])=>items.length).map(([title,items])=>`${title}\n${items.map(item=>`${item.label}\n用途：${item.note}\n读取时机：${item.when}\n${item.exists?`位置：${item.path}`:item.unavailable}`).join('\n\n')}`).join('\n\n');
  }
  function startupMessage(project,role,plan){
    return [`请作为「${role.title}」接续项目「${project.name}」。`,`本次场景：${plan.scenario.title}\n${plan.scenario.description}`,
      `先读取必读文件，按标注的用途和时机决定是否读取按需文件。遵循 project.json 中的 collaboration，以及 agentRoles 内 id="${role.id}" 的职责；其他角色用于理解分工，不代入其职责。`,
      '确认当前 Week/Day、实际状态和最新下一步，再完成本次场景的工作。被管理项目的业务规则以自己的项目 JSON 为准，记录读写说明只规定记录维护方式。',fileList(plan)].join('\n\n');
  }
  return {scenarios,build,fileList,startupMessage};
})();
if(typeof module!=='undefined'&&module.exports)module.exports=ReadingPlan;
