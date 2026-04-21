// 全局类型声明
export { };

declare module '*.vue' {
  import type { DefineComponent } from 'vue';
  const component: DefineComponent<{}, {}, any>
  export default component
}

declare global {
  // 会话相关类型
  interface ChatSession {
    id: string;
    title: string;
    subtitle?: string;
    pinned: boolean;
    isNew?: boolean;
    createdAt: string;
    updatedAt: string;
  }

  interface ChatMessage {
    id: string;
    role: 'user' | 'assistant';
    content: string;
    createdAt: string;
    attachment?: any;
    skill?: string | null;
    steps?: {
      title: string;
      steps: Step[];
    };
    document?: Document;
    documentVisible?: boolean;
    analysis?: Analysis;
    analysisVisible?: boolean;
    heartbeatTask?: HeartbeatTask;
    heartbeatVisible?: boolean;
    text?: string;
    textVisible?: boolean;
    streaming?: boolean;
    decisionPrompt?: {
      prompt: string;
      description?: string;
      options: Array<{
        id: string;
        label: string;
        variant?: 'default' | 'primary' | 'ghost';
        sendText?: string;
      }>;
    };
  }

  interface ChatSessionDetail extends ChatSession {
    messages: ChatMessage[];
  }

  // Claw相关类型
  interface Claw {
    id: string;
    name: string;
    description: string;
    icon: string;
    status: 'online' | 'offline';
    prompts: string[];
  }

  // 数据源相关类型
  interface DataSource {
    id: string;
    name: string;
    type: string;
    host: string;
    tables: number;
    records: number;
    status: 'online' | 'offline';
    lastSync: string;
  }

  // 分析相关类型
  interface AnalysisItem {
    title: string;
    summary: string;
    chartTitle: string;
    chartData: ChartDataItem[];
  }

  interface Analysis {
    title: string;
    summary: string;
    chartTitle: string;
    chartData: ChartDataItem[];
  }

  interface ChartDataItem {
    label: string;
    value: number;
    percent: number;
  }

  // 文档相关类型
  interface DocumentTemplate {
    id: string;
    name: string;
    description: string;
  }

  interface Document {
    title: string;
    org: string;
    issueNo: string;
    mainTitle: string;
    recipients: string;
    body: string;
    footerOrg: string;
    footerDate: string;
  }

  // 心跳任务相关类型
  interface HeartbeatItem {
    id: string;
    level1: string;
    level2: string;
    level3: string;
    level4: string;
    description: string;
  }

  interface HeartbeatTaskItem {
    id: string;
    level1: string;
    level2: string;
    level3: string;
    level4: string;
    description: string;
  }

  interface LevelOptions {
    level1: string[];
    level2: string[];
    level3: string[];
  }

  interface HeartbeatTask {
    id: string;
    summary: string;
    items: HeartbeatItem[] | HeartbeatTaskItem[];
    levelOptions: LevelOptions;
  }

  // 步骤相关类型
  type StepType =
    | 'think'
    | 'tool'
    | 'claw'
    | 'skill'
    | 'cli'
    | 'template'
    | 'subAgent'
    | 'document'
    | 'documentOutput'
    | 'reportCard'
    | 'tableCard'
    | 'plainText'
    | 'searchResult'
    | 'result';

  type StepContentType =
    | 'text'
    | 'search'
    | 'pre'
    | 'json'
    | 'html'
    | 'skills'
    | 'template'
    | 'documentCard'
    | 'reportCard'
    | 'tableCard'
    | 'plainText'
    | 'searchResult'
    | 'result';

  interface Step {
    id?: string;
    type: StepType;
    label?: string;
    content?: any;
    contentType?: StepContentType;
    open?: boolean;
    timestamp?: number;
    streaming?: boolean;
    [key: string]: any;
  }

  interface StepContent {
    total?: number;
    used?: number;
    summary?: string;
    skills?: string[];
    results?: any[];
  }

  // 流式消息相关类型
  interface StreamMessage {
    type: 'step' | 'document' | 'analysis' | 'heartbeat' | 'text' | 'done' | 'error';
    data:
    | Step
    | Document
    | Analysis
    | HeartbeatTask
    | string
    | { messageId: string }
    | { code: number; message: string };
  }

  interface StreamDoneData {
    messageId: string;
  }

  interface StreamErrorData {
    code: number;
    message: string;
  }

  // 聊天请求相关类型
  interface ChatRequest {
    sessionId?: string;
    content: string;
    model?: 'minimax' | 'qwen' | 'deepseek';
    clawId?: string;
    attachments?: Attachment[];
  }

  interface Attachment {
    id: string;
    name: string;
    type: string;
    url: string;
  }

  // 通用响应类型
  interface ApiResponse<T = any> {
    code: 200 | 400 | 404 | 500;
    message: string;
    data: T;
  }

  interface PaginatedResponse<T> {
    total: number;
    page: number;
    pageSize: number;
    list: T[];
  }
}
