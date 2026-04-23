<script setup>
import { computed } from "vue";

const props = defineProps({
  event: {
    type: Object,
    required: true,
  },
});

function formatTokens(value) {
  const n = Number(value || 0);
  if (n >= 1000) {
    return `${(n / 1000).toFixed(n >= 100000 ? 0 : 1).replace(/\.0$/, "")}K`;
  }
  return `${n}`;
}

const payload = computed(() => props.event?.payload || {});
const beforeUsage = computed(() => payload.value.contextUsageBefore || null);
const afterUsage = computed(() => payload.value.contextUsageAfter || payload.value || null);
</script>

<template>
  <article class="context-card">
    <div class="context-card-header">
      <div class="context-card-title">
        <span class="context-card-badge">
          <span class="material-symbols-rounded">compress</span>
        </span>
        <div>
          <strong>{{ event.display?.title || event.title || "上下文压缩" }}</strong>
          <p>{{ event.display?.subtitle || event.detail || "已更新上下文摘要。" }}</p>
        </div>
      </div>
    </div>

    <div class="context-card-body">
      <div class="context-card-metric">
        <span>压缩前</span>
        <strong>
          {{ beforeUsage ? `${formatTokens(beforeUsage.used)} / ${formatTokens(beforeUsage.window)}` : "自动计量" }}
        </strong>
      </div>
      <div class="context-card-metric">
        <span>压缩后</span>
        <strong>
          {{ afterUsage ? `${formatTokens(afterUsage.used)} / ${formatTokens(afterUsage.window)}` : "已完成" }}
        </strong>
      </div>
    </div>
  </article>
</template>

<style scoped>
.context-card {
  border-radius: 24px;
  border: 1px solid rgba(37, 62, 95, 0.12);
  background: #fff;
  box-shadow: 0 10px 30px rgba(28, 42, 61, 0.06);
  overflow: hidden;
  position: relative;
}

.context-card::before {
  content: "";
  position: absolute;
  inset: 0 auto 0 0;
  width: 4px;
  background: linear-gradient(180deg, #e8a126 0%, #ffd76b 100%);
}

.context-card-header {
  padding: 20px 24px 12px 28px;
}

.context-card-title {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.context-card-title strong {
  display: block;
  font-size: 15px;
  color: #152033;
}

.context-card-title p {
  margin: 6px 0 0;
  color: #5d6b82;
  font-size: 13px;
}

.context-card-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 34px;
  height: 34px;
  border-radius: 10px;
  background: #fff4dc;
  color: #a86a00;
}

.context-card-body {
  padding: 0 24px 20px 28px;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.context-card-metric {
  border-radius: 16px;
  background: #f8fafc;
  padding: 14px 16px;
}

.context-card-metric span {
  display: block;
  font-size: 12px;
  color: #6b778c;
  margin-bottom: 6px;
}

.context-card-metric strong {
  color: #172030;
  font-size: 14px;
}

@media (max-width: 720px) {
  .context-card-body {
    grid-template-columns: 1fr;
  }
}
</style>
