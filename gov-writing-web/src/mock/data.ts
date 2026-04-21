import Mock from 'mockjs';

const Random = Mock.Random;

export const mockSteps = {
  document: {
    title: '严打电信诈骗专项行动通知初稿',
    steps: [
      { type: 'think', label: 'Lead Agent 分析任务中' },
      {
        type: 'tool',
        label: '工具调用 · to_do_list',
        contentType: 'pre',
        content:
          '✓ 解析警务公文写作需求\n✓ 确定文种：专项行动通知\n✓ 调度 公文写作专家 Claw\n✓ 生成公文结构框架\n✓ 输出格式化文件',
      },
      {
        type: 'subAgent',
        label: 'Claw 调用 · <strong>公文专家</strong>',
        contentType: 'text',
        content:
          '调用公文写作专家 Claw，依据 GB/T 9704-2012 标准生成党政机关公文。\n文种识别：专项行动通知 · 发文机关：XX市公安局办公室 · 语言风格：正式',
      },
      {
        type: 'skill',
        label: 'Skills 调用 · doc_format + compliance_check',
        contentType: 'skills',
        content: {
          summary: '共调用 <strong>2</strong> 个 Skills',
          skills: ['doc_format', 'compliance_check'],
        },
      },
      {
        type: 'tool',
        label: '工具调用 · search',
        contentType: 'search',
        content: {
          total: 12,
          used: 3,
          results: [
            {
              title: '公安部关于深入推进打击治理电信网络诈骗工作的意见',
              description:
                '明确电信诈骗打击工作的总体部署、重点任务与协同机制，是各地开展专项行动的核心依据文件。',
              tag: '部级文件',
            },
            {
              title: '《中华人民共和国刑法》第二百六十六条',
              description: '诈骗公私财物相关法律条款及量刑标准，为专项行动提供法律授权依据。',
              tag: '法律法规',
            },
            {
              title: 'GB/T 9704-2012 党政机关公文格式国家标准',
              description: '规定党政机关公文的格式要素、版式及装订要求，是公文写作的核心合规依据。',
              tag: '技术标准',
            },
          ],
        },
      },
      {
        type: 'cli',
        label: 'CLI 工具 · read_file',
        contentType: 'pre',
        content:
          'read_file("templates/police_notice_template.docx")\n→ 读取警务公文模板，提取格式要素',
      },
      {
        type: 'documentOutput',
        contentType: 'documentCard',
        label: '关于进一步优化营商环境的通知（初稿）.docx',
        content: {
          description:
            '已按正式通知体例生成初稿，正文覆盖工作目标、重点任务与保障要求，适合作为后续审核与排版的起点。',
          footerHint: '点击结果文件后，可在右侧编辑器继续修改正文。',
          openEditorLabel: '在右侧编辑器打开',
          body: `<p style="margin: 0; text-align: center; color: red; font-size: 40pt; line-height: 59pt;">XX 市人民政府办公室</p>
  <p style="margin: 0; text-align: center; font-size: 16pt; line-height: 28pt;">&nbsp;</p>
  <p style="margin: 0; text-align: center; font-size: 16pt; line-height: 28pt;">XX 政办发〔2026〕8 号</span></p>
  <p style="margin: 0; text-align: center; font-size: 16pt; line-height: 28pt; border-top: 2px solid red;">&nbsp;</p>
  <p style="margin: 0; text-align: center; font-size: 22pt; line-height: 35pt;font-family: 方正小标宋_GBK">关于进一步优化营商环境的通知</p>
  <p style="margin: 0; text-align: center; font-size: 16pt; line-height: 28pt;">&nbsp;</p>
  <p style="margin: 0; font-size: 16pt; line-height: 28pt;">各处室、直属单位：</p>
  <p style="margin: 0; font-size: 16pt; line-height: 28pt; text-indent: 32pt;">为持续提升政务服务质效，营造稳定公平透明、可预期的营商环境，经研究决定，现就有关事项通知如下。</p>
  <p style="margin: 0; font-size: 16pt; line-height: 28pt; text-indent: 32pt;">一是强化服务意识。各部门要牢固树立以人民为中心的发展思想，优化办事流程，压缩办理时限，提升企业和群众获得感。</p>
  <p style="margin: 0; font-size: 16pt; line-height: 28pt; text-indent: 32pt;">二是完善政策体系。围绕市场准入、要素保障、法治环境等重点领域，及时修订配套制度，确保政策落地见效。</p>
  <p style="margin: 0; font-size: 16pt; line-height: 28pt; text-indent: 32pt;">三是加强督查考核。将营商环境优化纳入年度绩效考核，对工作不力、问题突出的单位予以通报并限期整改。</p>
  <p style="margin: 0; font-size: 16pt; line-height: 28pt; text-indent: 32pt;">请各单位认真贯彻执行。</p>
  <p style="margin: 0; font-size: 16pt; line-height: 28pt; text-align: right; padding-right: 48pt;">XX 市人民政府办公室</p>
  <p style="margin: 0; font-size: 16pt; line-height: 28pt; text-align: right; padding-right: 78pt;">2026年4月1日</p>`,
        },
      },
    ],
  },
  search: {
    title: '具身智能资料检索',
    steps: [
      { type: 'think', label: 'Lead Agent 分析任务中' },
      {
        type: 'tool',
        label: '工具调用 · to_do_list',
        contentType: 'pre',
        content:
          '✓ 生成检索词：具身智能、政策、产业、场景应用\n✓ 调度 资料检索专员 Claw\n✓ 筛选可引用资料\n✓ 输出摘要与原文入口',
      },
      {
        type: 'subAgent',
        label: 'Subagent · <strong>资料检索专员</strong>',
        contentType: 'text',
        content:
          '调用公文专家 Claw，依据 GB/T 9704-2012 标准生成党政机关公文。<br>文种识别：通知 &nbsp;·&nbsp; 发文机关：XX市人民政府办公室 &nbsp;·&nbsp; 语言风格：正式',
      },
      {
        type: 'skill',
        label: 'Skills 调用 · source_rank + summary_extract',
        contentType: 'skills',
        content: {
          summary: '共调用 <strong>2</strong> 个 Skills',
          skills: ['source_rank', 'summary_extract'],
        },
      },
      {
        type: 'tool',
        label: '工具调用 · search',
        contentType: 'search',
        content: {
          total: 12,
          used: 3,
          results: [
            {
              title: '具身智能产业发展观察：从大模型走向场景执行',
              description:
                '从感知、决策到行动闭环，梳理具身智能与机器人、政务服务终端结合的最新趋势。',
              tag: '产业观察',
            },
            {
              title: '人工智能赋能实体经济的若干政策方向',
              description: '聚焦政策支持、产业协同与试点落地，适合作为宏观背景材料引用。',
              tag: '政策解读',
            },
            {
              title: '具身智能在公共服务场景中的应用展望',
              description: '分析政务大厅、巡查、辅助问答等场景中的执行链路与可行边界。',
              tag: '场景应用',
            },
          ],
        },
      },
      {
        type: 'result',
        label: '检索结果',
        contentType: 'result',
        content: {
          badge: '检索结果',
          title: '已筛出 3 篇适合继续写作引用的文章',
          description:
            '覆盖政策、产业趋势与应用落地三个角度，可直接作为后续写作的背景材料或引用来源。',
          items: [
            {
              title: '《具身智能产业发展观察：从大模型走向场景执行》',
              meta: '梳理具身智能在机器人和场景执行层面的最新趋势。',
              url: '#',
            },
            {
              title: '《人工智能赋能实体经济的若干政策方向》',
              meta: '聚焦政策支持、产业协同与试点落地，适合作为宏观背景。',
              url: '#',
            },
            {
              title: '《具身智能在公共服务场景中的应用展望》',
              meta: '分析政务大厅、巡查、辅助问答等场景中的执行链路与边界。',
              url: '#',
            },
          ],
        },
      },
    ],
  },
  review: {
    title: '专项整治方案审校',
    steps: [
      { type: 'think', label: 'Lead Agent 分析任务中' },
      {
        type: 'tool',
        label: '工具调用 · to_do_list',
        contentType: 'pre',
        content:
          '✓ 识别文稿类型与考核目标\n✓ 核对题目、主送单位、时间/逻辑/规范检查\n✓ 调度 审核专员 Claw\n✓ 输出问题清单与修正建议',
      },
      {
        type: 'subAgent',
        label: 'Claw 调用 · 审核专员',
        contentType: 'text',
        content:
          '调用审核专员 Claw，校对文稿逻辑和法规比对冲突，重点检查标题发文地、主送单位、时间表达和逻辑闭环。\n文稿类型：工作方案 · 风险等级：中',
      },
      {
        type: 'skill',
        label: 'Skills 调用 · compliance_check + style_review',
        contentType: 'skills',
        content: {
          summary: '共调用 <strong>2</strong> 个 Skills',
          skills: ['compliance_check', 'style_review'],
        },
      },
      {
        type: 'cli',
        label: 'CLI 工具 · read_file',
        contentType: 'pre',
        content: 'read_file("workspace/专项整治工作方案.docx")\n→ 读取待审校文稿与原版段落',
      },
      {
        type: 'result',
        label: '审核结果',
        contentType: 'result',
        content: {
          badge: '审核结果',
          title: '已整理出 10 项问题，适合继续一键修正或人工核对',
          description:
            '问题主要集中在标题文种、主送单位、时间表述、标点规范和少量措辞。你可以继续走 prompt menu，也可以直接打开联动核对视图。',
          items: [
            { title: '标题与文种', meta: '标题缺少“方案”文种，建议补足正式表达。' },
            { title: '主送单位', meta: '正文抬头需补充具体对象，避免发文范围不清。' },
            {
              title: '时间与逻辑',
              meta: '“本月底前”与“总口径表达”存在歧义，部分段落衔接可进一步收紧。',
            },
          ],
        },
      },
    ],
  },
  revise: {
    title: '专项整治方案（修订版）',
    steps: [
      { type: 'think', label: 'Lead Agent 分析任务中' },
      {
        type: 'tool',
        label: '工具调用 · to_do_list',
        contentType: 'pre',
        content:
          '✓ 读取审核问题清单\n✓ 调度 审核专员 Claw 回写修订\n✓ 保留原有正文结构\n✓ 输出修订版文件',
      },
      {
        type: 'subAgent',
        label: 'Claw 调用 · 审核专员',
        contentType: 'text',
        content:
          '调用审核专员 Claw，依据问题清单执行批量回写修正，并保留原文段落组织方式。\n修正项：10 项 · 输出版本：v2.0',
      },
      {
        type: 'skill',
        label: 'Skills 调用 · rewrite_apply + doc_format',
        contentType: 'skills',
        content: {
          summary: '共调用 <strong>2</strong> 个 Skills',
          skills: ['rewrite_apply', 'doc_format'],
        },
      },
      {
        type: 'cli',
        label: 'CLI 工具 · write_file',
        contentType: 'pre',
        content:
          'write_file("workspace/关于开展专项整治工作的方案（修订版）.docx")\n→ 已按审核建议自动修正',
      },
      {
        type: 'documentOutput',
        contentType: 'documentCard',
        label: '关于开展专项整治工作的方案（修订版）.docx',
        content: {
          description:
            '已根据审核结果完成批量修正，标题、主送单位、时间表达和逻辑衔接均已回写到修订版。',
          footerHint: '已按审核建议自动修正。',
          openEditorLabel: '在右侧编辑器打开',
          body: `<p style="margin: 0; text-align: center; color: red; font-size: 40pt; line-height: 59pt;">XX 市人民政府办公室</p>
  <p style="margin: 0; text-align: center; font-size: 16pt; line-height: 28pt;">&nbsp;</p>
  <p style="margin: 0; text-align: center; font-size: 16pt; line-height: 28pt;">XX 政办发〔2026〕8 号</span></p>
  <p style="margin: 0; text-align: center; font-size: 16pt; line-height: 28pt; border-top: 2px solid red;">&nbsp;</p>
  <p style="margin: 0; text-align: center; font-size: 22pt; line-height: 35pt;">关于进一步优化营商环境的通知</p>
  <p style="margin: 0; text-align: center; font-size: 16pt; line-height: 28pt;">&nbsp;</p>
  <p style="margin: 0; font-size: 16pt; line-height: 28pt;">各处室、直属单位：</p>
  <p style="margin: 0; font-size: 16pt; line-height: 28pt; text-indent: 32pt;">为持续提升政务服务质效，营造稳定公平透明、可预期的营商环境，经研究决定，现就有关事项通知如下。</p>
  <p style="margin: 0; font-size: 16pt; line-height: 28pt; text-indent: 32pt;">一是强化服务意识。各部门要牢固树立以人民为中心的发展思想，优化办事流程，压缩办理时限，提升企业和群众获得感。</p>
  <p style="margin: 0; font-size: 16pt; line-height: 28pt; text-indent: 32pt;">二是完善政策体系。围绕市场准入、要素保障、法治环境等重点领域，及时修订配套制度，确保政策落地见效。</p>
  <p style="margin: 0; font-size: 16pt; line-height: 28pt; text-indent: 32pt;">三是加强督查考核。将营商环境优化纳入年度绩效考核，对工作不力、问题突出的单位予以通报并限期整改。</p>
  <p style="margin: 0; font-size: 16pt; line-height: 28pt; text-indent: 32pt;">请各单位认真贯彻执行。</p>
  <p style="margin: 0; font-size: 16pt; line-height: 28pt; text-align: right; padding-right: 48pt;">XX 市人民政府办公室</p>
  <p style="margin: 0; font-size: 16pt; line-height: 28pt; text-align: right; padding-right: 78pt;">2026年4月1日</p>`,
        },
      },
    ],
  },
  plagiarism: {
    title: '专项整治方案查重',
    steps: [
      { type: 'think', label: 'Lead Agent 分析任务中' },
      {
        type: 'tool',
        label: '工具调用 · to_do_list',
        contentType: 'pre',
        content:
          '✓ 抽取段落并建立比对索引\n✓ 调度 查重专员 Claw\n✓ 匹配相似来源\n✓ 输出重复率与改写建议',
      },
      {
        type: 'subAgent',
        label: '查重专员',
        contentType: 'text',
        content:
          '调用查重专员 Claw，对正文段落进行相似度匹配，并汇总高相似来源。\n累计检索：24 篇资料 · 输出形式：结果清单',
      },
      {
        type: 'skill',
        label: 'Skills 调用 · similarity_match + rewrite_hint',
        contentType: 'skills',
        content: {
          summary: '共调用 <strong>2</strong> 个 Skills',
          skills: ['similarity_match', 'rewrite_hint'],
        },
      },
      {
        type: 'tool',
        label: '工具调用 · search',
        contentType: 'search',
        content: {
          total: 24,
          used: 3,
          results: [
            {
              title: '《基层治理专项行动工作方案》',
              description: '重复率最高的句段集中在“建立台账、限时整改、跟踪问效”等任务安排表述。',
              tag: '重复率 28%',
            },
            {
              title: '《年度重点任务推进清单》',
              description: '主责单位在责任正式和词尾衔接表述，建议补充本单位职责以增强规范化叙述。',
              tag: '重复率 19%',
            },
            {
              title: '《重点领域专项整治实施方案》',
              description: '有原词抄袭与本地存在结构和措辞相似，建议改写背景与目标句式。',
              tag: '重复率 16%',
            },
          ],
        },
      },
      {
        type: 'result',
        label: '查重结果',
        contentType: 'result',
        content: {
          badge: '查重结果',
          title: '总重复率 18.6%，建议优先改写背景说明和任务要求',
          description:
            '示例已汇总 3 处中高相似片段，并整理了来源与改写方向。是否继续生成正式查重报告，可以继续使用当前输入区上方菜单。',
          items: [
            {
              title: '《基层治理专项行动工作方案》 · 28%',
              meta: '重复句集中在“建立台账、限时整改、跟踪问效”，建议重写词项组合与对象表述。',
            },
            {
              title: '《年度重点任务推进清单》 · 19%',
              meta: '责任主体与逻辑连接词表达偏重复，建议补充本单位职责和执行边界。',
            },
            {
              title: '《重点领域专项整治实施方案》 · 16%',
              meta: '背景说明结构相近，建议改写背景与目标段的句式。',
            },
          ],
        },
      },
    ],
  },
  bureauWeeklyReport: {
    title: '面向分局长的警情周报生成',
    steps: [
      { type: 'think', label: 'Lead Agent 分析任务中' },
      {
        type: 'tool',
        label: '工具调用 · to_do_list',
        contentType: 'pre',
        content:
          '✓ 确认周报目标对象：分局长\n✓ 寻找面向分局长的警情数据\n✓ 撰写警情周报正文\n✓ 审校与排版',
      },
      {
        type: 'subAgent',
        label: 'Claw 调用 · <strong>警务报告专家</strong>',
        contentType: 'text',
        content:
          '调用警务报告专家 Claw，生成面向分局长的标准警情周报格式。\n报告层级：分局领导 · 语言风格：简洁摘要 · 周期：2025W15',
      },
      {
        type: 'plainText',
        label: '请提供面向分局长的警情周报数据，或者由智能体自动寻找。',
        contentType: 'plainText',
        content: '请提供面向分局长的警情周报数据，或者由智能体自动寻找。',
      },
    ],
  },
  dataOpsAccess: {
    title: '警务数据源接入',
    steps: [
      { type: 'think', label: 'Lead Agent 分析任务中' },
      {
        type: 'tool',
        label: '工具调用 · to_do_list',
        contentType: 'pre',
        content: '✓ 数据源结构检查\n✓ 数据源连接\n✓ 数据确认',
      },
      {
        type: 'tool',
        label: '工具调用 · sessions_spawn',
        contentType: 'pre',
        content: '',
      },
      {
        type: 'subAgent',
        label: 'Claw 调用 · <strong>数据运营专家</strong>',
        contentType: 'text',
        content:
          '调用数据运营专家 Claw，验证警务数据库连接信息并执行导入。\n目标 host：10.0.8.50 · 数据库：police_ops_db · 用户：police_admin',
      },
      {
        type: 'skill',
        label: 'Skills 调用 · db_connector',
        contentType: 'skills',
        content: {
          summary: '共调用 <strong>1</strong> 个 Skills',
          skills: ['db_connector'],
        },
      },
      {
        type: 'cli',
        label: 'CLI 工具 · mysql -u',
        contentType: 'pre',
        content:
          'mysql -u police_admin -h 10.0.8.50 -p\n→ 连接成功，MySQL 8.0.36\n→ 当前用户：police_admin@10.0.8.50',
      },
      {
        type: 'cli',
        label: 'CLI 工具 · SHOW DATABASES',
        contentType: 'pre',
        content:
          'SHOW DATABASES;\n→ police_ops_db（已选定）\n→ 检测到 18 张数据库表，共 287,436 条警情记录',
      },
      {
        type: 'plainText',
        label:
          '数据源接入成功，共导入名为 police_ops_db 的 18 项数据库表，287,436 条警情记录。要查看当前已接入的所有数据源吗？',
        contentType: 'plainText',
        content:
          '✅ 数据源接入成功，共导入名为 police_ops_db 的 18 项数据库表，287,436 条警情记录。\n\n要查看当前已接入的所有数据源吗？',
      },
    ],
  },
  judgmentFlow: {
    title: '警情研判任务',
    steps: [
      { type: 'think', label: 'Lead Agent 分析任务中' },
      {
        type: 'tool',
        label: '工具调用 · to_do_list',
        contentType: 'pre',
        content:
          '✓ 按区域维度拉取济南市本月警情记录\n✓ 识别时空高发规律\n✓ 生成热力分布分析\n✓ 输出勤务建议',
      },
      {
        type: 'tool',
        label: '工具调用 · sessions_spawn',
        contentType: 'pre',
        content: '',
      },
      {
        type: 'subAgent',
        label: 'Claw 调用 · <strong>警情研判专家</strong>',
        contentType: 'text',
        content:
          '调用警情研判专家 Claw，拉取济南市本月全量警情数据进行时空分析。\n区域：济南市主城区 · 数据条数：2,847 条 · 时间范围：2025/04/01–04/09',
      },
      {
        type: 'skill',
        label: 'Skills 调用 · spatial_analysis + time_series',
        contentType: 'skills',
        content: {
          summary: '共调用 <strong>2</strong> 个 Skills',
          skills: ['spatial_analysis', 'time_series'],
        },
      },
      {
        type: 'cli',
        label: 'CLI 工具 · query_police_db',
        contentType: 'pre',
        content:
          "SELECT area, event_type, occurred_at FROM police_ops_db.cases\nWHERE city='济南市' AND occurred_at >= '2025-04-01'\n→ 返回 2,847 条记录，覆盖 4 个主城区 · 32 个街道",
      },
      {
        type: 'documentOutput',
        contentType: 'documentCard',
        label: '济南市警情研判分析报告_2025年4月.docx',
        content: {
          description:
            '已根据审核结果完成批量修正，标题、主送单位、时间表达和逻辑衔接均已回写到修订版。',
          footerHint: '已按审核建议自动修正。',
          openEditorLabel: '在右侧编辑器打开',
          body: `<p style="margin: 0; text-align: center; color: red; font-size: 40pt; line-height: 59pt; font-family: 方正小标宋_GBK">济南市公安局</p>
  <p style="margin: 0; text-align: center; font-size: 16pt; line-height: 28pt; border-bottom: 2px solid red;">&nbsp;</p>
  <p style="margin: 6px 0 0; text-align: center; font-size: 16pt; line-height: 28pt;">警情研判内部报告 · 2025年4月（截至4月9日）</span></p>
  <p style="margin: 0; text-align: center; font-size: 16pt; line-height: 28pt;">&nbsp;</p>
  <p style="margin: 0; text-align: center; font-size: 22pt; line-height: 35pt;font-family: 方正小标宋_GBK">济南市警情研判分析报告</p>
  <p style="margin: 0; text-align: center; font-size: 16pt; line-height: 28pt;">&nbsp;</p>
  <p style="margin: 0; font-size: 16pt; line-height: 28pt;">各分局、刑侦支队、治安支队：</p>
  <p style="margin: 0; font-size: 16pt; line-height: 28pt; text-indent: 32pt;">本报告基于 2025 年 4 月 1 日至 4 月 9 日济南市主城区警情数据（共 2,847 条），覆盖历下、市中、槐荫、历城 4 个主城区、32 个街道，经时空分析后形成如下研判结论。</p>
  <p style="margin: 0; font-size: 16pt; line-height: 28pt; text-indent: 32pt; font-family: 黑体;">一、高发区域分析</p>
  <p style="margin: 0; font-size: 16pt; line-height: 28pt; text-indent: 32pt;">本月警情呈现明显的区域集中态势，前三位高发区域如下：</p>
  <p style="margin: 0; font-size: 16pt; line-height: 28pt; text-indent: 64pt;">（一）历下区（泉城路—大明湖片区）：共发生警情 724 件，占全市 25.4%，以盗窃和打架斗殴为主，集中于商业街区及夜间娱乐场所周边。</p>
  <p style="margin: 0; font-size: 16pt; line-height: 28pt; text-indent: 64pt;">（二）市中区（舜耕路—英雄山片区）：共发生警情 531 件，占全市 18.7%，以交通事故和噪音扰民为主，集中于早晚高峰及居民密集区。</p>
  <p style="margin: 0; font-size: 16pt; line-height: 28pt; text-indent: 64pt;">（三）槐荫区（振兴街—西站片区）：共发生警情 418 件，占全市 14.7%，以诈骗和财物纠纷为主，与西客站流动人口密集相关。</p>
  <p style="margin: 0; font-size: 16pt; line-height: 28pt; text-indent: 32pt; font-family: 黑体;">二、高峰时段分析</p>
  <p style="margin: 0; font-size: 16pt; line-height: 28pt; text-indent: 32pt;">警情高发时段呈双峰分布：22:00–02:00（夜间峰值，占 38.2%，共 1,087 件）及 12:00–14:00（午间峰值，占 17.1%，共 487 件）。夜间时段以盗窃、打架斗殴为主；午间时段以交通事故、噪音扰民为主。</p>
  <p style="margin: 0; font-size: 16pt; line-height: 28pt; text-indent: 32pt; font-family: 黑体;">三、勤务建议</p>
  <p style="margin: 0; font-size: 16pt; line-height: 28pt; text-indent: 64pt;">（一）历下区建议增派 2 组机动警力，重点部署于泉城路—芙蓉街商圈，时段集中于22:00–02:00。</p>
  <p style="margin: 0; font-size: 16pt; line-height: 28pt; text-indent: 64pt;">（二）市中区建议在早晚高峰（07:30–09:00、17:30–19:00）加强舜耕路沿线路口执勤，减少交通事故。</p>
  <p style="margin: 0; font-size: 16pt; line-height: 28pt; text-indent: 64pt;">（三）槐荫区建议联合铁路部门在西站出站口部署反诈宣传岗，并安排 1 名便衣民警定点巡查。</p>
  <p style="margin: 0; font-size: 16pt; line-height: 28pt; text-align: right; padding-right: 78pt;">&nbsp;</p>
  <p style="margin: 0; font-size: 16pt; line-height: 28pt; text-align: right; padding-right: 48pt;">济南市公安局情报研判中心</p>
  <p style="margin: 0; font-size: 16pt; line-height: 28pt; text-align: right; padding-right: 78pt;">2025年4月9日</p>`,
        },
      },
    ],
  },
  dutyFlow: {
    title: '下周勤务排班方案',
    steps: [
      { type: 'think', label: 'Lead Agent 分析任务中' },
      {
        type: 'tool',
        label: '工具调用 · to_do_list',
        contentType: 'pre',
        content:
          '✓ 读取最新警情研判结果（东城区）\n✓ 匹配下周可用警力资源\n✓ 生成时段与区域排班方案\n✓ 输出可导出勤务表',
      },
      {
        type: 'tool',
        label: '工具调用 · sessions_spawn',
        contentType: 'pre',
        content: '',
      },
      {
        type: 'subAgent',
        label: 'Claw 调用 · <strong>勤务排班专家</strong>',
        contentType: 'text',
        content:
          '调用勤务排班专家 Claw，读取东城区警情热力数据与警力档案，生成最优排班方案。\n目标区域：东城区 · 周期：2025/04/14–04/20 · 可用警力：14 名',
      },
      {
        type: 'skill',
        label: 'Skills 调用 · schedule_optimizer + resource_matcher',
        contentType: 'skills',
        content: {
          summary: '共调用 <strong>2</strong> 个 Skills',
          skills: ['schedule_optimizer', 'resource_matcher'],
        },
      },
      {
        type: 'cli',
        label: 'CLI 工具 · query_police_db',
        contentType: 'pre',
        content:
          "SELECT officer_id, name, shift_available FROM police_ops_db.officers\nWHERE unit='东城区' AND week_of='2025-04-14'\n→ 返回 14 名可用警力，含 3 组机动力量",
      },
      {
        type: 'tableCard',
        label: '东城区下周巡逻勤务方案（2025/4/14-4/20）',
        contentType: 'tableCard',
        content: {
          title: '东城区下周巡逻勤务方案（2025/4/14-4/20）',
          summary: '共安排 28 班次，覆盖 3 个重点区域，调配 14 名警力（含 3 组机动力量）。',
          columns: ['日期', '时段', '重点区域', '负责民警', '优先级'],
          rows: [
            [
              '4/14（周一）',
              '22:00 – 02:00',
              '东华门街道',
              '王建国、李明',
              { text: '高', tag: 'high' },
            ],
            ['4/15（周二）', '12:00 – 14:00', '朝阳门路段', '张磊', { text: '中', tag: 'mid' }],
            [
              '4/16（周三）',
              '22:00 – 02:00',
              '建国门街道',
              '陈志伟、刘芳',
              { text: '高', tag: 'high' },
            ],
          ],
          footerHint: '...共 28 个班次，点击导出查看完整方案',
        },
      },
      {
        type: 'plainText',
        label: '巡逻方案已生成。如需调整警力分配或修改时段安排，请告知我。',
        contentType: 'plainText',
        content: '巡逻方案已生成。如需调整警力分配或修改时段安排，请告知我。',
      },
    ],
  },
  analysisFlow: {
    title: '典型警情案件分析',
    steps: [
      { type: 'think', label: 'Lead Agent 分析任务中' },
      {
        type: 'tool',
        label: '工具调用 · to_do_list',
        contentType: 'pre',
        content:
          '✓ 解析上传的警情数据 xlsx 文件\n✓ 数据清洗与字段分类\n✓ 提取典型警情案件类型\n✓ 生成可视化图表',
      },
      {
        type: 'tool',
        label: '工具调用 · sessions_spawn',
        contentType: 'pre',
        content: '',
      },
      {
        type: 'subAgent',
        label: 'Claw 调用 · <strong>数据分析专家</strong>',
        contentType: 'text',
        content:
          '调用数据分析专家 Claw，对警情数据进行结构化分析。\n数据行数：1,248 条 · 字段数：15 · 时间跨度：2025Q1',
      },
      {
        type: 'skill',
        label: 'Skills 调用 · xlsx + crime_analysis',
        contentType: 'skills',
        content: {
          summary: '共调用 <strong>2</strong> 个 Skills',
          skills: ['xlsx', 'crime_analysis'],
        },
      },
      {
        type: 'cli',
        label: 'CLI 工具 · read_file',
        contentType: 'pre',
        content: '',
      },
      {
        type: 'reportCard',
        label: '典型警情案件分析报告 · 2025Q1',
        contentType: 'reportCard',
        content: {
          title: '典型警情案件分析报告 · 2025Q1',
          summary: '共分析 1,248 条警情记录，识别出 5 类典型案件类型，占总量 82.3%。',
          chartTitle: '警情案件类型分布（Top 5）',
          chartData: [
            { label: '盗窃案件', value: 386, percent: 84 },
            { label: '交通事故', value: 247, percent: 58 },
            { label: '打架斗殴', value: 201, percent: 48 },
            { label: '诈骗案件', value: 168, percent: 41 },
            { label: '噪音扰民', value: 132, percent: 31 },
          ],
        },
      },
      {
        type: 'plainText',
        label: '分析已完成。是否需要基于以上结果生成面向分局长的警情分析周报？',
        contentType: 'plainText',
        content: '分析已完成。是否需要基于以上结果生成面向分局长的警情分析周报？',
      },
    ],
  },
  autoFind: {
    steps: [
      {
        type: 'documentOutput',
        contentType: 'documentCard',
        label: ' 警情分析周报_2025W15_分局长.docx',
        content: {
          description:
            '已根据审核结果完成批量修正，标题、主送单位、时间表达和逻辑衔接均已回写到修订版。',
          footerHint: '已按审核建议自动修正。',
          openEditorLabel: '在右侧编辑器打开',
          body: `<p style="margin: 0; text-align: center; color: red; font-size: 40pt; line-height: 59pt; font-family: 方正小标宋_GBK">XX 市公安局</p>
  <p style="margin: 0; text-align: center; font-size: 16pt; line-height: 28pt; border-bottom: 2px solid red;">&nbsp;</p>
  <p style="margin: 6px 0 0; text-align: center; font-size: 16pt; line-height: 28pt;">警情分析周报 · 第 15 周（2025/04/07–04/13）</span></p>
  <p style="margin: 0; text-align: center; font-size: 16pt; line-height: 28pt;">&nbsp;</p>
  <p style="margin: 0; text-align: center; font-size: 22pt; line-height: 35pt;font-family: 方正小标宋_GBK">警情分析周报</p>
  <p style="margin: 0; text-align: center; font-size: 16pt; line-height: 28pt;">&nbsp;</p>
  <p style="margin: 0; font-size: 16pt; line-height: 28pt;">分局长：</p>
  <p style="margin: 0; font-size: 16pt; line-height: 28pt; text-indent: 32pt;">本周期内，辖区共录入警情记录 1,248 条，经分类研判，识别出 5 类典型警情，合计占总量 82.3%，具体情况如下。</p>
  <p style="margin: 0; font-size: 16pt; line-height: 28pt; text-indent: 32pt; font-family: 黑体;">一、本周警情概况</p>
  <p style="margin: 0; font-size: 16pt; line-height: 28pt; text-indent: 32pt;">本月警情呈现明显的区域集中态势，前三位高发区域如下：</p>
  <p style="margin: 0; font-size: 16pt; line-height: 28pt; text-indent: 64pt;">（一）盗窃案件：共 386 件，占比 31.0%，为最高频类型，主要集中于商业区及夜间时段。。</p>
  <p style="margin: 0; font-size: 16pt; line-height: 28pt; text-indent: 64pt;">（二）交通事故：共 247 件，占比 19.8%，早晚高峰时段高发，建议加强路口执勤。</p>
  <p style="margin: 0; font-size: 16pt; line-height: 28pt; text-indent: 64pt;">（三）打架斗殴：共 201 件，占比 16.1%，多发于娱乐场所周边，22:00 后显著上升。</p>
  <p style="margin: 0; font-size: 16pt; line-height: 28pt; text-indent: 64pt;">（四）诈骗案件：共 168 件，占比 13.5%，电信诈骗占其中 78%，需持续推进防诈宣传。</p>
  <p style="margin: 0; font-size: 16pt; line-height: 28pt; text-indent: 64pt;">（五）噪音扰民：共 132 件，占比 10.6%，居民区投诉为主，多发于午休及深夜时段。</p>
  <p style="margin: 0; font-size: 16pt; line-height: 28pt; text-indent: 32pt; font-family: 黑体;">二、重点关注事项</p>
  <p style="margin: 0; font-size: 16pt; line-height: 28pt; text-indent: 32pt;">本周盗窃案件环比上周上升 12.4%，建议重点强化重点区域夜间巡逻力量，并对案发集中路段部署技防设施。诈骗案件中涉及老年群体的比例达 43%，建议联合社区开展专项宣传活动。</p>
  <p style="margin: 0; font-size: 16pt; line-height: 28pt; text-indent: 32pt; font-family: 黑体;">三、下周工作建议</p>
  <p style="margin: 0; font-size: 16pt; line-height: 28pt; text-indent: 64pt;">（一）增派夜间机动警力 2 组，重点覆盖商业区及娱乐场所密集路段。</p>
  <p style="margin: 0; font-size: 16pt; line-height: 28pt; text-indent: 64pt;">（二）协调反诈中心针对老年群体开展入户宣传，目标覆盖率不低于 60%。</p>
  <p style="margin: 0; font-size: 16pt; line-height: 28pt; text-align: right; padding-right: 78pt;">&nbsp;</p>
  <p style="margin: 0; font-size: 16pt; line-height: 28pt; text-align: right; padding-right: 48pt;">XX市公安局情报研判中心</p>
  <p style="margin: 0; font-size: 16pt; line-height: 28pt; text-align: right; padding-right: 78pt;">2025年4月13日</p>`,
        },
      },
    ],
  },
};

