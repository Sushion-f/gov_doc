import { mockAnalysis, mockSteps } from './data';

export function mockStreamMessage(
  content: string,
  onMessage: (data: any) => void,
  onError: (error: Error) => void,
  onComplete: () => void
): Promise<void> {
  return new Promise((resolve) => {
    const text = content.toLowerCase();
    let intent = 'general';

    if (text.includes('根据分析撰写警情周报，面向分局长')) {
      intent = 'bureauWeeklyReport';
    } else if (text.includes('自动寻找')) {
      intent = 'autoFind';
    } else if (text.includes('全部修改') || text.includes('修订')) {
      intent = 'revise';
    } else if (text.includes('审核') || text.includes('审校')) {
      intent = 'review';
    } else if (text.includes('查重') || text.includes('重复率')) {
      intent = 'plagiarism';
    } else if (text.includes('研判')) {
      intent = 'judgmentFlow';
    } else if (text.includes('勤务')) {
      intent = 'dutyFlow';
    } else if (text.includes('分析')) {
      intent = 'analysisFlow';
    } else if (text.includes('运营') || text.includes('接入')) {
      intent = 'dataOpsAccess';
    } else if (
      text.includes('公文') ||
      text.includes('通知') ||
      text.includes('写作') ||
      text.includes('起草')
    ) {
      intent = 'document';
    } else if (text.includes('检索') || text.includes('查询')) {
      intent = 'search';
    } else if (text.includes('工单') || text.includes('数据')) {
      intent = 'analysisFlow';
    } else if (text.includes('数据源') || text.includes('mysql') || text.includes('数据库')) {
      intent = 'dataOpsAccess';
    } else if (text.includes('情报') || text.includes('探测') || text.includes('风险')) {
      intent = 'intelligence';
    } else if (text.includes('周报') || text.includes('报告')) {
      intent = 'report';
    }

    const stepPayload = mockSteps[intent as keyof typeof mockSteps] || mockSteps.document;
    const steps = stepPayload.steps;

    setTimeout(() => {
      onMessage({
        type: 'step_title',
        data: {
          title: stepPayload.title,
        },
      });

      steps.forEach((step) => {
        onMessage({
          type: 'step',
          data: {
            type: step.type,
            label: step.label,
            contentType: step.contentType,
            content: step.content,
            open: false,
            streaming: false,
          },
        });
      });

      if (intent === 'analysis') {
        onMessage({ type: 'analysis', data: mockAnalysis.complaint });
      }

      if (intent === 'review') {
        onMessage({
          type: 'decision_prompt',
          data: {
            prompt: '共审核出以下 10 项错误，是否直接修改？',
            description: '上拉菜单与输入区会暂时提示，保持步骤页尺寸稳定。',
            options: [
              {
                id: 'apply_all',
                label: '全部修改',
                variant: 'primary',
                sendText: '请根据审核结果全部修改',
              },
              {
                id: 'ask_more',
                label: '都不要，我来补充',
                variant: 'default',
                text: '请保留正文结构，只修正标题、主送单位和时间表达。',
              },
            ],
          },
        });
      }

      if (intent === 'plagiarism') {
        onMessage({
          type: 'decision_prompt',
          data: {
            prompt: '是否需要生成查重报告？',
            description: '保留输入区上拉菜单和主流程，继续沿用同一输入框。',
            options: [
              { id: 'gen_report', label: '是', variant: 'primary', sendText: '请生成查重报告' },
              { id: 'skip_report', label: '否', variant: 'ghost' },
              {
                id: 'ask_more',
                label: '都不要，我来补充',
                variant: 'default',
                text: '请只保留重复率高于 20% 的句段，并输出改写建议。',
              },
            ],
          },
        });
      }
      if (intent === 'bureauWeeklyReport') {
        onMessage({
          type: 'decision_prompt',
          data: {
            prompt: '数据来源选择',
            description: '请提供面向分局长的警情周报数据来源，或选择其他方式：',
            options: [
              { id: 'gen_report', label: '请自动寻找', variant: 'primary', sendText: '请自动寻找' },
              {
                id: 'ask_more',
                label: '都不要，我来补充',
                variant: 'default',
                text: '请只保留重复率高于 20% 的句段，并输出改写建议。',
              },
            ],
          },
        });
      }
      onMessage({
        type: 'done',
      });
      onComplete();
      resolve();
    }, 100);
  });
}
