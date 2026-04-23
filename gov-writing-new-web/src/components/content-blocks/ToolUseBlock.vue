<script setup>
import { computed } from "vue";

const props = defineProps({
  block: { type: Object, required: true },
});

const name = computed(() => String(props.block?.name || "tool"));
const status = computed(() => String(props.block?.status || "running"));
const displayLabel = computed(() => {
  if (name.value === "dispatch_sub_agent") {
    const input = props.block?.input || {};
    return `派发子 Agent · ${input.agent_name || "未知"}`;
  }
  if (name.value === "workspace_cli") {
    const cmd = String(props.block?.input?.command || "").trim();
    return cmd ? `工作区命令 · ${cmd.slice(0, 40)}` : "执行工作区命令";
  }
  return `调用工具 · ${name.value}`;
});
const summary = computed(() => {
  const input = props.block?.input || {};
  if (name.value === "dispatch_sub_agent") {
    return String(input.task_prompt || "").slice(0, 160);
  }
  if (input && typeof input === "object") {
    return JSON.stringify(input).slice(0, 180);
  }
  return "";
});
</script>

<template>
  <div class="block-tool-use" :class="`status-${status}`">
    <div class="row">
      <span class="dot" />
      <span class="label">{{ displayLabel }}</span>
      <span class="status-tag">{{ status === "running" ? "执行中" : status === "error" ? "失败" : "已派发" }}</span>
    </div>
    <div v-if="summary" class="summary">{{ summary }}</div>
  </div>
</template>

<style scoped>
.block-tool-use {
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: 12px;
  padding: 10px 14px;
  margin: 6px 0;
  background: linear-gradient(135deg, #eff6ff, #f5f3ff);
  color: #1e293b;
}
.row {
  display: flex;
  align-items: center;
  gap: 10px;
}
.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #2563eb;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.15);
}
.status-running .dot {
  animation: pulse 1.2s ease-in-out infinite;
}
.status-error .dot {
  background: #dc2626;
  box-shadow: 0 0 0 3px rgba(220, 38, 38, 0.15);
}
.status-ok .dot {
  background: #16a34a;
  box-shadow: 0 0 0 3px rgba(22, 163, 74, 0.15);
}
.label {
  flex: 1;
  font-weight: 600;
  font-size: 13px;
}
.status-tag {
  font-size: 12px;
  color: #64748b;
}
.summary {
  margin-top: 6px;
  font-size: 12px;
  color: #475569;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
}
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}
</style>
