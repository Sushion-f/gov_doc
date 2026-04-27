<template>
  <div class="plain-text-step">
    {{ text }}
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue';

const props = defineProps<{
  step: Step;
}>();

const emit = defineEmits<{
  'streaming-complete': [];
}>();

const text = computed(() => {
  const raw = props.step.content;
  return typeof raw === 'string' ? raw : props.step.label || '';
});

onMounted(() => {
  emit('streaming-complete');
});
</script>

<style scoped lang="scss">
.plain-text-step {
  width: fit-content;
  max-width: 100%;
  background: #fff;
  border: 1px solid #e6ebf2;
  border-radius: 20px;
  color: #374151;
  font-size: 12px;
  line-height: 1.55;
  padding: 16px 22px;
}
</style>