export const mockDocuments = {
  notice: {
    title: '关于推进政务数字化转型工作的通知.docx',
    org: 'XX 市人民政府办公室',
    issueNo: 'XX 政办发〔2025〕12 号',
    mainTitle: '关于推进政务数字化转型工作的通知',
    recipients: '各部门、各单位：',
    body: `<p>为深入贯彻落实党中央、国务院关于数字中国建设的重要部署，加快推进政务服务数字化转型，提升政府治理效能，现将有关事项通知如下。</p>
<h4>一、总体要求</h4>
<p>以习近平新时代中国特色社会主义思想为指导，坚持以人民为中心的发展思想，聚焦数字政府建设目标，全面推进政务服务数字化、智能化转型。到2025年底，实现90%以上政务服务事项"网上办"，50%以上事项"掌上办"。</p>
<h4>二、主要任务</h4>
<p class="sub-p">（一）推进政务数据共享。整合各部门数据资源，建立跨部门数据共享平台，打破"数据孤岛"现象。</p>
<p class="sub-p">（二）提升政务服务效能。优化网上政务服务平台，实现"一网通办"，为企业和群众提供便捷服务体验。</p>
<p class="sub-p">（三）强化数据安全保障。建立健全数据安全管理制度，加强个人信息保护，确保政务数据安全可控。</p>
<h4>三、保障措施</h4>
<p>各部门要高度重视，加强组织领导，明确责任分工，确保各项工作任务落到实处。工作推进情况于每季度末报送市政府办公室汇总。</p>`,
    footerOrg: 'XX市人民政府办公室',
    footerDate: '2025年3月22日',
  },
  report: {
    title: '2025年第一季度工单分析周报.docx',
    org: 'XX市公安局指挥中心',
    issueNo: '工单周报〔2025〕第12期',
    mainTitle: '2025年第一季度工单分析周报',
    recipients: '副市长、局领导：',
    body: `<p>现将2025年第一季度工单办理情况报告如下。</p>
<h4>一、总体情况</h4>
<p>第一季度共受理各类工单1,248件，办结1,180件，办结率94.6%。其中，警务类工单856件，占68.6%；非警务类工单392件，占31.4%。</p>
<h4>二、主要特点</h4>
<p class="sub-p">（一）交通管理类工单占比最高，共342件，占27.4%，主要涉及交通违规举报、交通事故处理等。</p>
<p class="sub-p">（二）治安管理类工单218件，占17.5%，主要涉及噪音扰民、邻里纠纷等。</p>
<p class="sub-p">（三）城市管理类工单189件，占15.1%，主要涉及违规停车、市容环境等。</p>
<h4>三、工作建议</h4>
<p>建议加强交通管理力量部署，优化警力配置，提高工单处置效率。</p>`,
    footerOrg: 'XX市公安局指挥中心',
    footerDate: '2025年4月5日',
  },
};

