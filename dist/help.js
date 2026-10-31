'use strict';
(() => {
  const dialog = document.querySelector('#help-dialog');
  const entry = document.querySelector('#open-help');
  dialog.innerHTML = `
    <header class="help-header"><div><h2 id="help-title">使用说明</h2><p>让每次工作都有起点、结果和下一步。</p></div><button type="button" class="icon-button" data-help-close aria-label="关闭使用说明">✕</button></header>
    <nav class="help-topics" aria-label="使用说明目录">
        <button type="button" data-help-topic="daily">开始与交接</button><button type="button" data-help-topic="setup">第一次使用</button><button type="button" data-help-topic="week">续接与换周</button><button type="button" data-help-topic="manual">查看与补记</button><button type="button" data-help-topic="files">资料与迁移</button>
    </nav>
    <div class="help-body">
      <p class="help-intro">这里保存项目目标、结构和进度。实际工作在外部对话中完成，由管理者把结果写回记录，再从记录继续下一次工作。以下以“管理＋执行”协作为例，具体分工看当前项目的“协作说明”。</p>
      <div class="help-cycle" aria-label="完整使用流程"><span>确认起点</span><span aria-hidden="true">→</span><span>开展工作</span><span aria-hidden="true">→</span><span>写回交接</span><span aria-hidden="true">→</span><span>核对保存</span><span aria-hidden="true">→</span><span>下次继续</span></div>

      <details class="help-topic" id="help-daily" open>
        <summary>完成一次日常工作：从开始到下次继续</summary>
        <div class="help-topic-content"><ol class="help-steps">
          <li><h3>确认这次从哪里开始</h3><p>先用项目选择框选中项目，打开“项目概览”，看当前 Week / Day、今日目标和核心任务与结果。点“展开今日记录 →”，再展开当天最新一份详细交接，重点看“下一步位置”。</p><p class="help-purpose">目的：先知道哪些已经完成、这次第一步是什么，接续时就能准确继续。</p></li>
          <li><h3>让管理者准备本次任务</h3><p>打开“协作说明”，找到管理角色，选择“日常继续”，点“复制启动消息”，粘贴到外部管理对话。已有管理对话可以直接继续，请它根据当前记录准备本次任务、验收目标和执行起点。新项目还没有角色时，先按“第一次使用”补齐。</p><p class="help-purpose">目的：让管理者统一安排与当前进度，保证本次工作和项目目标衔接。</p></li>
          <li><h3>在执行对话里开展工作</h3><p>在“协作说明”找到执行角色，选好场景，点“复制启动消息”，粘贴到执行对话，并附上管理者准备的具体任务。需要单独提供位置时用“复制文件位置”。同机 agent 可以读取这些路径；确认它已读到资料、说清本次起点后，再开始工作。</p><p class="help-purpose">目的：把角色规则、必读文件和具体任务交给执行者；文件清单会随场景说明每份资料的用途。</p></li>
          <li><h3>结束或暂停时，留下实际结果</h3><p>在执行对话中请执行者总结：实际完成、验证结果、关键理解、问题与处理、代码和 Git 状态、下一步准确位置。未做完也可以交接，当天可保持“进行中”。</p><p class="help-purpose">目的：把本次对话中已经发生的事实和准确停留位置留下，便于管理者整理。</p></li>
          <li><h3>让管理者读取总结并保存</h3><p>回到管理对话，告诉它执行总结所在的可访问对话或文件，请它读取并更新记录。若它无法访问，可直接粘贴总结文本。管理者应追加本次交接、更新当天摘要与状态，必要时同步项目结构或目标，并告知保存文件、逻辑日和下一步。</p><blockquote>可直接这样说：请读取这份执行总结，更新当前逻辑日的记录，保存后告诉我更新了哪里，以及下次从哪一步继续。</blockquote><p class="help-purpose">目的：让执行结果进入正式记录；应用不会自行读取其他对话，管理者需要实际完成写入。</p></li>
          <li><h3>在应用里核对，完成本次闭环</h3><p>打开“当前周”，展开对应逻辑日和最新一份详细交接，确认本次结果、当天状态和下一步与总结一致。agent 修改文件后，页面空闲时会检查更新；也可点右上“本地资料 → 重新读取本地文件”。若仍看不到本次记录，让管理者核对保存位置和保存结果。</p><p>下次继续时，从这份最新记录开始。同一 Day 换对话用“同日续接”；真正进入下一个逻辑日时，再由管理者更新当前日。</p></li>
        </ol><div class="help-finish"><strong>本次完成标志</strong><p>你能在应用中找到本次结果，并明确下次第一步。执行 → 总结 → 管理保存 → 页面核对 → 下次接续，形成一条连续记录。</p></div></div>
      </details>

      <details class="help-topic" id="help-setup">
        <summary>第一次使用：建立能交接的项目</summary>
        <div class="help-topic-content"><ol class="help-steps">
          <li><h3>新建或导入项目</h3><p>点“＋ 新建项目”，填写名称并创建；已有本系统导出的项目，可从“本地资料 → 导入项目 JSON”导入，再在项目选择框中确认选中了正确项目。相同项目 ID 的导入不会覆盖现有资料。</p><p class="help-purpose">目的：让不同项目各自拥有正式记录与备份目录。</p></li>
          <li><h3>请管理者补齐交接所需的信息</h3><p>打开“文件位置”，点“复制交接路径”，把文件清单粘贴到一个新的外部对话，请它担任本项目管理者。让它阅读“记录读写说明”，与你确认目标和真实起点，再整理项目结构、运行方式、约束、长期与阶段目标、角色分工、本周目标和每日计划，设定当前 Week / Day。</p><blockquote>可直接这样说：请担任这个项目的管理者，先读取这些文件，与我确认项目目标和当前进度，再补齐项目资料、协作角色和本周计划，并准备第一次执行对话的启动消息。</blockquote><p>新建项目是空白起点，角色与完整计划需要按你的项目设置；可以采用学习管理与执行，也可以设置开发、评审等角色。</p></li>
          <li><h3>核对后开始第一次工作</h3><p>在“项目概览 → 项目结构”查看结构和运行方式；在“项目目标”查看方向，在“当前周”查看计划，在“协作说明”确认角色。能说清目标、当前起点和分工后，按“开始与交接”的完整流程开始。</p></li>
        </ol><div class="help-finish"><strong>完成标志</strong><p>新对话可以通过文件清单了解项目，并知道本次要做什么、结束后由谁更新记录。</p></div></div>
      </details>

      <details class="help-topic" id="help-week">
        <summary>换对话与周末：保持连续，开始新周</summary>
        <div class="help-topic-content"><h3>先选对接续场景</h3><dl class="help-scenarios"><div><dt>日常继续</dt><dd>从当前日最新记录继续，按页面清单读取本次必读文件。</dd></div><div><dt>同日续接</dt><dd>同一个 Day 因上下文过长等原因换对话，保持 Week / Day。先请管理者保存上一段总结，再复制该场景的启动消息；尚未保存时，要把上一段总结一并交给接手者。</dd></div><div><dt>新周开始</dt><dd>本周归档、新周计划补齐后使用。文件清单会增加上周最终交接，管理者还会读取目标与阶段规划；第一周没有历史交接时跳过。</dd></div></dl><p class="help-purpose">Week / Day 是逻辑进度；跨自然日或更换对话，都不会自动推进它。</p>
        <h3 class="help-subtitle">完成一次周交接</h3><ol class="help-steps">
          <li><h3>汇总本周</h3><p>请管理者根据本周已有报告，整理成果、验证、当前项目状态、遗留事项和下周第一步，保存本周交接。你可在“周记录 → 当前周 → 周交接”查看；需要手工填写时点“编辑周交接”。</p><p class="help-purpose">目的：下一周主要读这份汇总，就能承接关键状态和遗留问题。</p></li>
          <li><h3>确认归档条件</h3><p>核对本周各日均为“已完成”或“休息”，周交接也为“已完成”。仍有未完成工作时，先与管理者确定保留、调整或承接安排，按实际结果更新记录。</p></li>
          <li><h3>归档并补齐新周计划</h3><p>在当前周交接下点“归档本周并开始下一周”，检查说明后点“归档并开始”。系统保留历史周记录和交接，并建立下一周。再请管理者补齐新周目标及每日安排，确认“项目概览”指向新周的正确起点。</p><p class="help-purpose">目的：把已发生的历史保存完整，同时给下一次执行准备可用计划。</p></li>
          <li><h3>接上下一周</h3><p>回到“协作说明”，选“新周开始”，复制启动消息，连同管理者给出的具体任务开始执行；结束后仍按日常流程保存并核对交接。</p></li>
        </ol><div class="help-finish"><strong>完成标志</strong><p>“周记录”中能找到上周最终交接，“当前周”有可执行的新计划，新对话知道承接事项和第一步。</p></div></div>
      </details>

      <details class="help-topic" id="help-manual">
        <summary>查看与手工补记：找到事实，确认保存</summary>
        <div class="help-topic-content"><dl class="help-scenarios"><div><dt>看整体方向</dt><dd>“项目目标”集中显示长期、阶段和每周目标；“项目概览 → 项目结构”显示文件职责、运行方式和约定。</dd></div><div><dt>看一天做了什么</dt><dd>“当前周”中展开某个逻辑日，再展开详细交接。往期内容从“周记录”选择周，展开“每日详细记录”查看。</dd></div><div><dt>手工补充交接</dt><dd>在“项目概览”点“记录今日交接”，或在当天点“新增阶段交接”，填写实际结果、验证和下一步，选择当天状态并保存。已有交接会保留，本次内容作为新报告追加。</dd></div><div><dt>调整当天计划</dt><dd>在当天点“编辑计划与状态”。真正开始下一逻辑日时，确认该日计划存在，再点“设为当前日”；需要增加逻辑日时用“当前周”的“新增逻辑日”。</dd></div></dl><p class="help-purpose">日常优先由管理者统一维护。手工补记后也要告知管理者，后续对话读取最新记录。</p><div class="help-finish"><strong>每次保存后都做一次确认</strong><p>看到保存成功后，回到对应日或周交接查看内容。若提示保存未完成，保留输入，并让管理者读取最新记录、合并后再保存；页面中能看到结果才算完成。</p></div></div>
      </details>

      <details class="help-topic" id="help-files">
        <summary>资料与迁移：清理有范围，搬走能继续</summary>
        <div class="help-topic-content"><h3>先分清两个资料目录</h3><p>“文件位置”中可以打开或复制项目总目录，里面分为“正在使用文件”和“备份资料”。前者包含当前记录以及 history 中的正式历史周；后者是旧副本，按用途和时间分类，由你手工清理，不自动删除。</p><h3 class="help-subtitle">导出或转移资料</h3><ol class="help-steps">
          <li><h3>选择要带走的范围</h3><p>只需要正式记录时，用“本地资料 → 导出当前项目 JSON”，选择保存位置。要连同备份一起搬走，就从“文件位置”找到项目总目录，复制整个项目文件夹。</p></li>
          <li><h3>在新位置打开</h3><p>整体搬迁时，先退出应用，复制应用和旁边的“项目资料”，再打开新位置的应用。单项目搬迁时，把该项目文件夹放到目标资料根目录的 projects 文件夹下，保留项目 ID，不覆盖同名项目。JSON 导出包则用“本地资料 → 导入项目 JSON”接入。</p><p>如果资料放在自选位置，使用桌面应用的系统菜单“资料 → 选择资料目录…”，选中包含 projects 的资料根目录。</p></li>
          <li><h3>检查后继续接续</h3><p>在新位置选中项目，到“文件位置”核对实际路径，再检查当前 Week / Day、最新交接与目标。重新复制启动消息或文件清单，交给下一位 agent。</p></li>
        </ol><div class="help-finish"><strong>完成标志</strong><p>新位置能打开同一项目、找到最新记录并接上下一步。应用更新只替换程序，项目资料继续独立保存；被记录项目的代码仓库、数据库与运行环境按需另行迁移。</p></div></div>
      </details>
    </div>
    <footer class="help-footer"><p>看完后，回到原页面继续操作。</p><button type="button" class="primary" data-help-close>返回当前页面</button></footer>`;

  entry.addEventListener('click', () => {
    if (!dialog.open) dialog.showModal();
  });
  dialog.addEventListener('click', event => {
    if (event.target.closest('[data-help-close]')) dialog.close();
    const button = event.target.closest('[data-help-topic]');
    if (!button) return;
    const topic = dialog.querySelector('#help-' + button.dataset.helpTopic);
    dialog.querySelectorAll('.help-topic').forEach(item => { item.open = item === topic; });
    topic.querySelector('summary').focus({preventScroll:true});
    topic.scrollIntoView({block:'start'});
  });
  dialog.addEventListener('close', () => entry.focus({preventScroll:true}));
})();
