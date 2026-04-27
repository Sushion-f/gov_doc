<template>
  <div class="app-shell">
    <Sidebar ref="sidebarRef" :current-session-id="currentSessionId" @new-chat="handleNewChat" @select-session="handleSelectSession" @session-deleted="handleSessionDeleted" @open-cloud-disk="handleOpenCloudDisk" />

    <div class="workspace" :class="{ 'editor-open': linkedEditorOpen && linkedEditorStep }">
      <CloudDisk v-if="cloudDiskVisible" @file-open="handleCloudFileOpen" />

      <main v-else class="main-content">
        <div ref="scrollContainerRef" class="main-inner" @scroll="handleScroll" @wheel.passive="handleWheel">
          <ConversationView v-if="conversationVisible" :messages="messages" :visible="conversationVisible" @copy="handleCopy" @thumb-up="handleThumbUp" @thumb-down="handleThumbDown" @refresh="handleRefresh" @step-rendered="handleStepRendered" @steps-complete="handleStepsComplete" />
          <WelcomeSection v-else @question-click="handleQuestionClick" />
        </div>

        <DecisionActionBar v-if="activeDecision" :prompt="activeDecision.prompt" :description="activeDecision.description" :options="activeDecision.options" @action="handleDecisionAction" @close="closeDecisionBar" />
        <ChatInput v-show="!activeDecision" ref="inputRef" @send="handleSend" @claw-select="handleClawSelect" />
      </main>

      <Transition name="linked-editor">
        <div v-if="linkedEditorOpen && linkedEditorStep" class="linked-editor-shell" :key="linkedPanelKey">
          <aside class="linked-editor-aside">
            <LinkedEditorPanel :step="linkedEditorStep" @close="closeLinkedEditor" />
          </aside>
        </div>
      </Transition>
    </div>
  </div>
</template>

<script setup lang="ts">
import { addMessage, createNewChat, getChatDetail, getConversationDetail, runConversation, runNewConversation } from '@/api';
import { createSSEConnection, type AgentLoopEvent } from '@/api/sse';
import { LINKED_EDITOR_KEY } from '@/views/chat/linkedEditor';
import { computed, nextTick, onUnmounted, provide, ref, watch } from 'vue';
import ChatInput from './components/ChatInput.vue';
import CloudDisk from './components/CloudDisk.vue';
import ConversationView from './components/ConversationView.vue';
import DecisionActionBar from './components/DecisionActionBar.vue';
import LinkedEditorPanel from './components/LinkedEditorPanel.vue';
import Sidebar from './components/Sidebar.vue';
import WelcomeSection from './components/WelcomeSection.vue';

interface SendData {
  text: string;
  model?: string;
  claw?: string | null;
  skill?: string | null;
}

interface AssistantMessageData {
  text?: string;
  textVisible?: boolean;
  steps?: { title: string; steps: Step[] };
  decisionPrompt?: ChatMessage['decisionPrompt'];
  streaming?: boolean;
}

type BackendMessage = {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content?: string;
  contentHtml?: string;
  skillName?: string;
  createdAt: string;
};

const mapBackendMessages = (list: BackendMessage[] | undefined): ChatMessage[] => {
  if (!Array.isArray(list)) return [];
  return list
    .filter((msg) => msg.role === 'user' || msg.role === 'assistant')
    .map((msg) => ({
      id: msg.id,
      role: msg.role as 'user' | 'assistant',
      content: msg.content || '',
      text: msg.role === 'assistant' ? msg.contentHtml || msg.content || '' : undefined,
      textVisible: msg.role === 'assistant' ? true : undefined,
      skill: msg.skillName || null,
      createdAt: msg.createdAt,
      streaming: false,
    }));
};

const sidebarRef = ref<InstanceType<typeof Sidebar> | null>(null);
const linkedEditorOpen = ref(false);
const linkedEditorStep = ref<Step | null>(null);
const linkedPanelKey = computed(() => {
  const s = linkedEditorStep.value;
  if (!s) return 'none';
  return (s as { clientStepId?: string }).clientStepId || s.label || 'doc';
});

