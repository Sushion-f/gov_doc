<template>
  <div class="result-step">
    <div class="result-badge">{{ content.badge || '结果' }}</div>
    <h3 class="result-title">{{ content.title }}</h3>
    <p v-if="content.description" class="result-desc">{{ content.description }}</p>

    <div class="result-items">
      <div v-for="(item, idx) in content.items || []" :key="idx" class="result-item">
        <div class="item-title">{{ item.title }}</div>
        <div class="item-meta">{{ item.meta }}</div>
        <a
          class="item-link"
          v-if="item.url"
          :href="item.url || '#'"
          target="_blank"
          rel="noopener noreferrer"
          >打开原文<el-icon><TopRight /></el-icon
        ></a>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { TopRight } from '@element-plus/icons-vue';
import { computed, onMounted } from 'vue';

const props = defineProps<{
  step: Step;
}>();

const emit = defineEmits<{
  'streaming-complete': [];
}>();

const content = computed(() => (props.step.content || {}) as Record<string, any>);

onMounted(() => {
  emit('streaming-complete');
});
</script>

<style scoped lang="scss">
.result-step {
  width: 100%;
  border-radius: 18px;
  border: 1px solid #e5e7eb;
  background: #fff;
  padding: 14px 16px 16px;
}

.result-badge {
  display: inline-flex;
  align-items: center;
  height: 26px;
  padding: 0 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
  color: #0b57d0;
  background: #eef4ff;
  margin-bottom: 10px;
}

.result-title {
  margin: 0 0 8px;
  font-size: 16px;
  line-height: 1.35;
  color: #1f1f1f;
}

.result-desc {
  margin: 0 0 12px;
  color: #5f6368;
  font-size: 13px;
  line-height: 1.6;
}

.result-items {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.result-item {
  border: 1px solid #eceff3;
  border-radius: 14px;
  padding: 12px 14px;
  background: #fff;
}

.item-title {
  font-size: 13px;
  font-weight: 700;
  color: #1f1f1f;
  margin-bottom: 4px;
}

.item-meta {
  font-size: 13px;
  color: #5f6368;
  line-height: 1.55;
}

.item-link {
  display: inline-block;
  margin-top: 6px;
  color: #0b57d0;
  font-size: 13px;
  font-weight: 600;
  text-decoration: none;

  .el-icon {
    top: 2px;
  }
}
</style>
