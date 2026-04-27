<template>
  <div class="agent-step" :class="{ open: isOpen }">
    <div class="step-header" :class="{ clickable: step.content }" @click="toggleStep">
      <div class="step-icon sub-agent">
        <span class="thinking-icon">
          <svg viewBox="0 0 24 24">
            <path
              d="M6.5 3.5C5.67 3.5 5 4.17 5 5s.67 1.5 1.5 1.5S8 5.83 8 5 7.33 3.5 6.5 3.5zm4-1C9.67 2.5 9 3.17 9 4s.67 1.5 1.5 1.5S12 4.83 12 4s-.67-1.5-1.5-1.5zm4 1C13.67 3.5 13 4.17 13 5s.67 1.5 1.5 1.5S16 5.83 16 5s-.67-1.5-1.5-1.5zm3 2.5c-.83 0-1.5.67-1.5 1.5S16.67 9 17.5 9 19 8.33 19 7.5 18.33 6 17.5 6zM12 8c-3.31 0-6 2.69-6 6 0 2.28 1.27 4.26 3.14 5.3.37.21.53.64.38 1.03l-.68 1.8c-.17.44.15.87.62.87h5.08c.47 0 .79-.43.62-.87l-.68-1.8c-.15-.39.01-.82.38-1.03C16.73 18.26 18 16.28 18 14c0-3.31-2.69-6-6-6z"
            />
          </svg>
        </span>
      </div>
      <span class="step-label" v-html="step.label"></span>
      <el-icon v-if="step.content" class="step-chevron"><ArrowDown /></el-icon>
    </div>
    <div v-if="step.content && isOpen" class="step-content">
      <pre class="step-content-text">{{ displayContent }}</pre>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ArrowDown } from '@element-plus/icons-vue';
import { onBeforeUnmount, ref, watch } from 'vue';

const props = withDefaults(
  defineProps<{
    step: Step;
    animated?: boolean;
  }>(),
  { animated: true }
);

const emit = defineEmits<{
  'streaming-complete': [];
}>();

const isOpen = ref(true);
const displayContent = ref('');
let streamingTimer: number | null = null;

const toggleStep = () => {
  if (props.step.content) {
    isOpen.value = !isOpen.value;
  }
};

const startStreaming = () => {
  if (typeof props.step.content === 'string') {
    const fullContent = props.step.content;
    if (streamingTimer) {
      clearInterval(streamingTimer);
      streamingTimer = null;
    }
    if (!props.animated) {
      displayContent.value = fullContent;
      emit('streaming-complete');
      return;
    }

    displayContent.value = '';
    let index = 0;

    streamingTimer = window.setInterval(() => {
      if (index < fullContent.length) {
        displayContent.value += fullContent[index];
        index++;
      } else {
        if (streamingTimer) {
          clearInterval(streamingTimer);
          streamingTimer = null;
        }
        // 触发流式输出完成事件
        emit('streaming-complete');
      }
    }, 30); // 每30ms显示一个字符
  } else {
    displayContent.value = props.step.content;
    // 非字符串内容不需要流式输出，直接触发完成事件
    emit('streaming-complete');
  }
};

watch(
  () => [props.step.content, props.animated] as const,
  () => {
    startStreaming();
  },
  { immediate: true }
);

// 组件卸载时清理定时器
onBeforeUnmount(() => {
  if (streamingTimer) {
    clearInterval(streamingTimer);
  }
});
</script>

<style scoped lang="scss">
.agent-step {
  width: 100%;
  border-radius: 16px;
  border: 1px solid #e2e8f0;
  background: #ffffff;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
  opacity: 1;
  transform: translateY(0);
  transition: opacity 0.35s ease, transform 0.35s ease;

  &.open {
    background: #ffffff;
  }
}

.step-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  font-size: 14px;
  color: #64748b;
  line-height: 1.6;
  user-select: none;
  cursor: default;

  &.clickable {
    cursor: pointer;
    transition: background 0.18s ease;

    &:hover {
      background: rgba(240, 244, 249, 0.72);
    }
  }
}

.step-icon {
  width: 28px;
  height: 28px;
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 10px;

  &.sub-agent {
    background: rgba(219, 234, 254, 0.3);
    color: #2563eb;

    svg {
      width: 16px;
      height: 16px;
      fill: currentColor;
    }
  }
}

