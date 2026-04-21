<template>
  <div class="table-card-step">
    <div class="table-header">
      <div class="table-title-wrap">
        <span class="table-icon">📋</span>
        <h3 class="table-title">{{ content.title || step.label }}</h3>
      </div>
      <button type="button" class="table-export-btn">导出</button>
    </div>
    <p class="table-summary" v-html="content.summary || ''"></p>

    <table class="table-grid">
      <thead>
        <tr>
          <th v-for="(col, idx) in content.columns || []" :key="idx">{{ col }}</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="(row, rowIdx) in content.rows || []" :key="rowIdx">
          <td v-for="(cell, cellIdx) in row" :key="cellIdx">
            <span
              v-if="typeof cell === 'object' && cell?.tag"
              class="priority-tag"
              :class="`p-${cell.tag}`"
            >
              {{ cell.text }}
            </span>
            <span v-else>{{ cell }}</span>
          </td>
        </tr>
      </tbody>
    </table>

    <div v-if="content.footerHint" class="table-footer-hint">{{ content.footerHint }}</div>
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
.table-card-step {
  width: 100%;
  border-radius: 16px;
  border: 1px solid #e6ebf2;
  background: #fff;
  padding: 18px 20px;
}

.table-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.table-title-wrap {
  display: flex;
  align-items: center;
  gap: 8px;
}

.table-title {
  margin: 0;
  font-size: 13px;
  font-weight: 700;
  color: #1f2937;
}

.table-export-btn {
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

.table-summary {
  margin: 14px 0 14px;
  color: #4b5563;
  font-size: 13px;
}

.table-grid {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
  color: #374151;
}

.table-grid th,
.table-grid td {
  text-align: left;
  padding: 10px 8px;
  border-bottom: 1px solid #eef2f7;
}

.table-grid th {
  color: #6b7280;
  font-weight: 600;
}

.priority-tag {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  padding: 2px 10px;
  font-size: 13px;
  font-weight: 600;
}

.p-high {
  background: #ffe7ea;
  color: #dc2626;
}

.p-mid {
  background: #fff7db;
  color: #b45309;
}

.p-low {
  background: #e8f7ec;
  color: #15803d;
}

.table-footer-hint {
  margin-top: 14px;
  text-align: center;
  color: #6b7280;
  font-size: 13px;
}
</style>
