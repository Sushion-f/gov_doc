<script setup>
import { computed } from "vue";

const props = defineProps({
  block: { type: Object, required: true },
});

const kind = computed(() => String(props.block?.kind || "usage"));
const summary = computed(() => props.block?.summary || "");
const before = computed(() => props.block?.before || null);
const after = computed(() => props.block?.after || null);

function formatUsage(obj) {
  if (!obj) return "";
  const used = obj.used ?? obj.usedTokens ?? 0;
  const window = obj.window ?? obj.windowTokens ?? 0;
  return `${used} / ${window}`;
}
</script>

<template>
  <div class="block-context-notice" :class="`kind-${kind}`">
    <span class="material-symbols-rounded">compress</span>
    <div class="body">
      <div class="title">
        {{ kind === "compact" ? "上下文已压缩" : "上下文统计" }}
      </div>
      <div v-if="before || after" class="numbers">
        <span v-if="before">压缩前 {{ formatUsage(before) }}</span>
        <span v-if="after">保留 {{ formatUsage(after) }}</span>
      </div>
      <div v-if="summary" class="summary">{{ summary }}</div>
    </div>
  </div>
</template>

<style scoped>
.block-context-notice {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 14px;
  border-radius: 12px;
  background: rgba(100, 116, 139, 0.08);
  color: #475569;
  margin: 6px 0;
}
.kind-compact {
  background: rgba(37, 99, 235, 0.08);
  color: #1d4ed8;
}
.title {
  font-size: 13px;
  font-weight: 600;
}
.numbers {
  display: flex;
  gap: 12px;
  margin-top: 4px;
  font-size: 12px;
}
.summary {
  margin-top: 4px;
  font-size: 12px;
  line-height: 1.6;
  white-space: pre-wrap;
}
</style>