export const mockAnalysis = {
  complaint: {
    title: '典型问题分析报告 · 2025Q1',
    summary:
      '共分析 <strong>1,248</strong> 条工单，识别出 <strong>5</strong> 类典型投诉问题，占总量 <strong>84.7%</strong>。',
    chartTitle: '投诉类型分布（Top 5）',
    chartData: [
      { label: '交通违规', value: 342, percent: 82 },
      { label: '噪音扰民', value: 218, percent: 52 },
      { label: '邻里纠纷', value: 189, percent: 45 },
      { label: '违规停车', value: 165, percent: 39 },
      { label: '财物纠纷', value: 124, percent: 30 },
    ],
  },
  crime: {
    title: '刑事案件分析报告 · 重点人员轨迹',
    summary:
      '共分析 <strong>3</strong> 名重点人员，识别出 <strong>12</strong> 条异常轨迹，风险等级：<strong style="color: #f56c6c;">高</strong>。',
    chartTitle: '异常行为类型分布',
    chartData: [
      { label: '频繁跨区活动', value: 5, percent: 85 },
      { label: '夜间聚集', value: 3, percent: 60 },
      { label: '敏感区域出入', value: 2, percent: 40 },
      { label: '异常通讯', value: 2, percent: 35 },
    ],
  },
};

