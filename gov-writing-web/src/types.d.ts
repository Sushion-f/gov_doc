// 全局类型声明
export {};

declare global {
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
    attachment?: unknown;
    skill?: string | null;
    steps?: {
      title: string;
      steps: Step[];
    };
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
    content?: unknown;
    contentType?: StepContentType;
    open?: boolean;
    timestamp?: number;
    streaming?: boolean;
    [key: string]: unknown;
  }

  interface StepContent {
    total?: number;
    used?: number;
    summary?: string;
    skills?: string[];
    results?: unknown[];
  }

  interface ApiResponse<T = unknown> {
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
