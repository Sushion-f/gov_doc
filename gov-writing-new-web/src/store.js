import { computed, reactive } from "vue";
import { marked } from "marked";
import {
  EVENT_STREAM_TIMEOUT_MS,
  LONG_REQUEST_TIMEOUT_MS,
  postForm,
  requestJson,
  readEventStream,
  streamEventStream,
  uploadFile,
} from "./api";

marked.use({
  breaks: true,
  gfm: true,
});

export const state = reactive({
  bootstrapLoading: false,
  runLoading: false,
  user: null,
  modelOptions: [],
  skills: [],
  conversations: [],
  currentConversationId: null,
  currentConversation: null,
  currentEvents: [],
  currentRunId: null,
  latestTodoList: null,
  contextUsage: null,
  compactionHistory: [],
  pendingPromptMenu: null,
  activeQuickSkill: "",
  sidebarCollapsed: false,
  workspaceView: "recent",
  workspaceItems: [],
  workspaceTree: [],
  currentDocument: null,
  settingsProfile: null,
  settingsMemory: null,
  dictionaries: { whiteList: [], blackList: [] },
  templates: [],
  errorMessage: "",
  /** 主 Agent 规划阶段流式推理文本（仅当前 run） */
  streamingPlannerReasoning: "",
  /** 流式正文更新计数，用于触发聊天区滚动到底部 */
  streamScrollTick: 0,
  /** 点赞/点踩本地状态 messageId -> "like" | "dislike" */
  messageFeedbacks: {},
});

let activeRunController = null;
const KNOWN_PROTOCOL_TYPES = new Set([
  "system",
  "block_append",
  "block_update",
  "message_complete",
  "result",
  // 兼容旧事件类型（暂不再主动发，但前端容错）
  "assistant",
  "stream_event",
]);

function normalizeIncomingEvent(event) {
  if (!event || typeof event !== "object") {
    return event;
  }
  const type = String(event.type || "");
  if (KNOWN_PROTOCOL_TYPES.has(type)) {
    return event;
  }
  if (import.meta.env.DEV) {
    console.warn("[Protocol] Unknown item type:", type, event);
  }
  return { ...event, type: "system", subtype: "unknown", data: event };
}

function getStreamingAssistantMessage() {
  const msgs = state.currentConversation?.messages || [];
  for (let i = msgs.length - 1; i >= 0; i--) {
    const m = msgs[i];
    if (m && m.role === "assistant" && String(m.id).startsWith("temp-assistant")) {
      return m;
    }
  }
  return null;
}

function upsertContentBlock(block, { updateKind = "append" } = {}) {
  const target = getStreamingAssistantMessage();
  if (!target) {
    return;
  }
  if (!Array.isArray(target.contentBlocks)) {
    target.contentBlocks = [];
  }
  const existingIndex = target.contentBlocks.findIndex((item) => item && item.id === block.id);
  if (updateKind === "update" || existingIndex >= 0) {
    if (existingIndex >= 0) {
      target.contentBlocks.splice(existingIndex, 1, { ...target.contentBlocks[existingIndex], ...block });
    } else {
      target.contentBlocks.push(block);
    }
  } else {
    target.contentBlocks.push(block);
  }
  if (block.type === "text") {
    const textAggregate = target.contentBlocks
      .filter((item) => item && item.type === "text")
      .map((item) => String(item.text || ""))
      .join("\n\n")
      .trim();
    if (textAggregate) {
      target.content = textAggregate;
      target.contentHtml = marked.parse(textAggregate);
    }
  }
  state.streamScrollTick += 1;
}

function replaceMessageWithFinalBlocks(finalMessageId, blocks) {
  const msgs = state.currentConversation?.messages || [];
  for (let i = msgs.length - 1; i >= 0; i--) {
    const m = msgs[i];
    if (!m || m.role !== "assistant") {
      continue;
    }
    if (String(m.id).startsWith("temp-assistant")) {
      m.id = finalMessageId || m.id;
      m.contentBlocks = Array.isArray(blocks) && blocks.length ? blocks : m.contentBlocks || [];
      const textAggregate = (m.contentBlocks || [])
        .filter((item) => item && item.type === "text")
        .map((item) => String(item.text || ""))
        .join("\n\n")
        .trim();
      if (textAggregate) {
        m.content = textAggregate;
        m.contentHtml = marked.parse(textAggregate);
      }
      state.streamScrollTick += 1;
      return;
    }
  }
}