export const mockHeartbeatTask = {
  id: Random.guid(),
  summary: '截至3/27 15:00，刚才已新增了20条标签，具体明细如下:',
  items: [
    {
      id: Random.guid(),
      level1: '',
      level2: '',
      level3: '',
      level4: '违规停车举报',
      description: '',
    },
    {
      id: Random.guid(),
      level1: '',
      level2: '',
      level3: '',
      level4: '打架斗殴报警',
      description: '',
    },
    {
      id: Random.guid(),
      level1: '',
      level2: '',
      level3: '',
      level4: '噪音扰民投诉',
      description: '',
    },
    {
      id: Random.guid(),
      level1: '',
      level2: '',
      level3: '',
      level4: '盗窃案件报案',
      description: '',
    },
    {
      id: Random.guid(),
      level1: '',
      level2: '',
      level3: '',
      level4: '交通事故处理',
      description: '',
    },
    {
      id: Random.guid(),
      level1: '',
      level2: '',
      level3: '',
      level4: '邻里纠纷调解',
      description: '',
    },
    {
      id: Random.guid(),
      level1: '',
      level2: '',
      level3: '',
      level4: '电信诈骗举报',
      description: '',
    },
    {
      id: Random.guid(),
      level1: '',
      level2: '',
      level3: '',
      level4: '流动人口登记',
      description: '',
    },
  ],
  levelOptions: {
    level1: ['治安管理', '交通管理', '城市管理', '刑事侦查', '社区服务'],
    level2: ['警情处置', '案件办理', '巡逻防控', '窗口服务', '信息采集'],
    level3: ['一般警情', '重大警情', '紧急警情', '日常事务', '专项工作'],
  },
};

