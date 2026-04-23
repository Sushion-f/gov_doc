<script setup>
import { computed } from "vue";

const props = defineProps({
  block: { type: Object, required: true },
});

const menu = computed(() => props.block?.prompt_menu || {});
const question = computed(
  () => menu.value.question || menu.value.description || menu.value.title || "请补充必要信息后继续。"
);
const options = computed(() => Array.isArray(menu.value.options) ? menu.value.options : []);
</script>

<template>
  <div class="block-waiting-user">
    <div class="title">
      <span class="material-symbols-rounded">pause_circle</span>
      等待你的补充
    </div>
    <p class="question">{{ question }}</p>
    <ul v-if="options.length" class="options">
      <li v-for="option in options" :key="option.id || option.label">{{ option.label || option }}</li>
    </ul>
  </div>
</template>

<style scoped>
.block-waiting-user {
  border: 1px solid rgba(234, 179, 8, 0.4);
  border-radius: 14px;
  padding: 12px 16px;
  margin: 6px 0;
  background: #fffbeb;
  color: #78350f;
}
.title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  font-size: 13px;
}
.question {
  margin: 8px 0 6px;
  font-size: 13px;
  line-height: 1.65;
}
.options {
  list-style: disc;
  padding-left: 20px;
  margin: 4px 0 0;
  font-size: 12px;
  color: #78350f;
}
</style>