function applyProtocolItem(item, conversationId) {
  const normalized = normalizeIncomingEvent(item);
  if (normalized.type === "system") {
    if (normalized.subtype === "todo_list" && normalized.data?.steps) {
      state.latestTodoList = {
        ...normalized.data,
        currentStepId: normalized.data.current_step_id || normalized.data.currentStepId || null,
      };
      if (state.currentConversation?.id === conversationId) {
        state.currentConversation.latestTodoList = state.latestTodoList;
      }
    }
    if (normalized.subtype === "waiting_input") {
      state.pendingPromptMenu = normalized.data?.promptMenu
        ? {
            ...normalized.data,
            promptMenu: normalized.data.promptMenu,
          }
        : state.pendingPromptMenu;
      if (state.currentConversation?.id === conversationId) {
        state.currentConversation.pendingPromptMenu =
          state.pendingPromptMenu?.promptMenu || state.currentConversation.pendingPromptMenu;
      }
    }
    return normalized;
  }
  if (normalized.type === "block_append" || normalized.type === "block_update") {
    ensureCurrentConversationShape(conversationId);
    const block = normalized.block || {};
    if (!block || !block.type) {
      return normalized;
    }
    // thinking block 流式输出同时镜像到顶部 streamingPlannerReasoning 上
    if (block.type === "thinking") {
      state.streamingPlannerReasoning = String(block.thinking || "");
    }
    // todo_list block 同步到 latestTodoList，让原有 todo 条继续工作
    if (block.type === "todo_list") {
      const steps = (block.items || []).map((item) => ({
        id: item.id,
        title: item.text,
        status: item.status || "pending",
      }));
      if (steps.length) {
        state.latestTodoList = {
          steps,
          current_step_id: steps.find((step) => step.status !== "completed")?.id || null,
          currentStepId: steps.find((step) => step.status !== "completed")?.id || null,
        };
        if (state.currentConversation?.id === conversationId) {
          state.currentConversation.latestTodoList = state.latestTodoList;
        }
      }
    }
    upsertContentBlock(block, {
      updateKind: normalized.type === "block_update" ? "update" : "append",
    });
    return normalized;
  }
  if (normalized.type === "message_complete") {
    ensureCurrentConversationShape(conversationId);
    replaceMessageWithFinalBlocks(normalized.message_id, normalized.content || []);
    return normalized;
  }
  if (normalized.type === "result") {
    state.currentEvents = [...state.currentEvents, normalized];
    return normalized;
  }
  // 兼容旧协议：不再解析，记录用于观察
  return normalized;
}

export function abortCurrentRun() {
  activeRunController?.abort();
}

/**
 * 上报消息反馈；后端无接口时在本地记录状态。
 * @param {string} messageId
 * @param {"like"|"dislike"|null} type
 */
export async function submitFeedback(messageId, type) {
  if (!messageId) {
    return;
  }
  if (type === null) {
    delete state.messageFeedbacks[messageId];
    return;
  }
  try {
    await requestJson(`/api/agentloop/conversations/messages/${messageId}/feedback`, {
      method: "POST",
      body: JSON.stringify({ type }),
    });
  } catch {
    /* 接口未实现时仅本地保存 */
  }
  state.messageFeedbacks[messageId] = type;
}

const QUICK_ENTRY_ORDER = ["search", "writing", "review", "duplicate", "format"];

const QUICK_ENTRY_FALLBACK = {
  search: {
    key: "search",
    title: "资料检索",
    summary: "检索素材库与资料结果，并生成摘要列表。",
    examples: ["搜索一下关于具身智能的政策文章，并给我提炼 3 个要点。"],
  },
  writing: {
    key: "writing",
    title: "公文写作",
    summary: "生成公文正文、大纲或仿写结果，并同步文档产物。",
    examples: ["帮我写一篇关于优化营商环境的通知，语气正式，结构完整。"],
  },
  review: {
    key: "review",
    title: "公文审核",
    summary: "识别规范性问题并输出联动编辑器的审核意见。",
    examples: ["审核这篇文章，重点看标题格式、主送单位、时间表达和错别字。"],
  },
  duplicate: {
    key: "duplicate",
    title: "公文查重",
    summary: "分析重复风险、相似片段与查重报告。",
    examples: ["查重这篇文章，输出重复率、对应句子和来源链接。"],
  },
  format: {
    key: "format",
    title: "公文排版",
    summary: "推荐模板并输出排版结果或操作建议。",
    examples: ["排版这篇文章，优先推荐党政机关标准模板。"],
  },
};

/** 兼容旧逻辑：任意阶段加载中（首屏或发送中） */
export const loading = computed(() => state.bootstrapLoading || state.runLoading);

