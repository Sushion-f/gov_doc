<script setup>
import { computed } from "vue";
import BaseTimelineCard from "@/components/step-cards/BaseTimelineCard.vue";

const props = defineProps({
  stage: {
    type: Object,
    required: true,
  },
});

const emit = defineEmits(["open-artifact"]);

const STATUS_LABELS = {
  pending: "待执行",
  running: "进行中",
  done: "已完成",
  waiting: "待补充",
  error: "失败",
};

const EVENT_TYPE_LABELS = {
  planner_plan: "To do",
  agent_invoke: "Sub Agent",
  skill_invoke: "Skill",
  tool_call: "工具",
  cli_exec: "CLI",
  search: "检索",
  completed: "总结",
  message_final: "输出",
  artifact_created: "交付物",
  artifact_updated: "交付物",
  error: "异常",
  waiting_user: "待补充",
};

const syntheticEvent = computed(() => ({
  title: `${props.stage.index}. ${props.stage.title}`,
  detail: props.stage.subtitle,
  detailHtml: "",
  display: {
    title: `${props.stage.index}. ${props.stage.title}`,
    subtitle: props.stage.subtitle,
  },
}));

const tone = computed(() => {
  if (props.stage.status === "error") return "error";
  if (props.stage.status === "waiting") return "waiting";
  if (props.stage.key === "todo") return "plan";
  if (props.stage.key === "tools") return "tool";
  if (props.stage.key === "sub_agent") return "agent";
  if (props.stage.key === "summary" || props.stage.key === "deliverable" || props.stage.key === "result") {
    return "completed";
  }
  return "skill";
});

function statusLabel(status) {
  return STATUS_LABELS[status] || "处理中";
}

function eventTypeLabel(eventType) {
  return EVENT_TYPE_LABELS[eventType] || eventType || "事件";
}

function openArtifact() {
  const artifact = props.stage?.artifact;
  if (!artifact) {
    return;
  }
  emit("open-artifact", {
    id: artifact?.payload?.id || artifact?.payload?.artifactId,
    title: artifact?.payload?.title,
    summary: artifact?.payload?.summary,
    artifactType: artifact?.payload?.artifactType,
    workspaceNodeId: artifact?.payload?.workspaceNodeId || artifact?.payload?.meta?.workspaceNodeId,
  });
}
</script>

<template>
  <BaseTimelineCard
    :event="syntheticEvent"
    :icon="stage.icon || 'check_circle'"
    :tone="tone"
    :default-expanded="stage.status === 'error' || stage.status === 'waiting'"
  >
    <template #summary>
      <div class="stage-meta">
        <span class="stage-status" :class="`status-${stage.status}`">{{ statusLabel(stage.status) }}</span>
        <span v-for="chip in stage.chips || []" :key="`${stage.key}-${chip}`" class="stage-chip">
          {{ chip }}
        </span>
      </div>
    </template>

    <p v-if="stage.description" class="stage-description">
      {{ stage.description }}
    </p>

    <details v-if="stage.events?.length" class="stage-detail">
      <summary>查看过程明细（{{ stage.events.length }}）</summary>
      <ul class="stage-event-list">
        <li v-for="event in stage.events" :key="event.id || event.display?.cardKey || event.seqNo" class="stage-event-row">
          <span class="stage-event-type">{{ eventTypeLabel(event.eventType) }}</span>
          <div class="stage-event-copy">
            <strong>{{ event.display?.title || event.title || "执行步骤" }}</strong>
            <p>{{ event.display?.subtitle || event.detail || "已执行。" }}</p>
          </div>
        </li>
      </ul>
    </details>

    <template #footer>
      <button
        v-if="stage.artifact && (stage.artifact?.payload?.workspaceNodeId || stage.artifact?.payload?.relativePath || stage.artifact?.payload?.meta?.relativePath)"
        class="stage-open"
        type="button"
        @click="openArtifact"
      >
        打开交付物
      </button>
    </template>
  </BaseTimelineCard>
</template>

<style scoped>
.stage-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.stage-status,
.stage-chip,
.stage-event-type {
  display: inline-flex;
  align-items: center;
  min-height: 28px;
  padding: 0 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
}

.stage-status {
  background: #edf3ff;
  color: #0f6cbd;
}

.status-done {
  background: #e8f8ec;
  color: #15803d;
}

.status-running {
  background: #edf3ff;
  color: #0f6cbd;
}

.status-pending {
  background: #f1f5f9;
  color: #5d6b82;
}

.status-waiting {
  background: #fff4dc;
  color: #a86a00;
}

.status-error {
  background: #ffe8e5;
  color: #cf453c;
}

.stage-chip {
  background: #f5f7fb;
  color: #475467;
}

.stage-description {
  margin: 12px 0 0;
  color: #243147;
  font-size: 13px;
  line-height: 1.7;
}

.stage-detail {
  margin-top: 14px;
  border-top: 1px solid rgba(37, 62, 95, 0.08);
  padding-top: 14px;
}

.stage-detail summary {
  cursor: pointer;
  color: #0f6cbd;
  font-size: 13px;
  font-weight: 600;
}

.stage-event-list {
  list-style: none;
  margin: 12px 0 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.stage-event-row {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 14px;
  background: #f8fafc;
}

.stage-event-type {
  flex: none;
  background: #eaf4ff;
  color: #0f6cbd;
}

.stage-event-copy {
  min-width: 0;
}

.stage-event-copy strong {
  display: block;
  color: #152033;
  font-size: 13px;
}

.stage-event-copy p {
  margin: 4px 0 0;
  color: #5d6b82;
  font-size: 12px;
  line-height: 1.6;
}

.stage-open {
  margin-top: 12px;
  border: none;
  border-radius: 999px;
  padding: 9px 14px;
  background: #e8f8ec;
  color: #15803d;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}
</style>
