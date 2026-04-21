<template>
  <div class="analysis-output" :class="{ 'stream-hidden': !visible, 'stream-visible': visible }">
    <div class="analysis-output-header">
      <span class="analysis-output-title">📊 {{ analysis.title }}</span>
      <div class="doc-actions">
        <button class="doc-action-btn" @click="handleExport">
          <el-icon><Download /></el-icon>
          导出
        </button>
      </div>
    </div>
    <div class="analysis-body">
      <div class="analysis-summary-text" v-html="analysis.summary"></div>
      <div class="chart-title">{{ analysis.chartTitle }}</div>
      <div class="bar-chart">
        <div v-for="(item, index) in analysis.chartData" :key="index" class="bar-row">
          <span class="bar-label">{{ item.label }}</span>
          <div class="bar-track">
            <div class="bar-fill" :style="{ width: item.percent + '%' }">
              <span class="bar-val">{{ item.value }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Download } from '@element-plus/icons-vue';

const props = defineProps({
  analysis: {
    type: Object as () => Analysis,
    default: () => ({
      title: '',
      summary: '',
      chartTitle: '',
      chartData: [],
    }),
  },
  visible: {
    type: Boolean,
    default: false,
  },
});

const emit = defineEmits<{
  export: [analysis: Analysis];
}>();

const handleExport = () => {
  emit('export', props.analysis);
};
</script>

<style scoped lang="scss">
.analysis-output {
  margin-top: 8px;
  border-radius: 12px;
  background: #fff;
  border: 1px solid rgba(0, 0, 0, 0.08);
  overflow: hidden;
  transition: all 0.3s ease;

  &.stream-hidden {
    display: none;
  }

  &.stream-visible {
    display: block;
    animation: fadeIn 0.3s ease;
  }
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.analysis-output-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  background: rgba(0, 0, 0, 0.02);
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
}

.analysis-output-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--on-surface);
}

.doc-actions {
  display: flex;
  gap: 6px;
}

.doc-action-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 12px;
  background: none;
  border: 1px solid rgba(0, 0, 0, 0.1);
  border-radius: 6px;
  font-size: 12px;
  font-weight: 500;
  color: var(--on-surface-variant);
  cursor: pointer;
  font-family: inherit;
  transition: all 0.12s ease;

  &:hover {
    background: rgba(0, 0, 0, 0.04);
    border-color: rgba(0, 0, 0, 0.15);
    color: var(--on-surface);
  }

  .el-icon {
    font-size: 14px;
  }
}

.analysis-body {
  padding: 16px 20px;
  background: #fff;
}

.analysis-summary-text {
  font-size: 14px;
  line-height: 1.6;
  color: var(--on-surface);
  margin-bottom: 16px;
  padding: 12px;
  background: rgba(0, 47, 134, 0.04);
  border-radius: 8px;
  border-left: 3px solid var(--primary);
}

.chart-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--on-surface);
  margin-bottom: 12px;
}

.bar-chart {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.bar-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.bar-label {
  width: 80px;
  font-size: 13px;
  color: var(--on-surface);
  text-align: right;
  flex-shrink: 0;
}

.bar-track {
  flex: 1;
  height: 28px;
  background: rgba(0, 0, 0, 0.04);
  border-radius: 4px;
  overflow: hidden;
  position: relative;
}

.bar-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--primary) 0%, var(--primary-soft) 100%);
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  padding-right: 8px;
  transition: width 0.5s ease;
  position: relative;

  &::after {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: linear-gradient(90deg, transparent 0%, rgba(255, 255, 255, 0.2) 50%, transparent 100%);
    animation: shimmer 2s infinite;
  }
}

@keyframes shimmer {
  0% {
    transform: translateX(-100%);
  }
  100% {
    transform: translateX(100%);
  }
}

.bar-val {
  font-size: 12px;
  font-weight: 600;
  color: #fff;
  z-index: 1;
}
</style>