const openLinkedEditor = (step: Step) => {
  linkedEditorStep.value = step;
  linkedEditorOpen.value = true;
};

const closeLinkedEditor = () => {
  linkedEditorOpen.value = false;
  linkedEditorStep.value = null;
};

provide(LINKED_EDITOR_KEY, {
  open: openLinkedEditor,
  close: closeLinkedEditor,
  activeStep: linkedEditorStep,
  isOpen: linkedEditorOpen,
});
const conversationVisible = ref(false);
const messages = ref<ChatMessage[]>([]);
const currentSessionId = ref<string>();
const activeDecision = ref<ChatMessage['decisionPrompt'] | null>(null);
const pendingDecision = ref<ChatMessage['decisionPrompt'] | null>(null);
const waitStepsCompleteForDecision = ref(false);
const scrollContainerRef = ref<HTMLElement | null>(null);
const autoScroll = ref(true);
/** 侧栏切换会话加载历史时，避免 watch 多次 smooth 滚底；由 handleSelectSession 内瞬时滚底 */
const isRestoringHistory = ref(false);
/** 会话切换阶段禁用一切自动滚底（包含步骤渲染事件） */
const isSwitchingSession = ref(false);
/** 程序化 smooth 滚动过程中会触发 scroll，短暂忽略以免误判为“用户离开底部” */
let scrollIgnoreUntil = 0;

const scrollToBottom = (behavior: ScrollBehavior = 'smooth') => {
  if (!autoScroll.value) return;
  scrollIgnoreUntil = Date.now() + (behavior === 'smooth' ? 800 : 80);
  nextTick(() => {
    requestAnimationFrame(() => {
      const container = scrollContainerRef.value;
      if (!container) return;
      container.scrollTo({
        top: container.scrollHeight,
        behavior,
      });
    });
  });
};

const handleScroll = () => {
  if (Date.now() < scrollIgnoreUntil) return;
  if (!scrollContainerRef.value) return;
  const { scrollTop, scrollHeight, clientHeight } = scrollContainerRef.value;
  const isAtBottom = scrollHeight - scrollTop - clientHeight < 50;
  autoScroll.value = isAtBottom;
};

const handleWheel = (e: WheelEvent) => {
  if (e.deltaY < 0) {
    autoScroll.value = false;
  }
};

watch(
  () => messages.value.length,
  (len) => {
    if (len === 0) {
      activeDecision.value = null;
      pendingDecision.value = null;
      waitStepsCompleteForDecision.value = false;
      return;
    }
    if (autoScroll.value && !isRestoringHistory.value && !isSwitchingSession.value) {
      scrollToBottom('smooth');
    }
  },
);

watch(
  () => {
    const steps = messages.value[messages.value.length - 1]?.steps;
    if (steps && Array.isArray(steps.steps)) return steps.steps.length;
    if (Array.isArray(steps)) return steps.length;
    return 0;
  },
  () => {
    if (autoScroll.value && !isRestoringHistory.value && !isSwitchingSession.value) {
      scrollToBottom('smooth');
    }
  },
);

watch(
  () => conversationVisible.value,
  (newVal) => {
    if (newVal) {
      autoScroll.value = true;
      if (!isRestoringHistory.value && !isSwitchingSession.value) scrollToBottom('smooth');
    }
  },
);

const cloudDiskVisible = ref(false);

const handleOpenCloudDisk = () => {
  cloudDiskVisible.value = true;
};

const handleCloudFileOpen = (file: { id: string; name: string; type: string }) => {
  console.log('打开云盘文件:', file);
};

const handleNewChat = (session: ChatSession) => {
  activeStream.value?.close();
  activeStream.value = null;
  cloudDiskVisible.value = false;
  currentSessionId.value = session.id;
  messages.value = [];
  conversationVisible.value = false;
  activeDecision.value = null;
  pendingDecision.value = null;
  waitStepsCompleteForDecision.value = false;
  autoScroll.value = true;
};

