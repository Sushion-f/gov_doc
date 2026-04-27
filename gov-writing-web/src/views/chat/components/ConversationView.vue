<template>
  <div class="conversation-view" :class="{ visible: visible }">
    <div
      v-for="(message, index) in localMessages"
      :key="message.id || `m-${index}`"
      class="message"
      :class="message.role === 'user' ? 'user-message' : 'assistant-message'"
    >
      <div v-if="message.role === 'user'" class="user-message-content">
        <div v-if="message.attachment" class="user-attachment">
          <el-icon><Upload /></el-icon>
          {{ message.attachment }}
        </div>
        <div class="user-bubble">
          <div v-if="message.skill" class="user-bubble-skill">
            <el-icon><Search /></el-icon>
            {{ message.skill }}
          </div>
          <div class="user-bubble-text">{{ message.content }}</div>
        </div>
      </div>

      <div v-else class="assistant-message-content">
        <div v-if="getStepTitle(message)" class="assistant-header">
          <div class="assistant-meta">
            <div class="assistant-caption">{{ getStepTitle(message) }}</div>
          </div>
          <div class="assistant-status" :class="{ streaming: isMessageStreaming(message) }">
            <template v-if="isMessageStreaming(message)">
              <span class="status-dot" aria-hidden="true"></span>
              流式执行中
            </template>
            <template v-else>
              <el-icon><CircleCheck /></el-icon>
              执行完成
            </template>
          </div>
        </div>
        <AgentSteps
          v-if="getStepList(message).length"
          :steps="getStepList(message)"
          :animated="isMessageStreaming(message)"
          @step-rendered="handleStepRendered"
          @steps-complete="handleStepsComplete(message)"
        />

        <div
          v-if="message.text"
          class="assistant-text-bubble"
          :class="{ 'stream-hidden': !message.textVisible, 'stream-visible': message.textVisible }"
        >
          <div v-html="message.text"></div>
        </div>

        <div class="msg-actions">
          <button class="msg-action-btn" title="复制" @click="handleCopy(message)">
            <el-icon><CopyDocument /></el-icon>
          </button>
          <button class="msg-action-btn" title="有帮助" @click="handleThumbUp(message)">
            <el-icon><Star /></el-icon>
          </button>
          <button class="msg-action-btn" title="重新生成" @click="handleRefresh(message)">
            <el-icon><Refresh /></el-icon>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { CircleCheck, CopyDocument, Refresh, Search, Star, Upload } from '@element-plus/icons-vue';
import { ref, watch } from 'vue';
import AgentSteps from './AgentSteps.vue';

const props = defineProps({
  messages: {
    type: Array as () => ChatMessage[],
    default: () => [],
  },
  visible: {
    type: Boolean,
    default: false,
  },
});

const emit = defineEmits<{
  copy: [message: ChatMessage];
  'thumb-up': [message: ChatMessage];
  'thumb-down': [message: ChatMessage];
  refresh: [message: ChatMessage];
  'step-rendered': [];
  'steps-complete': [message: ChatMessage];
}>();

const localMessages = ref<ChatMessage[]>([]);

watch(
  () => props.messages,
  (newMessages) => {
    localMessages.value = newMessages;
  },
  { immediate: true, deep: true },
);

const handleCopy = (message: ChatMessage) => {
  emit('copy', message);
};

const handleThumbUp = (message: ChatMessage) => {
  emit('thumb-up', message);
};

const handleThumbDown = (message: ChatMessage) => {
  emit('thumb-down', message);
};

const handleRefresh = (message: ChatMessage) => {
  emit('refresh', message);
};

const handleStepRendered = () => {
  emit('step-rendered');
};

const handleStepsComplete = (message: ChatMessage) => {
  emit('steps-complete', message);
};

const getStepTitle = (message: ChatMessage) => {
  const rawSteps = message.steps as { title?: string; steps?: Step[] } | undefined;
  if (!rawSteps) return '';
  if (Array.isArray(rawSteps)) return '';
  return rawSteps.title || '';
};

