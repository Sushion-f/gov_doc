import ClawStep from './ClawStep.vue';
import CliStep from './CliStep.vue';
import DocumentOutputStep from './DocumentOutputStep.vue';
import PlainTextStep from './PlainTextStep.vue';
import ReportCardStep from './ReportCardStep.vue';
import ResultStep from './ResultStep.vue';
import SkillStep from './SkillStep.vue';
import SubAgentStep from './SubAgentStep.vue';
import TableCardStep from './TableCardStep.vue';
import TemplateRecommendStep from './TemplateRecommendStep.vue';
import ThinkStep from './ThinkStep.vue';
import ToolStep from './ToolStep.vue';

// 步骤组件映射
export const stepComponents: Record<string, any> = {
  think: ThinkStep,
  tool: ToolStep,
  claw: ClawStep,
  skill: SkillStep,
  cli: CliStep,
  template: TemplateRecommendStep,
  subAgent: SubAgentStep,
  documentOutput: DocumentOutputStep,
  reportCard: ReportCardStep,
  tableCard: TableCardStep,
  plainText: PlainTextStep,
  result: ResultStep,
};

export default stepComponents;