const handleSelectSession = async (sessionId: string) => {
  activeStream.value?.close();
  activeStream.value = null;
  cloudDiskVisible.value = false;
  currentSessionId.value = sessionId;
  activeDecision.value = null;
  pendingDecision.value = null;
  waitStepsCompleteForDecision.value = false;
  autoScroll.value = true;
  isRestoringHistory.value = true;
  isSwitchingSession.value = true;
  try {
    if (sessionId.startsWith('local-')) {
      const res = await getChatDetail(sessionId);
      messages.value = res.data.messages || [];
    } else {
      const detail = await getConversationDetail(sessionId);
      messages.value = mapBackendMessages(detail.messages);
    }
    conversationVisible.value = messages.value.length > 0;
  } catch (error) {
    console.error('加载会话详情失败:', error);
    messages.value = [];
    conversationVisible.value = false;
  } finally {
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        isRestoringHistory.value = false;
        isSwitchingSession.value = false;
      });
    });
  }
};

const handleSessionDeleted = (sessionId: string) => {
  if (currentSessionId.value === sessionId) {
    activeStream.value?.close();
    activeStream.value = null;
    currentSessionId.value = void 0;
    messages.value = [];
    conversationVisible.value = false;
    activeDecision.value = null;
    pendingDecision.value = null;
    waitStepsCompleteForDecision.value = false;
    autoScroll.value = true;
  }
};

const inputRef = ref<InstanceType<typeof ChatInput> | null>(null);
const activeStream = ref<{ close: () => void } | null>(null);

const handleQuestionClick = (question: string) => {
  // 填充到输入框
  if (inputRef.value) {
    inputRef.value.setInputText(question);
  }
};

const ensureActiveSession = async () => {
  if (currentSessionId.value) return currentSessionId.value;
  const res = await createNewChat();
  currentSessionId.value = res.data.id;
  if (sidebarRef.value) {
    sidebarRef.value.addSession(res.data);
  }
  return res.data.id;
};

const handleSend = async (data: SendData) => {
  if (data.text.trim()) {
    await ensureActiveSession();
    activeDecision.value = null;
    pendingDecision.value = null;
    waitStepsCompleteForDecision.value = false;
    autoScroll.value = true;
    conversationVisible.value = true;
    addUserMessage(data.text, null, data.skill || data.claw || null);
    processAssistantResponse(data);
  }
};

const handleDecisionAction = (option: { id: string; label: string; sendText?: string; text?: string }) => {
  activeDecision.value = null;
  pendingDecision.value = null;
  waitStepsCompleteForDecision.value = false;
  if (option.sendText) {
    handleSend({
      text: option.sendText,
      model: 'Qwen 3.5',
      claw: null,
    });
    return;
  }
  inputRef.value?.setInputText(option.text || '');
};

const closeDecisionBar = () => {
  activeDecision.value = null;
  pendingDecision.value = null;
  waitStepsCompleteForDecision.value = false;
};

const handleClawSelect = (claw: string | null) => {
  console.log('选择 Claw:', claw);
};

const handleCopy = (message: ChatMessage) => {
  console.log('复制消息:', message);
};

const handleThumbUp = (message: ChatMessage) => {
  console.log('点赞:', message);
};

const handleThumbDown = (message: ChatMessage) => {
  console.log('点踩:', message);
};

const handleRefresh = (message: ChatMessage) => {
  console.log('重新生成:', message);
};

const handleStepRendered = () => {
  if (autoScroll.value && !isSwitchingSession.value) scrollToBottom();
};

const handleStepsComplete = (message: ChatMessage) => {
  message.streaming = false;
  if (waitStepsCompleteForDecision.value && pendingDecision.value) {
    activeDecision.value = pendingDecision.value;
    pendingDecision.value = null;
    waitStepsCompleteForDecision.value = false;
  }
};

