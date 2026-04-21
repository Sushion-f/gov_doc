import {
  ApiResponse,
  ChatMessage,
  ChatSession,
  ChatSessionDetail,
  PaginatedResponse,
} from '@/types';

const DB_NAME = 'chat-mock-db';
const DB_VERSION = 1;
const STORE_SESSIONS = 'sessions';

const ok = <T>(data: T, message = 'success'): ApiResponse<T> => ({
  code: 200,
  message,
  data,
});

const nowIso = () => new Date().toISOString();
const genId = (prefix: string) =>
  `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;

/** 剥离 Vue Proxy 等不可结构化克隆的数据，保证 IndexedDB 写入稳定 */
function jsonClone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains(STORE_SESSIONS)) {
        db.createObjectStore(STORE_SESSIONS, { keyPath: 'id' });
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

function reqToPromise<T>(req: IDBRequest<T>): Promise<T> {
  return new Promise((resolve, reject) => {
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

type StoredSession = ChatSessionDetail;

async function getAllSessionsRaw(): Promise<StoredSession[]> {
  const db = await openDb();
  return new Promise<StoredSession[]>((resolve, reject) => {
    const tx = db.transaction(STORE_SESSIONS, 'readonly');
    const store = tx.objectStore(STORE_SESSIONS);
    const req = store.getAll() as IDBRequest<StoredSession[]>;
    req.onsuccess = () => resolve(req.result || []);
    req.onerror = () => reject(req.error);
    tx.oncomplete = () => db.close();
    tx.onerror = () => {
      db.close();
      reject(tx.error);
    };
  });
}

async function getSessionRaw(sessionId: string): Promise<StoredSession | undefined> {
  const db = await openDb();
  return new Promise<StoredSession | undefined>((resolve, reject) => {
    const tx = db.transaction(STORE_SESSIONS, 'readonly');
    const store = tx.objectStore(STORE_SESSIONS);
    const req = store.get(sessionId) as IDBRequest<StoredSession | undefined>;
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
    tx.oncomplete = () => db.close();
    tx.onerror = () => {
      db.close();
      reject(tx.error);
    };
  });
}

async function putSessionRaw(session: StoredSession): Promise<void> {
  const db = await openDb();
  const plain = jsonClone(session);
  await new Promise<void>((resolve, reject) => {
    const tx = db.transaction(STORE_SESSIONS, 'readwrite');
    const store = tx.objectStore(STORE_SESSIONS);
    const req = store.put(plain);
    req.onerror = () => reject(req.error);
    tx.oncomplete = () => {
      db.close();
      resolve();
    };
    tx.onerror = () => {
      db.close();
      reject(tx.error);
    };
  });
}

async function deleteSessionRaw(sessionId: string): Promise<void> {
  const db = await openDb();
  await new Promise<void>((resolve, reject) => {
    const tx = db.transaction(STORE_SESSIONS, 'readwrite');
    const store = tx.objectStore(STORE_SESSIONS);
    const req = store.delete(sessionId);
    req.onerror = () => reject(req.error);
    tx.oncomplete = () => {
      db.close();
      resolve();
    };
    tx.onerror = () => {
      db.close();
      reject(tx.error);
    };
  });
}

function sortSessions(list: StoredSession[]): StoredSession[] {
  return [...list].sort((a, b) => {
    if (a.pinned !== b.pinned) return a.pinned ? -1 : 1;
    return new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime();
  });
}

function buildDefaultSession(): StoredSession {
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

function toStaticDetail(session: StoredSession): ChatSessionDetail {
  const detail = structuredClone(session) as ChatSessionDetail;
  detail.messages = detail.messages.map((m) => ({
    ...m,
    // 详情回显采用静态态，不再显示流式中间态
    streaming: false,
  }));
  return detail;
}

export async function createNewChat(): Promise<ApiResponse<ChatSession>> {
  const session = buildDefaultSession();
  await putSessionRaw(session);
  const { id, title, pinned, createdAt, updatedAt, isNew } = session;
  return ok({ id, title, pinned, createdAt, updatedAt, isNew });
}

export async function getChatList(params?: {
  page?: number;
  pageSize?: number;
  pinned?: boolean;
}): Promise<ApiResponse<PaginatedResponse<ChatSession>>> {
  // 仅返回已持久化的会话；勿在列表前插入随机 id 的「占位会话」，否则会与父组件 currentSessionId 错位，导致消息写入 A、侧栏选中 B，切换后无法回显
  let all = sortSessions(await getAllSessionsRaw());

  if (typeof params?.pinned === 'boolean') {
    all = all.filter((s) => s.pinned === params.pinned);
  }
  const page = params?.page || 1;
  const pageSize = params?.pageSize || 20;
  const start = (page - 1) * pageSize;
  const pageItems = all.slice(start, start + pageSize);
  return ok({
    total: all.length,
    page,
    pageSize,
    list: pageItems,
  });
}

export async function getChatDetail(sessionId: string): Promise<ApiResponse<ChatSessionDetail>> {
  let session = await getSessionRaw(sessionId);
  if (!session) {
    session = buildDefaultSession();
    session.id = sessionId;
    await putSessionRaw(session);
  }
  return ok(toStaticDetail(session));
}

export async function deleteChat(sessionId: string): Promise<ApiResponse<null>> {
  await deleteSessionRaw(sessionId);
  return ok(null);
}

export async function renameChat(sessionId: string, title: string): Promise<ApiResponse<null>> {
  const session = await getSessionRaw(sessionId);
  if (!session) return ok(null);
  session.title = title.trim() || session.title;
  session.updatedAt = nowIso();
  await putSessionRaw(session);
  return ok(null);
}

export async function pinChat(sessionId: string, pinned: boolean): Promise<ApiResponse<null>> {
  const session = await getSessionRaw(sessionId);
  if (!session) return ok(null);
  session.pinned = pinned;
  session.updatedAt = nowIso();
  await putSessionRaw(session);
  return ok(null);
}

export async function addMessage(
  sessionId: string,
  message: Omit<ChatMessage, 'id' | 'createdAt'> | ChatMessage
): Promise<ApiResponse<string>> {
  let session = await getSessionRaw(sessionId);
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
  await putSessionRaw(session);
  return ok(normalized.id);
}

export function streamMessage(
  data: {
    content: string;
    sessionId?: string;
    model?: string;
    clawId?: string;
    attachments?: string[];
  },
  onMessage: (data: any) => void,
  onError: (error: Error) => void,
  onComplete: () => void
): Promise<void> {
  // 这里使用mock实现，实际项目中应该使用fetchEventSource
  return import('@/mock/stream').then(({ mockStreamMessage }) => {
    return mockStreamMessage(data.content, onMessage, onError, onComplete);
  });
}
