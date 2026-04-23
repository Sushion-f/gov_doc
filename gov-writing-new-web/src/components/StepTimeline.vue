<script setup>
import { computed } from "vue";

const props = defineProps({
  events: {
    type: Array,
    default: () => [],
  },
});

const emit = defineEmits(["open-artifact"]);

const flowItems = computed(() => {
  const items = [];
  for (const entry of props.events || []) {
    if (entry?.type === "assistant") {
      for (const block of entry?.message?.content || []) {
        if (!block?.type) {
          continue;
        }
        if (block.type === "tool_use" || block.type === "tool_result") {
          items.push({
            key: block.id || block.tool_use_id || `${entry.message?.id}-${block.type}`,
            kind: block.type,
            icon: block.type === "tool_use" ? "play_circle" : "task_alt",
            title: block.display_label || block.name || "执行步骤",
            summary: block.summary || block.metadata?.detail || "",
            status: block.status || (block.type === "tool_use" ? "running" : "completed"),
          });
        }
        if (block.type === "artifact") {
          items.push({
            key: block.id || `${entry.message?.id}-artifact`,
            kind: "artifact",
            icon: block.status === "artifact_error" ? "warning" : "description",
            title: block.title || "交付物",
            summary: block.errorDetail || block.summary || "",
            status: block.status || "ready",
            artifact: block,
          });
        }
      }
    }
    if (entry?.type === "result" && entry?.subtype === "error") {
      items.push({
        key: `${entry.run_id || "run"}-result-error`,
        kind: "result_error",
        icon: "error",
        title: "执行异常",
        summary: entry?.error?.message || entry?.summary || "执行失败",
        status: "failed",
      });
    }
  }
  return items;
});
</script>

<template>
  <div v-if="flowItems.length" class="flow-list">
    <article
      v-for="item in flowItems"
      :key="item.key"
      class="flow-card"
      :class="[`is-${item.status}`]"
    >
      <div class="flow-card-main">
        <span class="flow-card-icon material-symbols-rounded">{{ item.icon }}</span>
        <div class="flow-card-copy">
          <div class="flow-card-title">{{ item.title }}</div>
          <div v-if="item.summary" class="flow-card-summary">{{ item.summary }}</div>
        </div>
      </div>
      <button
        v-if="item.artifact && (item.artifact.workspaceNodeId || item.artifact.id)"
        class="flow-card-action"
        type="button"
        @click="emit('open-artifact', item.artifact)"
      >
        打开
      </button>
    </article>
  </div>
</template>

<style scoped>
.flow-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.flow-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 14px;
  border-radius: 16px;
  border: 1px solid rgba(15, 23, 42, 0.08);
  background: #ffffff;
}

.flow-card.is-running {
  background: #f8fafc;
}

.flow-card.is-completed,
.flow-card.is-ready {
  background: #f0fdf4;
}

.flow-card.is-artifact_error,
.flow-card.is-failed {
  background: #fef2f2;
}

.flow-card-main {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  min-width: 0;
}

.flow-card-icon {
  font-size: 18px;
  color: #4b5563;
}

.flow-card-copy {
  min-width: 0;
}

.flow-card-title {
  font-size: 14px;
  font-weight: 600;
  color: #111827;
}

.flow-card-summary {
  margin-top: 3px;
  font-size: 12px;
  line-height: 1.5;
  color: #6b7280;
}

.flow-card-action {
  flex-shrink: 0;
  border: none;
  border-radius: 999px;
  padding: 8px 12px;
  background: #111827;
  color: #fff;
  cursor: pointer;
}
</style>
