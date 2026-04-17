<script setup>
import { computed, ref } from "vue";
import { marked } from "marked";

marked.use({ breaks: true, gfm: true });

function renderStepDetail(detailHtml, fallbackText) {
  const raw = String(detailHtml || "").trim();
  const fb = String(fallbackText || "").trim();
  if (raw && /<(div|section|article|table|ul|ol|h[1-6])\b/i.test(raw)) {
    return raw;
  }
  const text = fb || raw.replace(/<[^>]+>/g, "").trim();
  if (!text) {
    return raw || "";
  }
  return marked.parse(text);
}

const props = defineProps({
  events: {
    type: Array,
    default: () => [],
  },
  stepOutcomes: {
    type: Array,
    default: () => [],
  },
});

const expandedIds = ref([]);

const visibleEvents = computed(() => {
  const ordered = [];
  const byCardKey = new Map();
  for (const event of props.events) {
    const display = event.display || {};
    if (!display.visible) {
      continue;
    }
    const cardKey = display.cardKey || event.id || event.seqNo;
    if (!byCardKey.has(cardKey)) {
      ordered.push(cardKey);
    }
    byCardKey.set(cardKey, { ...event, display: { ...display, cardKey } });
  }
  return ordered.map((key) => byCardKey.get(key));
});

const visibleStepOutcomes = computed(() =>
  (props.stepOutcomes || []).map((step, index) => ({
    id: step.task_id || `history-step-${index}`,
    eventType: step.retryable ? "waiting_user" : step.error_detail ? "failed" : "completed",
    title: step.title || step.summary || `步骤 ${index + 1}`,
    detail: step.summary || step.title || "已生成结果。",
    detailHtml: step.html || "",
    display: {
      visible: true,
      cardKey: step.task_id || `history-step-${index}`,
      title: step.title || step.summary || `步骤 ${index + 1}`,
      subtitle: step.summary || step.title || "已生成结果。",
      status: step.retryable ? "waiting_user" : step.error_detail ? "failed" : "completed",
    },
  }))
);

const timelineItems = computed(() => (visibleEvents.value.length ? visibleEvents.value : visibleStepOutcomes.value));

function iconClass(eventType) {
  const mapping = {
    created: "think",
    running: "claw",
    tool_call: "tool",
    waiting_user: "skill",
    completed: "skill",
    failed: "cli",
  };
  return mapping[eventType] || "tool";
}

function iconName(eventType) {
  const mapping = {
    created: "psychology",
    running: "robot_2",
    tool_call: "build",
    waiting_user: "person_alert",
    completed: "task_alt",
    failed: "error",
  };
  return mapping[eventType] || "build";
}

function toggle(id) {
  if (expandedIds.value.includes(id)) {
    expandedIds.value = expandedIds.value.filter((item) => item !== id);
    return;
  }
  expandedIds.value = [...expandedIds.value, id];
}

function isExpanded(id) {
  return expandedIds.value.includes(id);
}
</script>

<template>
  <div class="agent-steps">
    <article
      v-for="event in timelineItems"
      :key="event.display?.cardKey || event.id || event.seqNo"
      class="agent-step"
      :class="{ open: isExpanded(event.display?.cardKey || event.id || event.seqNo) }"
    >
      <button
        class="step-header clickable"
        type="button"
        @click="toggle(event.display?.cardKey || event.id || event.seqNo)"
      >
        <span class="step-icon" :class="iconClass(event.display?.status || event.eventType)">
          <span class="material-symbols-rounded">{{ iconName(event.display?.status || event.eventType) }}</span>
        </span>
        <span class="step-label">
          <strong>{{ event.display?.title || event.title }}</strong>
          {{ event.display?.subtitle || event.detail || event.eventType }}
        </span>
        <span class="step-chevron material-symbols-rounded">expand_more</span>
      </button>
      <div v-if="isExpanded(event.display?.cardKey || event.id || event.seqNo)" class="step-content">
        <div
          v-if="event.detailHtml || event.display?.subtitle || event.detail"
          class="markdown-body step-detail-md"
          v-html="
            renderStepDetail(
              event.detailHtml,
              event.display?.subtitle || event.detail || ''
            )
          "
        />
      </div>
    </article>
  </div>
</template>
