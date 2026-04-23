<script setup>
import { computed, ref } from "vue";
import { marked } from "marked";

const props = defineProps({
  block: { type: Object, required: true },
});

const expanded = ref(false);
const html = computed(() => marked.parse(String(props.block?.thinking || "")));
const preview = computed(() => String(props.block?.thinking || "").slice(0, 140));
</script>

<template>
  <details class="block-thinking" :open="expanded">
    <summary @click.prevent="expanded = !expanded">
      <span class="label">思考</span>
      <span v-if="!expanded" class="preview">{{ preview }}</span>
    </summary>
    <div class="body markdown-body" v-html="html" />
  </details>
</template>

<style scoped>
.block-thinking {
  margin: 6px 0 10px;
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: 12px;
  background: #f5f5f7;
  overflow: hidden;
}
summary {
  display: flex;
  gap: 12px;
  align-items: center;
  cursor: pointer;
  list-style: none;
  padding: 10px 14px;
  font-size: 13px;
  color: #475569;
}
summary::-webkit-details-marker {
  display: none;
}
.label {
  font-weight: 600;
}
.preview {
  color: #94a3b8;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 480px;
}
.body {
  padding: 0 14px 12px;
  font-size: 13px;
  color: #334155;
}
</style>
