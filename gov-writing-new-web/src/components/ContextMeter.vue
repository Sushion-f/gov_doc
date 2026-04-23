<script setup>
import { computed, ref, onMounted, onBeforeUnmount } from "vue";

const props = defineProps({
  usage: {
    type: Object,
    default: null,
  },
  loading: {
    type: Boolean,
    default: false,
  },
  history: {
    type: Array,
    default: () => [],
  },
});

const emit = defineEmits(["compact"]);

const popoverOpen = ref(false);
const rootEl = ref(null);

function formatTokens(value) {
  const n = Number(value || 0);
  if (n >= 1000) {
    return `${(n / 1000).toFixed(n >= 100000 ? 0 : 1).replace(/\.0$/, "")}K`;
  }
  return `${n}`;
}

function formatTime(value) {
  if (!value) return "";
  try {
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return "";
    return d.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  } catch (_) {
    return "";
  }
}

const ratio = computed(() => Number(props.usage?.ratio || 0));
const triggerRatio = computed(() => {
  const explicit = Number(props.usage?.triggerRatio || 0);
  if (explicit > 0 && explicit <= 1) return explicit;
  const used = Number(props.usage?.willCompactAt || 0);
  const window = Number(props.usage?.window || 0);
  if (!used || !window) return 0.75;
  return used / window;
});
const percentage = computed(() => `${Math.min(ratio.value, 1) * 100}%`);
const percentLabel = computed(() => `${Math.round(ratio.value * 100)}%`);
const meterTone = computed(() => {
  if (ratio.value >= 0.9) return "danger";
  if (ratio.value >= triggerRatio.value) return "warning";
  return "normal";
});
const sourceLabel = computed(() => {
  const src = props.usage?.source;
  if (src === "api") return "API 真实用量";
  if (src === "estimate") return "本地估算 · tiktoken";
  return "待统计";
});
const hint = computed(() => {
  if (ratio.value >= 0.9) return "接近上限，建议立即压缩";
  if (ratio.value >= triggerRatio.value) return "即将自动压缩";
  return "上下文窗口正常";
});

function togglePopover() {
  popoverOpen.value = !popoverOpen.value;
}

function onDocClick(event) {
  if (!rootEl.value) return;
  if (!rootEl.value.contains(event.target)) {
    popoverOpen.value = false;
  }
}

onMounted(() => document.addEventListener("click", onDocClick));
onBeforeUnmount(() => document.removeEventListener("click", onDocClick));

function onCompact() {
  emit("compact");
  popoverOpen.value = false;
}
</script>

<template>
  <div v-if="usage" ref="rootEl" class="ctx-meter" :class="`tone-${meterTone}`">
    <button class="ctx-meter-inline" type="button" @click="togglePopover" :aria-expanded="popoverOpen">
      <span class="ctx-bar">
        <span class="ctx-fill" :style="{ width: percentage }" />
      </span>
      <span class="ctx-text">
        <strong>{{ formatTokens(usage.used) }}</strong>
        <span class="ctx-sep">/</span>
        <span>{{ formatTokens(usage.window) }}</span>
        <span class="ctx-pct">{{ percentLabel }}</span>
      </span>
      <span class="material-symbols-rounded ctx-caret">expand_more</span>
    </button>

    <button
      class="ctx-compact-btn"
      type="button"
      :disabled="loading"
      :title="hint"
      @click="onCompact"
    >
      <span class="material-symbols-rounded">compress</span>
      <span>压缩</span>
    </button>

    <div v-if="popoverOpen" class="ctx-popover" role="dialog">
      <header>
        <div>
          <div class="ctx-popover-title">上下文状态</div>
          <div class="ctx-popover-sub">{{ sourceLabel }} · {{ hint }}</div>
        </div>
        <span class="ctx-popover-pct" :class="`tone-${meterTone}`">{{ percentLabel }}</span>
      </header>

      <dl class="ctx-popover-grid">
        <div>
          <dt>已使用</dt>
          <dd>{{ formatTokens(usage.used) }}</dd>
        </div>
        <div>
          <dt>窗口上限</dt>
          <dd>{{ formatTokens(usage.window) }}</dd>
        </div>
        <div>
          <dt>压缩阈值</dt>
          <dd>{{ Math.round(triggerRatio * 100) }}%</dd>
        </div>
        <div v-if="usage.apiUsage">
          <dt>完成 tokens</dt>
          <dd>{{ formatTokens(usage.apiUsage.completion_tokens || 0) }}</dd>
        </div>
      </dl>

      <section class="ctx-history">
        <h4>压缩历史</h4>
        <p v-if="!history.length" class="ctx-history-empty">当前对话暂未触发压缩。</p>
        <ul v-else>
          <li v-for="item in history" :key="item.id">
            <div class="ctx-history-head">
              <span>{{ formatTime(item.timestamp) }}</span>
              <span v-if="item.before && item.after">
                {{ formatTokens(item.before.used) }} → {{ formatTokens(item.after.used) }} tokens
              </span>
            </div>
            <p v-if="item.summary">{{ item.summary.slice(0, 260) }}{{ item.summary.length > 260 ? "…" : "" }}</p>
          </li>
        </ul>
      </section>
    </div>
  </div>