.step-label {
  flex: 1;
  font-size: 14px;
  color: #64748b;

  strong {
    color: #0f172a;
    font-weight: 600;
  }
}

.step-chevron {
  font-family: 'Material Symbols Rounded';
  font-size: 18px;
  color: var(--on-surface-variant);
  transition: transform 0.2s ease;
  font-variation-settings: 'FILL' 0, 'wght' 300, 'GRAD' 0, 'opsz' 24;
  flex-shrink: 0;
}

.agent-step.open .step-chevron {
  transform: rotate(180deg);
}

.step-content {
  display: none;
  border-top: 1px solid #e2e8f0;
  padding: 14px 16px 16px;
  font-size: 12px;
  line-height: 1.6;
  color: #64748b;
  font-family: 'Noto Sans SC', 'Source Han Sans SC', 'PingFang SC', sans-serif;

  pre {
    margin: 0;
  }

  .step-content-pre {
    font-family: 'SFMono-Regular', Consolas, monospace;
    font-size: 12px;
    background: #f8fafc;
    border-radius: 12px;
    white-space: pre-wrap;
    border: 1px solid #e2e8f0;
    color: var(--grey-800);
  }

  &.step-content-json {
    font-family: 'SFMono-Regular', Consolas, monospace;
    font-size: 12px;
    background: rgba(30, 30, 30, 0.95);
    border-radius: 12px;
    white-space: pre-wrap;
    color: #d4d4d4;
    overflow-x: auto;

    pre {
      margin: 0;
    }
  }

  &.step-content-text {
    color: var(--grey-800);
    line-height: 1.6;
    background: #f8fafc;
    border-radius: 12px;
    border: 1px solid #e2e8f0;
  }

  &.step-content-html {
    .search-result-summary {
      font-size: 12px;
      color: var(--grey-600);
      margin-bottom: 10px;

      strong {
        color: var(--grey-900);
      }
    }

    .search-cards {
      display: flex;
      flex-direction: column;
      gap: 6px;
    }

    .search-card {
      display: flex;
      gap: 10px;
      align-items: flex-start;
      padding: 10px 12px;
      background: #f8fafc;
      border: 1px solid #e2e8f0;
      border-radius: 12px;
      transition: background 0.12s;

      &:hover {
        background: #f1f5f9;
      }
    }

    .search-card-num {
      flex-shrink: 0;
      width: 20px;
      height: 20px;
      border-radius: 50%;
      background: #e2e8f0;
      color: #64748b;
      font-size: 11px;
      font-weight: 600;
      display: flex;
      align-items: center;
      justify-content: center;
      margin-top: 1px;
    }

    .search-card-body {
      flex: 1;
      min-width: 0;
    }

    .search-card-title {
      font-size: 13px;
      font-weight: 500;
      color: var(--grey-900);
      margin-bottom: 4px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    .search-card-desc {
      font-size: 12px;
      color: var(--grey-600);
      line-height: 1.5;
      display: -webkit-box;
      -webkit-line-clamp: 2;
      line-clamp: 2;
      -webkit-box-orient: vertical;
      overflow: hidden;
    }

    .search-card-tag {
      display: inline-block;
      margin-top: 6px;
      padding: 3px 8px;
      background: #e2e8f0;
      border-radius: 10px;
      font-size: 10px;
      color: var(--grey-600);
    }
  }

  &.step-content-skills {
    padding: 10px 12px;

    .skill-summary {
      font-size: 12px;
      color: var(--grey-600);
      margin-bottom: 8px;

      strong {
        color: var(--grey-900);
      }
    }

    .skill-chips {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
    }

    .skill-chip {
      display: flex;
      align-items: center;
      gap: 4px;
      padding: 4px 10px;
      background: #dcfce7;
      border: 1px solid #bbf7d0;
      border-radius: 16px;
      font-size: 12px;
      color: #16a34a;
      font-weight: 500;

      .skill-chip-icon {
        font-size: 10px;
      }
    }
  }

  &.step-content-template {
    background: #f8fafc;
    border-radius: 12px;
    padding: 10px 12px;
  }
}

.agent-step.open .step-content {
  display: block;
}

.thinking-icon {
  font-size: 14px;
}
</style>
