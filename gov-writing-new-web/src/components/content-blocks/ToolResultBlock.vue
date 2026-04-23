<script setup>
import { computed } from "vue";

const props = defineProps({
  block: { type: Object, required: true },
});

const isError = computed(() => Boolean(props.block?.is_error));
const innerBlocks = computed(() => Array.isArray(props.block?.content) ? props.block.content : []);
</script>

<template>
  <div class="block-tool-result" :class="{ 'is-error': isError }">
    <div class="row">
      <span class="badge">{{ isError ? "失败" : "结果" }}</span>
      <span class="name">{{ block.name || "tool_result" }}</span>
    </div>
    <div class="body">
      <template v-for="(inner, idx) in innerBlocks" :key="idx">
        <p v-if="inner?.type === 'text'">{{ inner.text }}</p>
        <div v-else-if="inner?.type === 'artifact_ref'" class="artifact-chip">
          <span class="material-symbols-rounded">description</span>
          <span class="artifact-title">{{ inner.title || inner.artifact_id }}</span>
        </div>
        <div v-else-if="inner?.type === 'error'" class="error-text">{{ inner.message }}</div>
      </template>
    </div>
  </div>
</template>

<style scoped>
.block-tool-result {
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-left: 3px solid #16a34a;
  border-radius: 10px;
  padding: 10px 14px;
  margin: 6px 0;
  background: #f8fafc;
}
.block-tool-result.is-error {
  border-left-color: #dc2626;
  background: #fef2f2;
}
.row {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 12px;
  color: #475569;
}
.badge {
  padding: 2px 8px;
  border-radius: 999px;
  background: rgba(22, 163, 74, 0.1);
  color: #15803d;
  font-weight: 600;
}
.is-error .badge {
  background: rgba(220, 38, 38, 0.1);
  color: #b91c1c;
}
.name {
  color: #64748b;
}
.body {
  margin-top: 6px;
  font-size: 13px;
  color: #1e293b;
  line-height: 1.65;
}
.body p {
  margin: 0 0 4px;
  white-space: pre-wrap;
}
.artifact-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-top: 4px;
  padding: 4px 10px;
  border-radius: 999px;
  background: rgba(37, 99, 235, 0.08);
  color: #1d4ed8;
  font-size: 12px;
}
.error-text {
  color: #b91c1c;
  font-weight: 500;
}
</style>
