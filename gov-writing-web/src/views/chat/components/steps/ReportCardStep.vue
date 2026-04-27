<template>
  <div class="report-card-step">
    <div class="report-header">
      <div class="report-title-wrap">
        <span class="report-icon">📊</span>
        <h3 class="report-title">{{ content.title || step.label }}</h3>
      </div>
      <button type="button" class="report-export-btn">导出</button>
    </div>
    <p class="report-summary" v-html="content.summary || ''"></p>
    <div class="report-chart-title">{{ content.chartTitle || '' }}</div>
    <div class="report-bars">
      <div v-for="(item, idx) in content.chartData || []" :key="idx" class="report-bar-row">
        <span class="report-bar-label">{{ item.label }}</span>
        <div class="report-bar-track">
          <div
            class="report-bar-fill"
            :style="{ width: `${Math.max(4, Number(item.percent) || 0)}%` }"
          >
            <span class="report-bar-value">{{ item.value }}</span>
          </div>
        </div>
      </div>
    </div>
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

const content = computed(() => (props.step.content || {}) as any);

onMounted(() => {
  emit('streaming-complete');
});
</script>

<style scoped lang="scss">
.report-card-step {
  width: 100%;
  border-radius: 16px;
  border: 1px solid #e6ebf2;
  background: #fff;
  padding: 18px 20px;
}

.report-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.report-title-wrap {
  display: flex;
  align-items: center;
  gap: 8px;
}

.report-icon {
  font-size: 18px;
}

.report-title {
  margin: 0;
  font-size: 13px;
  line-height: 1.3;
  color: #1f2937;
  font-weight: 700;
}

.report-export-btn {
  padding: 5px 10px;
  background: none;
  border: 1px solid rgba(148, 163, 184, 0.24);
  border-radius: 8px;
  font-size: 12px;
  color: #64748b;
  cursor: pointer;
  font-family: inherit;
  transition: background 0.12s ease;

  &:hover {
    background: rgba(0, 47, 134, 0.05);
  }
}

.report-summary {
  margin: 14px 0 18px;
  color: #4b5563;
  font-size: 13px;
  line-height: 1.6;
}

.report-chart-title {
  color: #6b7280;
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 14px;
}

.report-bars {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.report-bar-row {
  display: grid;
  grid-template-columns: 80px 1fr;
  align-items: center;
  gap: 12px;
}

.report-bar-label {
  color: #4b5563;
  font-size: 13px;
  text-align: right;
}

.report-bar-track {
  width: 100%;
  height: 22px;
  background: #ebf0f7;
  border-radius: 4px;
  overflow: hidden;
}

.report-bar-fill {
  height: 100%;
  background: linear-gradient(90deg, #003e9f, #2f6ef2);
  border-radius: 4px;
  position: relative;
  min-width: 56px;
}

.report-bar-value {
  position: absolute;
  right: 12px;
  top: 50%;
  transform: translateY(-50%);
  color: #fff;
  font-weight: 700;
  font-size: 13px;
}
</style>