const getStepList = (message: ChatMessage): Step[] => {
  const rawSteps = message.steps as { steps?: Step[] } | Step[] | undefined;
  if (!rawSteps) return [];
  if (Array.isArray(rawSteps)) return rawSteps;
  if (Array.isArray(rawSteps.steps)) return rawSteps.steps;
  return [];
};

const isMessageStreaming = (message: ChatMessage) => message.streaming === true;
</script>

<style scoped lang="scss">
.conversation-view {
  display: none;
  flex-direction: column;
  gap: 20px;
  width: 100%;
  max-width: 760px;
  flex: 1;

  &.visible {
    display: flex;
  }
}

.message {
  display: flex;
  flex-direction: column;
  gap: 8px;

  &.user-message {
    align-items: flex-end;
  }

  &.assistant-message {
    align-items: flex-start;
    width: 100%;
    padding: 18px 20px;
    border-radius: 26px;
    background: rgba(255, 255, 255, 0.92);
    border: 1px solid rgba(242, 242, 242, 0.95);
    box-shadow: 0 12px 34px rgba(11, 87, 208, 0.08);
  }
}

.user-message-content {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 6px;
}

.user-attachment {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 10px;
  background: rgba(0, 47, 134, 0.08);
  border: 1px solid rgba(0, 47, 134, 0.15);
  border-radius: 8px;
  font-size: 12px;
  color: var(--primary);

  .el-icon {
    font-size: 15px;
  }
}

.user-bubble {
  background: var(--primary);
  color: #fff;
  padding: 12px 18px;
  border-radius: 20px 20px 4px 20px;
  font-size: 14px;
  line-height: 1.6;
  display: flex;
  flex-direction: column;
  gap: 8px;
  align-items: flex-start;
}

.user-bubble-skill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 2px 12px;
  background: rgba(255, 255, 255, 0.2);
  border-radius: 999px;
  font-size: 12px;
  font-weight: 500;
  color: #fff;

  .el-icon {
    font-size: 13px;
  }
}

.user-bubble-text {
  white-space: pre-wrap;
  word-break: break-word;
}

.assistant-message-content {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;

  .assistant-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 14px;
    margin-bottom: 14px;

    .assistant-meta {
      display: flex;
      align-items: center;
      gap: 12px;

      .assistant-caption {
        font-size: 18px;
        font-weight: 600;
        line-height: 1.3;
        color: #1f1f1f;
      }
    }

    .assistant-status {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      font-size: 13px;
      color: #64748b;

      &.streaming {
        color: var(--primary);
      }

      .status-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background: var(--primary);
        animation: pulse 1.2s ease-in-out infinite;
      }
    }
  }
}

@keyframes pulse {
  0%,
  100% {
    opacity: 1;
    transform: scale(1);
  }
  50% {
    opacity: 0.45;
    transform: scale(0.92);
  }
}

.assistant-text-bubble {
  margin-top: 8px;
  padding: 12px 14px;
  border-radius: 12px;
  background: rgba(248, 250, 252, 0.95);
  border: 1px solid rgba(226, 232, 240, 0.9);
  font-size: 14px;
  line-height: 1.65;
  color: #1f2937;

  &.stream-hidden {
    opacity: 0.35;
  }

  &.stream-visible {
    opacity: 1;
  }
}

.msg-actions {
  display: flex;
  gap: 8px;
  margin-top: 10px;
}

.msg-action-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border-radius: 10px;
  border: 1px solid rgba(226, 232, 240, 0.95);
  background: rgba(255, 255, 255, 0.92);
  color: #64748b;
  cursor: pointer;
  transition:
    background 0.15s ease,
    color 0.15s ease,
    border-color 0.15s ease;

  &:hover {
    border-color: rgba(0, 47, 134, 0.18);
    color: var(--primary);
    background: rgba(235, 243, 254, 0.85);
  }

  .el-icon {
    font-size: 16px;
  }
}
</style>
