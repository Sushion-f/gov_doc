import Mock from 'mockjs';
import { mockAnalysis, mockChatSessions, mockClaws, mockDataSources, mockDocuments, mockHeartbeatTask, mockSteps } from './data';

Mock.setup({
  timeout: '200-500',
});

const chatSessions = [...mockChatSessions];
const sessionMessages: Record<string, Array<{
  id: string;
  role: 'user' | 'assistant';
  content: string;
  createdAt: string;
}>> = {};

// 初始化会话消息
chatSessions.forEach(session => {
  sessionMessages[session.id] = [];
});

// 新会话
Mock.mock(RegExp('.*chat/chat/new.*'), 'post', () => {
  const id = Mock.Random.guid();
  const session = {
    id,
    title: '新对话',
    pinned: false,
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  };
  chatSessions.unshift(session);
  sessionMessages[id] = [];
  return {
    code: 0,
    message: 'success',
    data: session,
  };
});

// 会话列表
Mock.mock(RegExp('.*chat/chat/list.*'), 'get', (options) => {
  const url = new URL(options.url, 'http://localhost');
  const page = parseInt(url.searchParams.get('page') || '1');
  const pageSize = parseInt(url.searchParams.get('pageSize') || '20');
  const pinned = url.searchParams.get('pinned');

  let filtered = chatSessions;
  if (pinned !== null) {
    filtered = chatSessions.filter((s) => s.pinned === (pinned === 'true'));
  }

  const start = (page - 1) * pageSize;
  const list = filtered.slice(start, start + pageSize);

  return {
    code: 0,
    message: 'success',
    data: {
      total: filtered.length,
      page,
      pageSize,
      list,
    },
  };
});

// 会话详情
Mock.mock(RegExp('.*chat/chat/detail/.*'), 'get', (options) => {
  const sessionId = options.url.match(/\/detail\/([\w-]+)/)?.[1] as string;
  const session = chatSessions.find((s) => s.id === sessionId);
  if (!session) {
    return {
      code: 1004,
      message: 'Session not found',
      data: null,
    };
  }
  return {
    code: 0,
    message: 'success',
    data: {
      ...session,
      messages: sessionMessages[sessionId] || [],
    },
  };
});

// 重命名会话
Mock.mock(RegExp('.*chat.*chat.*rename.*'), 'put', (options) => {
  const sessionId = options.url.match(/\/chat\/([^\/]+)\/rename/)?.[1];
  const body = JSON.parse(options.body || '{}');
  const session = chatSessions.find((s) => s.id === sessionId);
  if (session) {
    session.title = body.title || session.title;
    session.updatedAt = new Date().toISOString();
  }
  return {
    code: 0,
    message: 'success',
    data: null,
  };
});

// 置顶会话
Mock.mock(RegExp('.*chat.*chat.*pin.*'), 'put', (options) => {
  const sessionId = options.url.match(/\/chat\/([^\/]+)\/pin/)?.[1];
  const body = JSON.parse(options.body || '{}');
  const session = chatSessions.find((s) => s.id === sessionId);
  if (session) {
    session.pinned = body.pinned ?? !session.pinned;
    session.updatedAt = new Date().toISOString();
  }
  return {
    code: 0,
    message: 'success',
    data: null,
  };
});

// 删除会话
Mock.mock(RegExp('.*chat/chat/delete/.*'), 'delete', (options) => {
  const sessionId = options.url.match(/\/delete\/([\w-]+)/)?.[1] as string;
  const index = chatSessions.findIndex((s) => s.id === sessionId);
  if (index > -1) {
    chatSessions.splice(index, 1);
    delete sessionMessages[sessionId];
  }
  return {
    code: 0,
    message: 'success',
    data: null,
  };
});

// 添加消息
Mock.mock(RegExp('.*chat/chat/message/add.*'), 'post', (options) => {
  const body = JSON.parse(options.body || '{}');
  const { sessionId, message } = body;
  if (sessionId && sessionMessages[sessionId]) {
    sessionMessages[sessionId].push({
      ...message,
      id: Mock.Random.guid(),
      createdAt: new Date().toISOString(),
    });
    const session = chatSessions.find((s) => s.id === sessionId);
    if (session) {
      session.updatedAt = new Date().toISOString();
      if (session.title === '新对话' && message.role === 'user') {
        session.title = message.content.slice(0, 20) + (message.content.length > 20 ? '...' : '');
      }
    }
  }
  return {
    code: 0,
    message: 'success',
    data: null,
  };
});