export const homeQuickSkills = computed(() => {
  const remoteSkills = new Map((state.skills || []).map((item) => [item.key, item]));
  return QUICK_ENTRY_ORDER.map((key) => {
    const fallback = QUICK_ENTRY_FALLBACK[key];
    const remote = remoteSkills.get(key) || {};
    return {
      key,
      title: remote.title || fallback.title,
      summary: remote.summary || fallback.summary,
      examples: Array.isArray(remote.examples) && remote.examples.length ? remote.examples : fallback.examples,
    };
  });
});

export const recommendationPrompts = computed(() => {
  if (!state.user) {
    return [];
  }
  if (state.user.is_first_login_to_agentloop ?? state.user.is_first_login_to_new_app) {
    return ["如何使用该产品？", "该产品能帮助我什么？"];
  }
  return [
    "我现在有哪些skills？",
    state.settingsProfile?.recommendationSummary || "帮我根据最近习惯推荐一个高频任务。",
  ];
});

export async function bootstrapApp() {
  state.bootstrapLoading = true;
  try {
    const [me, skills, conversations] = await Promise.all([
      requestJson("/api/agentloop/me"),
      requestJson("/api/agentloop/skills"),
      requestJson("/api/agentloop/conversations"),
    ]);
    state.user = me.data;
    let modelList = me.data?.auth_models || [];
    try {
      const models = await requestJson("/api/agentloop/models");
      if (Array.isArray(models.data) && models.data.length) {
        modelList = models.data;
      }
    } catch {
      /* 模型列表接口异常时不阻塞登录与首屏 */
    }
    state.modelOptions = modelList;
    state.skills = skills.data || [];
    state.conversations = conversations.data || [];
    if (state.conversations.length && !state.currentConversationId) {
      await selectConversation(state.conversations[0].id);
    }
  } catch (error) {
    state.errorMessage = String(error.message || error);
  } finally {
    state.bootstrapLoading = false;
  }
}

export async function refreshConversations() {
  const response = await requestJson("/api/agentloop/conversations");
  state.conversations = response.data || [];
}

export async function createConversation(title = "新对话") {
  const response = await requestJson("/api/agentloop/conversations", {
    method: "POST",
    body: JSON.stringify({ title }),
  });
  await refreshConversations();
  state.currentConversationId = response.data.id;
  await selectConversation(response.data.id);
  return response.data.id;
}

export async function selectConversation(conversationId) {
  state.currentConversationId = conversationId;
  const response = await requestJson(`/api/agentloop/conversations/${conversationId}`);
  state.currentConversation = response.data;
  state.latestTodoList = response.data?.latestTodoList || null;
  state.contextUsage =
    response.data?.runningContext?.contextUsage ||
    response.data?.runningContext?.context_usage ||
    null;
  state.pendingPromptMenu = response.data?.pendingPromptMenu || null;
  const summary = state.conversations.find((item) => item.id === conversationId);
  if (summary?.lastRunId) {
    try {
      const replay = await readEventStream(
        `/api/agentloop/conversations/${conversationId}/events?run_id=${summary.lastRunId}`,
        { timeoutMs: EVENT_STREAM_TIMEOUT_MS }
      );
      state.currentEvents = [];
      state.streamingPlannerReasoning = "";
      for (const item of replay) {
        applyProtocolItem(item, conversationId);
      }
    } catch (error) {
      state.currentEvents = [];
    }
  } else {
    state.currentEvents = [];
  }
  return response.data;
}

