<template>
  <div class="agent-steps">
    <div
      v-for="item in renderedSteps"
      :key="item._renderKey"
      class="step-row"
      :class="{ 'step-animate': animated !== false }"
    >
      <component
        :is="stepComponents[item.step.type]"
        :step="item.step"
        :animated="animated !== false"
        @streaming-complete="onStreamingComplete(item._renderKey)"
      />
    </div>
    <div v-if="showOrganizingHint" class="organizing-hint">
      正在整理结果
      <span class="dots" aria-hidden="true"><i></i><i></i><i></i></span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue';
import { stepComponents } from './steps/index';

const props = defineProps<{
  steps: Step[];
  animated?: boolean;
}>();

const emit = defineEmits<{
  'step-rendered': [];
  'steps-complete': [];
}>();

const renderedCount = ref(0);
const renderKeys = ref<string[]>([]);
const completedKeys = ref<Set<string>>(new Set());
const hasEmittedComplete = ref(false);
const waitingNext = ref(false);
let lastStepsLength = 0;
let revealNextTimer: number | null = null;

const clearRevealTimer = () => {
  if (revealNextTimer !== null) {
    clearTimeout(revealNextTimer);
    revealNextTimer = null;
  }
  waitingNext.value = false;
};

/** 当前步骤 streaming-complete 后，间隔 600ms 再展示下一步 */
const scheduleRevealNext = () => {
  clearRevealTimer();
  if (renderedCount.value >= props.steps.length) return;
  waitingNext.value = true;
  revealNextTimer = window.setTimeout(() => {
    revealNextTimer = null;
    waitingNext.value = false;
    if (renderedCount.value < props.steps.length) {
      renderedCount.value++;
      emit('step-rendered');
    }
  }, 600);
};

const ensureKeys = (len: number) => {
  while (renderKeys.value.length < len) {
    const i = renderKeys.value.length;
    renderKeys.value.push(`step-${Date.now()}-${i}`);
  }
};

watch(
  () => props.steps.length,
  (len) => {
    if (len !== lastStepsLength) {
      hasEmittedComplete.value = false;
    }
    if (len > lastStepsLength) {
      ensureKeys(len);
      if (props.animated === false) {
        renderedCount.value = len;
        emit('step-rendered');
        hasEmittedComplete.value = true;
        emit('steps-complete');
      } else if (len > 0 && renderedCount.value === 0) {
        renderedCount.value = 1;
        emit('step-rendered');
      }
    }
    lastStepsLength = len;
  },
  { immediate: true }
);

const renderedSteps = computed(() => {
  const n = renderedCount.value;
  return props.steps.slice(0, n).map((step, i) => ({
    step,
    _renderKey: renderKeys.value[i] ?? `step-${i}`,
  }));
});

const showOrganizingHint = computed(
  () =>
    props.animated !== false &&
    waitingNext.value &&
    renderedCount.value > 0 &&
    renderedCount.value < props.steps.length
);

const onStreamingComplete = (key: string) => {
  if (completedKeys.value.has(key)) return;
  completedKeys.value.add(key);

  const currentIndex = renderedCount.value - 1;
  const currentKey = currentIndex >= 0 ? renderKeys.value[currentIndex] : '';
  // 仅当“当前最后一个已展示步骤”完成时，才允许推进到下一步
  if (key !== currentKey) return;

  if (props.animated === false) return;
  if (renderedCount.value >= props.steps.length && !hasEmittedComplete.value) {
    waitingNext.value = false;
    hasEmittedComplete.value = true;
    emit('steps-complete');
    return;
  }
  scheduleRevealNext();
};

onBeforeUnmount(() => {
  clearRevealTimer();
  completedKeys.value.clear();
});
</script>

<style scoped lang="scss">
.agent-steps {
  display: flex;
  flex-direction: column;
  gap: 10px;
  width: 100%;
}

.step-row {
  width: 100%;
}

.step-animate {
  animation: stepSlideIn 0.4s cubic-bezier(0.4, 0, 0.2, 1);
}

.organizing-hint {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  margin-left: 4px;
  margin-top: 2px;
  color: #6b7280;
  font-size: 14px;
  line-height: 1.5;

  .dots {
    display: inline-flex;
    align-items: center;
    gap: 4px;

    i {
      width: 6px;
      height: 6px;
      border-radius: 50%;
      background: #3b82f6;
      opacity: 0.3;
      animation: dotPulse 1.1s infinite ease-in-out;
    }

    i:nth-child(2) {
      animation-delay: 0.16s;
    }

    i:nth-child(3) {
      animation-delay: 0.32s;
    }
  }
}

@keyframes stepSlideIn {
  from {
    opacity: 0;
    transform: translateY(-20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes dotPulse {
  0%,
  80%,
  100% {
    opacity: 0.25;
    transform: translateY(0);
  }
  40% {
    opacity: 1;
    transform: translateY(-1px);
  }
}
</style>