</template>

<style scoped>
.ctx-meter {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  position: relative;
}

.ctx-meter-inline {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  border: 1px solid rgba(29, 53, 87, 0.12);
  background: rgba(255, 255, 255, 0.9);
  border-radius: 999px;
  cursor: pointer;
  color: #1f2a3d;
  font-size: 12px;
  line-height: 1;
  transition: background 0.15s ease, border-color 0.15s ease;
}

.ctx-meter-inline:hover {
  background: #f2f6fb;
  border-color: rgba(15, 108, 189, 0.35);
}

.ctx-bar {
  position: relative;
  width: 58px;
  height: 6px;
  border-radius: 999px;
  background: #e8eef5;
  overflow: hidden;
  flex-shrink: 0;
}

.ctx-fill {
  position: absolute;
  left: 0;
  top: 0;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #0f6cbd 0%, #49a2ff 100%);
  transition: width 0.2s ease, background 0.2s ease;
}

.ctx-text {
  display: inline-flex;
  align-items: baseline;
  gap: 4px;
  font-feature-settings: "tnum" 1;
}

.ctx-text strong {
  font-weight: 600;
}

.ctx-sep {
  color: #97a3b6;
}

.ctx-pct {
  color: #65758b;
  margin-left: 4px;
  font-size: 11px;
}

.ctx-caret {
  font-size: 16px;
  color: #97a3b6;
}

.ctx-compact-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  border: 1px solid rgba(29, 53, 87, 0.12);
  background: #ffffff;
  border-radius: 999px;
  padding: 6px 10px;
  font-size: 12px;
  color: #1f2a3d;
  cursor: pointer;
  line-height: 1;
  transition: background 0.15s ease, border-color 0.15s ease, color 0.15s ease;
}

.ctx-compact-btn .material-symbols-rounded {
  font-size: 16px;
}

.ctx-compact-btn:hover:not(:disabled) {
  background: #eaf4ff;
  color: #0f6cbd;
  border-color: rgba(15, 108, 189, 0.45);
}

.ctx-compact-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.tone-warning .ctx-fill {
  background: linear-gradient(90deg, #e8a126 0%, #ffc252 100%);
}

.tone-warning .ctx-compact-btn {
  color: #a86a00;
  border-color: rgba(168, 106, 0, 0.4);
  background: #fff7e6;
}

.tone-danger .ctx-fill {
  background: linear-gradient(90deg, #cf453c 0%, #ff7a6b 100%);
}

.tone-danger .ctx-compact-btn {
  color: #b42318;
  border-color: rgba(180, 35, 24, 0.4);
  background: #ffe7e4;
}

.ctx-popover {
  position: absolute;
  bottom: calc(100% + 10px);
  left: 0;
  width: min(420px, 80vw);
  max-height: 60vh;
  overflow: auto;
  background: #ffffff;
  border-radius: 14px;
  border: 1px solid rgba(29, 53, 87, 0.12);
  box-shadow: 0 20px 40px rgba(15, 23, 42, 0.14);
  padding: 16px;
  z-index: 60;
}

.ctx-popover header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.ctx-popover-title {
  font-size: 14px;
  font-weight: 600;
  color: #1f2a3d;
}

.ctx-popover-sub {
  font-size: 12px;
  color: #65758b;
  margin-top: 2px;
}

.ctx-popover-pct {
  font-size: 16px;
  font-weight: 600;
  color: #0f6cbd;
}

.ctx-popover-pct.tone-warning {
  color: #a86a00;
}

.ctx-popover-pct.tone-danger {
  color: #b42318;
}

.ctx-popover-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  margin: 0 0 14px;
  padding: 12px;
  background: #f5f8fc;
  border-radius: 10px;
}

.ctx-popover-grid dt {
  font-size: 11px;
  color: #65758b;
  margin-bottom: 2px;
}

.ctx-popover-grid dd {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: #1f2a3d;
  font-feature-settings: "tnum" 1;
}

.ctx-history h4 {
  margin: 0 0 8px;
  font-size: 12px;
  color: #65758b;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.ctx-history-empty {
  margin: 0;
  font-size: 12px;
  color: #97a3b6;
}

.ctx-history ul {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.ctx-history li {
  padding: 10px 12px;
  background: #ffffff;
  border: 1px solid rgba(29, 53, 87, 0.08);
  border-radius: 10px;
}

.ctx-history-head {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: #65758b;
  margin-bottom: 4px;
}

.ctx-history li p {
  margin: 0;
  font-size: 12px;
  color: #455061;
  line-height: 1.55;
  white-space: pre-wrap;
  word-break: break-word;
}
</style>