const addUserMessage = async (content: string, attachment: any = null, skill: string | null = null) => {
  const message: ChatMessage = {
    id: `user-${Date.now()}`,
    role: 'user',
    content,
    attachment,
    skill,
    createdAt: new Date().toISOString(),
  };
  messages.value.push(message);

  if (currentSessionId.value && currentSessionId.value.startsWith('local-')) {
    try {
      await addMessage(currentSessionId.value, message);
      if (sidebarRef.value) {
        sidebarRef.value.updateSessionTitle(currentSessionId.value, content.slice(0, 20) + (content.length > 20 ? '...' : ''));
      }
    } catch (error) {
      console.error('保存消息失败:', error);
    }
  }
};

const addAssistantMessage = (data: AssistantMessageData) => {
  const message: ChatMessage = {
    id: `assistant-${Date.now()}`,
    role: 'assistant',
    content: '',
    createdAt: new Date().toISOString(),
    ...data,
  };
  messages.value.push(message);
};

const processAssistantResponse = (data: SendData) => {
  // 创建一个新的助手消息用于流式更新
  const assistantMessageIndex = messages.value.length;
  addAssistantMessage({
    steps: {
      title: '',
      steps: [],
    },
    text: '',
    textVisible: false,
    streaming: true,
  });

  const currentId = currentSessionId.value || '';
  const isDraft = currentId.startsWith('local-');

  const payload = {
    content: data.text,
    model: data.model,
    skill: data.skill || data.claw || null,
  };

  const connect = async () => {
    try {
      const runRes = isDraft ? await runNewConversation(payload) : await runConversation(currentId, payload);

      if (isDraft && currentSessionId.value) {
        const oldId = currentSessionId.value;
        currentSessionId.value = runRes.conversationId;
        sidebarRef.value?.replaceSessionId(oldId, runRes.conversationId, runRes.conversationTitle);
      }

      activeStream.value?.close();
      activeStream.value = createSSEConnection(runRes.streamUrl, {
        onEvent: (event: AgentLoopEvent) => {
          const currentMsg = messages.value[assistantMessageIndex];
          if (!currentMsg) return;
          if (!currentMsg.steps || Array.isArray(currentMsg.steps)) {
            currentMsg.steps = { title: '', steps: [] };
          }
          const stepList = currentMsg.steps.steps;

          const display = event.display;
          if (event.eventType === 'waiting_user') {
            const promptMenu = (event.payload?.promptMenu || {}) as Record<string, any>;
            const decision = {
              prompt: (promptMenu.title as string) || event.title || '请继续选择',
              description: promptMenu.description as string | undefined,
              options: Array.isArray(promptMenu.options)
                ? promptMenu.options.map((opt: any) => ({
                    id: String(opt.key || ''),
                    label: String(opt.label || opt.key || '选项'),
                    variant: opt.recommended ? 'primary' : 'default',
                  }))
                : [],
            };
            currentMsg.decisionPrompt = decision;
            pendingDecision.value = decision;
            return;
          }

          if (display?.visible === false) return;
          console.log('event', event);
          stepList.push({
            type: event.eventType === 'tool_call' ? 'tool' : event.eventType === 'created' ? 'think' : 'plainText',
            label: display?.title || event.title || '执行步骤',
            contentType: 'html',
            content: event.detailHtml || event.detail || display?.subtitle || '',
            open: false,
            clientStepId: `sse-${event.seqNo ?? Date.now()}-${stepList.length}`,
          });
        },
        onDone: async () => {
          const currentMsg = messages.value[assistantMessageIndex];
          if (!currentMsg || !currentSessionId.value) return;
          try {
            const detail = await getConversationDetail(currentSessionId.value);
            const lastAssistant = [...detail.messages].reverse().find((m) => m.role === 'assistant');
            if (lastAssistant) {
              currentMsg.text = lastAssistant.contentHtml || lastAssistant.content || '';
              currentMsg.textVisible = true;
            }
          } catch (error) {
            console.error('拉取会话详情失败:', error);
          } finally {
            currentMsg.streaming = false;
          }
        },
        onError: (error: Error) => {
          console.error('Stream connection error:', error);
          const currentMsg = messages.value[assistantMessageIndex];
          if (currentMsg) {
            currentMsg.streaming = false;
            currentMsg.text = '抱歉，连接中断，请重试。';
            currentMsg.textVisible = true;
          }
        },
      });
    } catch (error) {
      const currentMsg = messages.value[assistantMessageIndex];
      if (currentMsg) {
        currentMsg.streaming = false;
        currentMsg.text = '抱歉，请求失败，请稍后重试。';
        currentMsg.textVisible = true;
      }
      console.error('运行会话失败:', error);
    }
  };

  void connect();
};

