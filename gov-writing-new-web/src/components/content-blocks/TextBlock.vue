<script setup>
import { computed } from "vue";
import { marked } from "marked";

const props = defineProps({
  block: { type: Object, required: true },
});

const html = computed(() => marked.parse(String(props.block?.text || "")));
</script>

<template>
  <div class="block-text markdown-body" v-html="html" />
</template>

<style scoped>
.block-text {
  font-size: 14px;
  color: #0f172a;
  line-height: 1.72;
  padding: 6px 0;
}
</style>
