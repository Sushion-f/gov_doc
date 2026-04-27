/**
 * 会话内存存储（阶段 0 替代 IndexedDB；后续阶段由 AgentLoop API 替换）。
 * 类型来自全局 `types.d.ts`。
 */

const sessions = new Map<string, ChatSessionDetail>();

const ok = <T>(data: T, message = 'success'): ApiResponse<T> => ({
  code: 200,
  message,
  data,
});

const nowIso = () => new Date().toISOString();
const genId = (prefix: string) =>
  `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;

function jsonClone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}

function sortSessions(list: ChatSessionDetail[]): ChatSessionDetail[] {
  return [...list].sort((a, b) => {
    if (a.pinned !== b.pinned) return a.pinned ? -1 : 1;
    return new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime();
  });
}

function buildDefaultSession(): ChatSessionDetail {
  const ts = nowIso();
  return {
    id: genId('session'),
    isNew: true,
    title: '新对话',
    pinned: false,
    createdAt: ts,
    updatedAt: ts,
    messages: [],
  };
}

function toStaticDetail(session: ChatSessionDetail): ChatSessionDetail {
  const detail = jsonClone(session);
  detail.messages = detail.messages.map((m) => ({
    ...m,
    streaming: false,
  }));
  return detail;
}

export async function createNewChat(): Promise<ApiResponse<ChatSession>> {
  const session = buildDefaultSession();
  sessions.set(session.id, jsonClone(session));
  const { id, title, pinned, createdAt, updatedAt, isNew } = session;
  return ok({ id, title, pinned, createdAt, updatedAt, isNew });
}

export async function getChatList(params?: {
  page?: number;
  pageSize?: number;
  pinned?: boolean;
}): Promise<ApiResponse<PaginatedResponse<ChatSession>>> {
  let all = sortSessions([...sessions.values()]);

  if (typeof params?.pinned === 'boolean') {
    all = all.filter((s) => s.pinned === params.pinned);
  }
  const page = params?.page || 1;
  const pageSize = params?.pageSize || 20;
  const start = (page - 1) * pageSize;
  const pageItems = all.slice(start, start + pageSize).map((s) => ({
    id: s.id,
    title: s.title,
    subtitle: s.subtitle,
    pinned: s.pinned,
    isNew: s.isNew,
    createdAt: s.createdAt,
    updatedAt: s.updatedAt,
  }));
  return ok({
    total: all.length,
    page,
    pageSize,
    list: pageItems,
  });
}

export async function getChatDetail(sessionId: string): Promise<ApiResponse<ChatSessionDetail>> {
  let session = sessions.get(sessionId);
  if (!session) {
    session = buildDefaultSession();
    session.id = sessionId;
    sessions.set(sessionId, jsonClone(session));
  }
  return ok(toStaticDetail(session));
}

export async function deleteChat(sessionId: string): Promise<ApiResponse<null>> {
  sessions.delete(sessionId);
  return ok(null);
}

export async function renameChat(sessionId: string, title: string): Promise<ApiResponse<null>> {
  const session = sessions.get(sessionId);
  if (!session) return ok(null);
  session.title = title.trim() || session.title;
  session.updatedAt = nowIso();
  sessions.set(sessionId, jsonClone(session));
  return ok(null);
}

export async function pinChat(sessionId: string, pinned: boolean): Promise<ApiResponse<null>> {
  const session = sessions.get(sessionId);
  if (!session) return ok(null);
  session.pinned = pinned;
  session.updatedAt = nowIso();
  sessions.set(sessionId, jsonClone(session));
  return ok(null);
}

export async function addMessage(
  sessionId: string,
  message: Omit<ChatMessage, 'id' | 'createdAt'> | ChatMessage,
): Promise<ApiResponse<string>> {
  let session = sessions.get(sessionId);
  if (!session) {
    session = buildDefaultSession();
    session.id = sessionId;
  }

  const msg = message as ChatMessage;
  const normalized: ChatMessage = {
    ...msg,
    id: msg.id || genId('msg'),
    createdAt: msg.createdAt || nowIso(),
  };

  const idx = session.messages.findIndex((m) => m.id === normalized.id);
  if (idx >= 0) {
    session.messages[idx] = { ...session.messages[idx], ...normalized };
  } else {
    session.messages.push(normalized);
  }

  if (normalized.role === 'user') {
    const firstUser = session.messages.find((m) => m.role === 'user');
    if (firstUser?.id === normalized.id) {
      const nextTitle = normalized.content.trim();
      if (nextTitle) {
        session.title = nextTitle.length > 24 ? `${nextTitle.slice(0, 24)}...` : nextTitle;
      }
      session.isNew = false;
    }
  }

  session.updatedAt = nowIso();
  sessions.set(sessionId, jsonClone(session));
  return ok(normalized.id);
}

/** 占位流式：后续阶段由真实 SSE 替换 */
export function streamMessage(
  _data: {
    content: string;
    sessionId?: string;
    model?: string;
    clawId?: string;
    attachments?: string[];
  },
  onMessage: (data: { type: string; data?: unknown }) => void,
  _onError: (error: Error) => void,
  onComplete: () => void,
): Promise<void> {
  return new Promise((resolve) => {
    queueMicrotask(() => {
      onMessage({
        type: 'step_title',
        data: { title: '处理中' },
      });
      onMessage({
        type: 'step',
        data: {
          type: 'think',
          label: '说明',
          contentType: 'text',
          content:
            '当前为本地占位流式输出。接入 AgentLoop 的 POST /conversations/run 与 SSE 后将展示真实步骤与结果。',
        },
      });
      onMessage({
        type: 'text',
        data: { text: '（占位）请继续完成阶段 4 对接以连接真实后端。' },
      });
      onMessage({ type: 'done', data: {} });
      onComplete();
      resolve();
    });
  });
}
