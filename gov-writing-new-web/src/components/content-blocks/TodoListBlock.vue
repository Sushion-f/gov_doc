<script setup>
import { computed } from "vue";

const props = defineProps({
  block: { type: Object, required: true },
});

const items = computed(() => Array.isArray(props.block?.items) ? props.block.items : []);

function statusLabel(status) {
  if (status === "completed") return "已完成";
  if (status === "in_progress" || status === "running") return "执行中";
  if (status === "failed" || status === "error") return "失败";
  return "待执行";
}
</script>

<template>
  <div class="block-todo-list">
    <div class="title">
      <span class="material-symbols-rounded">checklist</span>
      任务规划
    </div>
    <ol>
      <li v-for="item in items" :key="item.id" :class="`status-${item.status || 'pending'}`">
        <span class="marker" />
        <span class="text">{{ item.text }}</span>
        <span class="status">{{ statusLabel(item.status) }}</span>
      </li>
    </ol>
  </div>
</template>

<style scoped>
.block-todo-list {
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: 14px;
  padding: 12px 16px;
  margin: 6px 0;
  background: #ffffff;
}
.title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 600;
  color: #0f172a;
  margin-bottom: 8px;
}
ol {
  list-style: none;
  padding: 0;
  margin: 0;
}
li {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 0;
  font-size: 13px;
  color: #334155;
}
.marker {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #cbd5e1;
}
.status-completed .marker {
  background: #16a34a;
}
.status-in_progress .marker,
.status-running .marker {
  background: #2563eb;
  animation: pulse 1.2s ease-in-out infinite;
}
.status-failed .marker,
.status-error .marker {
  background: #dc2626;
}
.text {
  flex: 1;
}
.status {
  font-size: 11px;
  color: #64748b;
}
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}
</style>