// Claw列表
Mock.mock(RegExp('.*chat/claw/list.*'), 'get', () => {
  return {
    code: 0,
    message: 'success',
    data: {
      list: mockClaws,
    },
  };
});

// Claw详情
Mock.mock(RegExp('.*chat/claw/detail/.*'), 'get', (options) => {
  const clawId = options.url.match(/\/claw\/detail\/([\w-]+)/)?.[1];
  const claw = mockClaws.find((c) => c.id === clawId);
  return {
    code: claw ? 0 : 1004,
    message: claw ? 'success' : 'Claw not found',
    data: claw || null,
  };
});

// Claw提示
Mock.mock(RegExp('.*chat/claw/[\w-]+/prompts.*'), 'get', (options) => {
  const clawId = options.url.match(/\/claw\/([\w-]+)\/prompts/)?.[1];
  const claw = mockClaws.find((c) => c.id === clawId);
  return {
    code: 0,
    message: 'success',
    data: {
      prompts: claw?.prompts || [],
    },
  };
});

// 数据源列表
Mock.mock(RegExp('.*chat/datasource/list.*'), 'get', () => {
  return {
    code: 0,
    message: 'success',
    data: {
      list: mockDataSources,
    },
  };
});

// 添加数据源
Mock.mock(RegExp('.*chat/datasource/add.*'), 'post', () => {
  return {
    code: 0,
    message: 'success',
    data: {
      id: Mock.Random.guid(),
      status: 'online',
      lastSync: new Date().toISOString(),
    },
  };
});

// 测试数据源
Mock.mock(RegExp('.*chat/datasource/test.*'), 'post', () => {
  return {
    code: 0,
    message: 'success',
    data: {
      connected: true,
      version: 'MySQL 8.0.32',
      tables: 10,
    },
  };
});

// 删除数据源
Mock.mock(RegExp('.*chat/datasource/delete/.*'), 'delete', () => {
  return {
    code: 0,
    message: 'success',
    data: null,
  };
});

// 同步数据源
Mock.mock(RegExp('.*chat/datasource/sync/.*'), 'post', () => {
  return {
    code: 0,
    message: 'success',
    data: {
      synced: true,
      records: 1200,
      syncedAt: new Date().toISOString(),
    },
  };
});

// 心跳任务列表
Mock.mock(RegExp('.*chat/heartbeat/list.*'), 'get', () => {
  return {
    code: 0,
    message: 'success',
    data: {
      list: [mockHeartbeatTask],
    },
  };
});

// 心跳任务详情
Mock.mock(RegExp('.*chat/heartbeat/detail/.*'), 'get', () => {
  return {
    code: 0,
    message: 'success',
    data: mockHeartbeatTask,
  };
});

// 保存心跳任务
Mock.mock(RegExp('.*chat/heartbeat/save.*'), 'post', () => {
  return {
    code: 0,
    message: 'success',
    data: {
      id: Mock.Random.guid(),
      saved: true,
    },
  };
});

// 文档模板
Mock.mock(RegExp('.*chat/document/templates.*'), 'get', () => {
  return {
    code: 0,
    message: 'success',
    data: {
      list: [
        { id: 'notice', name: '通知', description: '党政机关通知公文' },
        { id: 'report', name: '报告', description: '工作报告' },
        { id: 'summary', name: '总结', description: '工作总结' },
      ],
    },
  };
});

// 分析历史
Mock.mock(RegExp('.*chat/analysis/history.*'), 'get', () => {
  return {
    code: 0,
    message: 'success',
    data: {
      list: [mockAnalysis.complaint, mockAnalysis.crime],
    },
  };
});

export function detectIntent(content: string): string {
  const text = content.toLowerCase();
  if (text.includes('公文') || text.includes('通知') || text.includes('写作') || text.includes('起草')) {
    return 'document';
  }
  if (text.includes('分析') || text.includes('工单') || text.includes('数据')) {
    return 'analysis';
  }
  if (text.includes('数据源') || text.includes('mysql') || text.includes('数据库')) {
    return 'dataOps';
  }
  if (text.includes('情报') || text.includes('探测') || text.includes('风险')) {
    return 'intelligence';
  }
  return 'general';
}

export { mockAnalysis, mockClaws, mockDataSources, mockDocuments, mockHeartbeatTask, mockSteps };

export default Mock;