export async function renameConversation(conversationId, payload) {
  const response = await requestJson(`/api/agentloop/conversations/${conversationId}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
  await refreshConversations();
  if (state.currentConversationId === conversationId && state.currentConversation && payload?.title != null) {
    state.currentConversation.title = response.data?.title || payload.title;
  }
}

export async function compactConversation(conversationId) {
  if (!conversationId) {
    return null;
  }
  const response = await requestJson(`/api/agentloop/conversations/${conversationId}/compact`, {
    method: "POST",
  });
  await refreshConversations();
  if (state.currentConversationId === conversationId && state.currentConversation) {
    state.currentConversation.runningContext = response.data?.runningContext || null;
  }
  state.contextUsage =
    response.data?.runningContext?.contextUsage ||
    response.data?.runningContext?.context_usage ||
    state.contextUsage;
  return response.data;
}

export async function deleteConversation(conversationId) {
  await requestJson(`/api/agentloop/conversations/${conversationId}`, { method: "DELETE" });
  await refreshConversations();
  if (state.currentConversationId === conversationId) {
    state.currentConversationId = null;
    state.currentConversation = null;
    state.latestTodoList = null;
    state.contextUsage = null;
    state.compactionHistory = [];
  }
}

async function replayEvents(conversationId, runId) {
  const events = await readEventStream(`/api/agentloop/conversations/${conversationId}/events?run_id=${runId}`, {
    timeoutMs: LONG_REQUEST_TIMEOUT_MS,
  });
  state.currentEvents = [];
  for (const event of events) {
    applyProtocolItem(event, conversationId);
    await new Promise((resolve) => window.setTimeout(resolve, 120));
  }
}

export function ensureCurrentConversationShape(conversationId) {
  if (!state.currentConversation || state.currentConversation.id !== conversationId) {
    state.currentConversation = {
      id: conversationId,
      title: "",
      messages: [],
      artifacts: [],
      runningContext: null,
      pendingPromptMenu: null,
      latestTodoList: null,
    };
  }
  if (!Array.isArray(state.currentConversation.messages)) {
    state.currentConversation.messages = [];
  }
  if (!Array.isArray(state.currentConversation.artifacts)) {
    state.currentConversation.artifacts = [];
  }
}

function appendOptimisticMessages({ content, model }) {
  ensureCurrentConversationShape(state.currentConversationId);
  const userId = `temp-user-${Date.now()}`;
  const assistantId = `temp-assistant-${Date.now()}`;
  state.currentConversation.messages = [
    ...state.currentConversation.messages,
    {
      id: userId,
      role: "user",
      content,
      contentHtml: `<p>${content}</p>`,
      model,
      meta: {},
    },
    {
      id: assistantId,
      role: "assistant",
      content: "执行中",
      contentHtml: "<p>正在处理你的请求，步骤卡片会实时更新。</p>",
      contentBlocks: [],
      model,
      meta: {},
    },
  ];
}

async function streamConversationEvents(conversationId, runId) {
  state.currentEvents = [];
  state.latestTodoList = state.currentConversation?.latestTodoList || state.latestTodoList || null;
  if (activeRunController) {
    activeRunController.abort();
  }
  activeRunController = new AbortController();
  try {
    await streamEventStream(`/api/agentloop/conversations/${conversationId}/events?run_id=${runId}`, {
      timeoutMs: LONG_REQUEST_TIMEOUT_MS,
      signal: activeRunController.signal,
      onEvent(event) {
        applyProtocolItem(event, conversationId);
      },
    });
  } catch (err) {
    const name = err?.name || "";
    const msg = String(err?.message || err || "");
    if (name !== "AbortError" && !/aborted|AbortError/i.test(msg)) {
      throw err;
    }
  } finally {
    activeRunController = null;
  }
}

export async function runConversation({
  content,
  model,
  skill,
  attachments = [],
  operationContext = null,
  resumeFromWaiting = false,
  selectedOption = null,
  promptMenuInput = null,
}) {
  let conversationId = state.currentConversationId;
  if (!conversationId) {
    conversationId = await createConversation();
  }
  state.runLoading = true;
  state.errorMessage = "";
  state.currentEvents = [];
  state.latestTodoList = state.currentConversation?.latestTodoList || null;
  state.contextUsage = state.currentConversation?.runningContext?.contextUsage || state.contextUsage;
  state.streamingPlannerReasoning = "";
  try {
    appendOptimisticMessages({ content, model: model || state.user?.default_model || "" });
    const response = await requestJson(`/api/agentloop/conversations/${conversationId}/run`, {
      method: "POST",
      body: JSON.stringify({
        content,
        model,
        skill,
        attachments,
        operation_context: operationContext,
        resume_from_waiting: resumeFromWaiting,
        selected_option: selectedOption,
        prompt_menu_input: promptMenuInput,
      }),
      timeoutMs: LONG_REQUEST_TIMEOUT_MS,
    });
    state.currentRunId = response.data.runId;
    await refreshConversations();
    state.pendingPromptMenu = response.data.pendingPromptMenu || null;
    await streamConversationEvents(conversationId, response.data.runId);
    await Promise.all([refreshConversations(), selectConversation(conversationId)]);
    state.pendingPromptMenu = state.currentConversation?.pendingPromptMenu || state.pendingPromptMenu || null;
    return response.data;
  } catch (error) {
    const name = error?.name || "";
    const msg = String(error?.message || error || "");
    if (name === "AbortError" || /aborted|AbortError/i.test(msg)) {
      state.errorMessage = "";
    } else {
      state.errorMessage = String(error.message || error);
      throw error;
    }
  } finally {
    state.runLoading = false;
    state.streamingPlannerReasoning = "";
  }
}

export async function loadWorkspace(view = state.workspaceView) {
  state.workspaceView = view;
  const [items, tree] = await Promise.all([
    requestJson(`/api/agentloop/workspace?view=${view}`),
    requestJson("/api/agentloop/workspace/tree"),
  ]);
  state.workspaceItems = items.data || [];
  state.workspaceTree = tree.data || [];
}

export async function createFolder(name, parentId = null) {
  await requestJson("/api/agentloop/workspace/folders", {
    method: "POST",
    body: JSON.stringify({ name, parent_id: parentId }),
  });
  await loadWorkspace(state.workspaceView);
}

export async function createDocument(name, source = "manual") {
  const response = await requestJson("/api/agentloop/workspace/documents", {
    method: "POST",
    body: JSON.stringify({ name, source, content_html: "<p></p>", content_text: "" }),
  });
  await loadWorkspace(state.workspaceView);
  return response.data.id;
}

export async function uploadDocument(file) {
  const response = await uploadFile("/api/agentloop/workspace/uploads", file);
  await loadWorkspace(state.workspaceView);
  return response.data;
}

export async function fetchDocument(nodeId) {
  const response = await requestJson(`/api/agentloop/workspace/documents/${nodeId}`);
  state.currentDocument = response.data;
  return response.data;
}

export async function saveDocument(nodeId, payload) {
  const response = await requestJson(`/api/agentloop/workspace/documents/${nodeId}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
  await fetchDocument(nodeId);
  await loadWorkspace(state.workspaceView);
  return response.data;
}

export async function renameNode(nodeId, name) {
  await requestJson(`/api/agentloop/workspace/nodes/${nodeId}`, {
    method: "PUT",
    body: JSON.stringify({ name }),
  });
  await loadWorkspace(state.workspaceView);
}

export async function moveNode(nodeId, parentId = null) {
  await requestJson(`/api/agentloop/workspace/nodes/${nodeId}/move`, {
    method: "PUT",
    body: JSON.stringify({ parent_id: parentId }),
  });
  await loadWorkspace(state.workspaceView);
}

export async function deleteNode(nodeId) {
  await requestJson(`/api/agentloop/workspace/nodes/${nodeId}`, { method: "DELETE" });
  await loadWorkspace(state.workspaceView);
}

export async function sendNodeToConversation(nodeId) {
  const response = await requestJson(`/api/agentloop/workspace/nodes/${nodeId}/send-to-conversation`, {
    method: "POST",
  });
  await refreshConversations();
  return response.data;
}

export function downloadNode(nodeId) {
  window.open(`${import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000"}/api/agentloop/workspace/download/${nodeId}`, "_blank");
}

export async function loadSettings() {
  const [profile, memory, dictionaries, templates] = await Promise.all([
    requestJson("/api/agentloop/settings/profile"),
    requestJson("/api/agentloop/settings/memory"),
    requestJson("/api/agentloop/settings/dictionaries"),
    requestJson("/api/agentloop/settings/templates"),
  ]);
  state.settingsProfile = profile.data;
  if (state.user && profile.data?.defaultModel) {
    state.user.default_model = profile.data.defaultModel;
  }
  if (Array.isArray(profile.data?.authModels) && profile.data.authModels.length) {
    state.modelOptions = profile.data.authModels;
  }
  state.settingsMemory = memory.data;
  state.dictionaries = dictionaries.data;
  state.templates = templates.data || [];
}

export async function addDictionaryEntry(dictType, word, notes = "") {
  await requestJson("/api/agentloop/settings/dictionaries", {
    method: "PUT",
    body: JSON.stringify({
      dict_type: dictType,
      word,
      notes,
    }),
  });
  await loadSettings();
}

export async function deleteDictionaryEntry(entryId) {
  await requestJson(`/api/agentloop/settings/dictionaries/${entryId}`, { method: "DELETE" });
  await loadSettings();
}

export async function uploadTemplate({ title, documentType, file }) {
  const formData = new FormData();
  formData.append("title", title);
  if (documentType) {
    formData.append("document_type", documentType);
  }
  formData.append("file", file);
  await postForm("/api/agentloop/settings/templates", formData);
  await loadSettings();
}

export async function deleteTemplate(templateId) {
  await requestJson(`/api/agentloop/settings/templates/${templateId}`, { method: "DELETE" });
  await loadSettings();
}

export async function saveProfile(payload) {
  await requestJson("/api/agentloop/settings/profile", {
    method: "PUT",
    body: JSON.stringify(payload),
  });
  await loadSettings();
}

export async function saveMemory(payload) {
  await requestJson("/api/agentloop/settings/memory", {
    method: "PUT",
    body: JSON.stringify(payload),
  });
  await loadSettings();
}

export async function clearMemory() {
  await requestJson("/api/agentloop/settings/memory", { method: "DELETE" });
  await loadSettings();
}