export const mockDataSources = [
  {
    id: Random.guid(),
    name: 'mysql_test',
    type: 'MySQL 8.0.32',
    host: '192.168.1.100',
    tables: 10,
    records: 1200,
    status: 'online',
    lastSync: Random.datetime(),
  },
  {
    id: Random.guid(),
    name: 'police_data',
    type: 'PostgreSQL 14.5',
    host: '192.168.1.101',
    tables: 5,
    records: 2500,
    status: 'online',
    lastSync: Random.datetime(),
  },
  {
    id: Random.guid(),
    name: 'crime_records',
    type: 'MongoDB 5.0',
    host: '192.168.1.102',
    tables: 1,
    records: 3800,
    status: 'offline',
    lastSync: Random.datetime(),
  },
];

export const mockClaws = [
  {
    id: 'document_expert',
    name: '公文写作专家',
    description: '依据GB/T 9704-2012标准生成党政机关公文',
    icon: 'document',
    status: 'online',
    prompts: ['帮我写一份通知', '起草一份会议纪要', '撰写工作汇报'],
  },
  {
    id: 'report_expert',
    name: '工单报告专家',
    description: '生成各类工单分析报告和周报',
    icon: 'report',
    status: 'online',
    prompts: ['生成本周工单周报', '分析月度工单趋势', '制作季度汇报材料'],
  },
  {
    id: 'data_analyst',
    name: '数据分析专家',
    description: '对工单数据进行结构化分析和可视化',
    icon: 'chart',
    status: 'online',
    prompts: ['分析工单数据趋势', '识别典型投诉问题', '生成数据可视化图表'],
  },
  {
    id: 'data_ops',
    name: '数据运营专家',
    description: '管理数据源接入和数据质量',
    icon: 'database',
    status: 'online',
    prompts: ['添加数据源', '检查数据质量', '同步数据'],
  },
  {
    id: 'intel_expert',
    name: '情报探测专家',
    description: '多维度情报分析和风险评估',
    icon: 'search',
    status: 'online',
    prompts: ['分析重点人员轨迹', '评估安全风险', '生成情报报告'],
  },
];

export const mockChatSessions = (() => {
  const sessions: Array<{
    id: string;
    title: string;
    pinned: boolean;
    createdAt: string;
    updatedAt: string;
  }> = [];
  for (let i = 0; i < 5; i++) {
    sessions.push({
      id: Random.guid(),
      title: Random.ctitle(5, 15),
      pinned: Random.boolean(),
      createdAt: Random.datetime(),
      updatedAt: Random.datetime(),
    });
  }
  return sessions;
})();

export const mockWelcomeQuestions = {
  firstTime: [
    { text: '如何使用该产品？', icon: 'help' },
    { text: '该产品能帮助我什么？', icon: 'info' },
  ],
  returning: [
    { text: '我现在有哪些claw？', icon: 'list' },
    { text: '查看最近的工作进度', icon: 'history' },
  ],
};