onUnmounted(() => {
  activeStream.value?.close();
  activeStream.value = null;
});
</script>

<style scoped lang="scss">
.app-shell {
  display: flex;
  height: 100vh;
  width: 100vw;
  overflow: hidden;
  min-width: 0;
  background: radial-gradient(ellipse 80% 50% at 20% -10%, rgba(0, 47, 134, 0.1) 0%, transparent 60%), radial-gradient(ellipse 60% 40% at 80% 110%, rgba(50, 114, 231, 0.08) 0%, transparent 55%), radial-gradient(ellipse 40% 30% at 60% 50%, rgba(0, 97, 255, 0.04) 0%, transparent 50%), linear-gradient(160deg, #f0f4ff 0%, #f8faff 40%, #eef2fb 100%);
  background-attachment: fixed;
}

.workspace {
  flex: 1;
  display: flex;
  flex-direction: row;
  justify-content: center;
  min-width: 0;
  min-height: 0;
  height: 100%;
  overflow: hidden;
  position: relative;

  // &::before {
  //   content: '';
  //   position: fixed;
  //   top: 0;
  //   left: 0;
  //   right: 0;
  //   bottom: 0;
  //   background: url(@/assets/images/background.png) right top / cover no-repeat;
  //   pointer-events: none;
  //   z-index: 0;
  // }

  &.editor-open {
    .main-content {
      width: 44.7%;
    }

    :deep(.bottom-area) .bottom-area-inner {
      padding: 20px 16px;
    }
  }
}

.main-content {
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  width: 100%;
  height: 100%;
  position: relative;
  background: transparent;
  overflow: hidden;
  min-width: 0;
}

.linked-editor-shell {
  flex: 1;
  min-height: 0;
  height: 100%;
  z-index: 10;
}

.linked-editor-aside {
  width: 100%;
  height: 100%;
  min-height: 0;
  background: #ffffff;
  border-radius: 24px;
  box-shadow: -10px 0 36px rgba(0, 0, 0, 0.08);
  overflow: hidden;
}

.linked-editor-enter-active,
.linked-editor-leave-active {
  transition:
    flex-basis 0.34s cubic-bezier(0.4, 0, 0.2, 1),
    max-width 0.34s cubic-bezier(0.4, 0, 0.2, 1),
    width 0.34s cubic-bezier(0.4, 0, 0.2, 1),
    opacity 0.28s ease;
}

.linked-editor-enter-active .linked-editor-aside,
.linked-editor-leave-active .linked-editor-aside {
  transition: transform 0.34s cubic-bezier(0.4, 0, 0.2, 1);
}

.linked-editor-enter-from,
.linked-editor-leave-to {
  flex-basis: 0 !important;
  width: 0 !important;
  max-width: 0 !important;
  border-left-width: 0;
  opacity: 0;
}

.linked-editor-enter-from .linked-editor-aside,
.linked-editor-leave-to .linked-editor-aside {
  transform: translateX(100%);
}

.linked-editor-enter-to .linked-editor-aside,
.linked-editor-leave-from .linked-editor-aside {
  transform: translateX(0);
}

.main-inner {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  overflow-y: auto;
  padding: 30px 0 40px;
  height: calc(100% - 172px);
  gap: 0;

  &::-webkit-scrollbar {
    width: 8px;
    height: 8px;
  }

  &::-webkit-scrollbar-thumb {
    background: rgba(94, 94, 94, 0.22);
    border-radius: 999px;
  }
}
</style>
