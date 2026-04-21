<template>
  <div class="agent-step" :class="{ open: isOpen }">
    <div class="step-header" :class="{ clickable: step.content }" @click="toggleStep">
      <div class="step-icon tool">
        <span>⚙</span>
      </div>
      <span class="step-label" v-html="step.label"></span>
      <el-icon v-if="step.content" class="step-chevron"><ArrowDown /></el-icon>
    </div>
    <div v-if="step.content && isOpen" class="step-content" :class="`step-content-${step.contentType || 'text'}`">
      <!-- 文本形式 -->
      <pre v-if="step.contentType === 'pre'" class="step-content-pre">{{ displayContent }}</pre>
      <!-- 搜索结果形式 -->
      <div v-else-if="step.contentType === 'search'" class="step-content-search">
        <div class="agent-search-summary">
          共找到
          <strong>{{ (step.content as any).total || 0 }}</strong>
          条相关资料，已引用
          <strong>{{ (step.content as any).used || 0 }}</strong>
          条
        </div>
        <div class="agent-search-cards">
          <div v-for="(result, index) in (step.content as any).results || []" :key="index" class="agent-search-card">
            <div class="agent-search-card-num">{{ (index as number) + 1 }}</div>
            <div class="agent-search-card-body">
              <strong>{{ result.title }}</strong>
              <p>{{ result.description }}</p>
              <div v-if="result.tag" class="agent-search-card-tag">{{ result.tag }}</div>
            </div>
          </div>
          <!-- 当没有搜索结果时显示提示 -->
          <div v-if="!((step.content as any).results && (step.content as any).results.length > 0)" class="agent-search-empty">未找到相关资料</div>
        </div>
      </div>
      <!-- 普通文本形式，支持流式输出 -->
      <div v-else class="step-content-text">
        <div class="streaming-text" v-html="displayContent"></div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ArrowDown } from '@element-plus/icons-vue';
import { onBeforeUnmount, ref, watch } from 'vue';

const props = withDefaults(
  defineProps<{
    step: Step;
    /** false：历史回显时一次性展示全文，不做逐字流式 */
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
  { immediate: true },
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
  transition:
    opacity 0.35s ease,
    transform 0.35s ease;

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

  &.tool {
    background: rgba(251, 188, 4, 0.18);
    color: #b06000;
  }
}

.step-label {
  flex: 1;
  font-size: 14px;
  color: #64748b;
  line-height: 1.6;

  .tool-call-prefix {
    color: #64748b;
    font-weight: 400;
  }

  strong {
    color: #1e293b;
    font-weight: 600;
  }
}

.step-chevron {
  font-family: 'Material Symbols Rounded';
  font-size: 18px;
  color: var(--on-surface-variant);
  transition: transform 0.2s ease;
  font-variation-settings:
    'FILL' 0,
    'wght' 300,
    'GRAD' 0,
    'opsz' 24;
  flex-shrink: 0;
}

.agent-step.open .step-chevron {
  transform: rotate(180deg);
}

.step-content {
  display: none;
  border-top: 1px solid rgba(227, 227, 227, 0.84);
  padding: 14px 16px 16px;
  background: rgba(255, 255, 255, 0.82);
  font-size: 12px;
  line-height: 1.75;
  color: var(--grey-600);
  font-family: 'Noto Sans SC', 'Source Han Sans SC', 'PingFang SC', sans-serif;

  &.step-content-pre pre {
    font-family: 'SFMono-Regular', Consolas, monospace;
    font-size: 12px;
    background: rgba(240, 244, 249, 0.84);
    border-radius: 16px;
    margin: 0;
    padding: 14px 16px 16px;
    white-space: pre-wrap;
    border: 1px solid rgba(227, 227, 227, 0.84);
    color: var(--grey-800);
  }

  &.step-content-search {
    padding: 14px 16px 16px;

    .agent-search-summary {
      font-size: 12px;
      color: var(--grey-600);
      margin-bottom: 10px;

      strong {
        color: var(--grey-900);
      }
    }

    .agent-search-cards {
      display: flex;
      flex-direction: column;
      gap: 6px;
    }

    .agent-search-card {
      display: flex;
      gap: 10px;
      align-items: flex-start;
      padding: 10px 12px;
      border-radius: 12px;
      background: #f8fafc;
      border: 1px solid #e2e8f0;
    }

    .agent-search-card-num {
      width: 20px;
      height: 20px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      border-radius: 50%;
      background: #dce7f8;
      color: #0842a0;
      font-size: 11px;
      font-weight: 600;
      flex-shrink: 0;
    }

    .agent-search-card-body {
      flex: 1;
      min-width: 0;
    }

    .agent-search-card-body strong {
      display: block;
      font-size: 12px;
      line-height: 1.5;
      color: var(--grey-900);
      margin-bottom: 4px;
    }

    .agent-search-card-body p {
      font-size: 12px;
      line-height: 1.5;
      color: var(--grey-600);
      margin: 0 0 6px 0;
    }

    .agent-search-card-tag {
      display: inline-block;
      padding: 3px 8px;
      border-radius: 10px;
      background: #e2e8f0;
      color: var(--grey-600);
      font-size: 10px;
      font-weight: 500;
    }

    .agent-search-empty {
      padding: 16px;
      text-align: center;
      color: var(--grey-600);
      font-size: 12px;
      background: #f8fafc;
      border: 1px solid #e2e8f0;
      border-radius: 12px;
    }
  }

  &.step-content-text {
    color: var(--grey-800);
    line-height: 1.6;
    background: #f8fafc;
    border-radius: 12px;
    padding: 10px 12px;
    border: 1px solid #e2e8f0;
  }
}

.agent-step.open .step-content {
  display: block;
}
</style>
