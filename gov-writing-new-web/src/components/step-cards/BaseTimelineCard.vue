<script setup>
import { computed, ref } from "vue";
import { marked } from "marked";

marked.use({ breaks: true, gfm: true });

const props = defineProps({
  event: {
    type: Object,
    required: true,
  },
  icon: {
    type: String,
    default: "build",
  },
  tone: {
    type: String,
    default: "tool",
  },
  title: {
    type: String,
    default: "",
  },
  subtitle: {
    type: String,
    default: "",
  },
  defaultExpanded: {
    type: Boolean,
    default: false,
  },
});

const expanded = ref(props.defaultExpanded);

function renderDetail(detailHtml, fallbackText) {
  const raw = String(detailHtml || "").trim();
  const fb = String(fallbackText || "").trim();
  if (raw && /<(div|section|article|table|ul|ol|h[1-6]|pre)\b/i.test(raw)) {
    return raw;
  }
  const text = fb || raw.replace(/<[^>]+>/g, "").trim();
  if (!text) {
    return raw || "";
  }
  return marked.parse(text);
}

const resolvedTitle = computed(() => props.title || props.event?.display?.title || props.event?.title || "步骤事件");
const resolvedSubtitle = computed(() => props.subtitle || props.event?.display?.subtitle || props.event?.detail || "");
const detailHtml = computed(() =>
  renderDetail(
    props.event?.detailHtml,
    props.event?.display?.subtitle || props.event?.detail || ""
  )
);
const hasDetail = computed(() => Boolean(String(detailHtml.value || "").trim()));
</script>

<template>
  <article class="timeline-card" :class="`tone-${tone}`">
    <button class="timeline-card-header" type="button" @click="expanded = !expanded">
      <div class="timeline-card-title">
        <span class="timeline-card-badge">
          <span class="material-symbols-rounded">{{ icon }}</span>
        </span>
        <div>
          <strong>{{ resolvedTitle }}</strong>
          <p>{{ resolvedSubtitle }}</p>
        </div>
      </div>
      <span class="material-symbols-rounded timeline-card-chevron">
        {{ expanded ? "expand_less" : "expand_more" }}
      </span>
    </button>

    <div class="timeline-card-body">
      <slot name="summary" />
      <slot />
      <button v-if="hasDetail" class="timeline-card-toggle" type="button" @click="expanded = !expanded">
        {{ expanded ? "收起详情" : "展开详情" }}
      </button>
      <div v-if="expanded && hasDetail" class="timeline-card-detail markdown-body" v-html="detailHtml" />
      <slot name="footer" />
    </div>
  </article>
</template>

<style scoped>
.timeline-card {
  border-radius: 24px;
  border: 1px solid rgba(37, 62, 95, 0.12);
  background: #fff;
  box-shadow: 0 10px 30px rgba(28, 42, 61, 0.06);
  overflow: hidden;
  position: relative;
}

.timeline-card::before {
  content: "";
  position: absolute;
  inset: 0 auto 0 0;
  width: 4px;
  background: linear-gradient(180deg, #0f6cbd 0%, #49a2ff 100%);
}

.timeline-card-header {
  width: 100%;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  border: none;
  background: transparent;
  padding: 20px 24px 12px 28px;
  text-align: left;
  cursor: pointer;
}

.timeline-card-title {
  display: flex;
  gap: 12px;
  align-items: flex-start;
}

.timeline-card-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 34px;
  height: 34px;
  border-radius: 10px;
  background: #eaf4ff;
  color: #0f6cbd;
}

.timeline-card-title strong {
  display: block;
  font-size: 15px;
  color: #152033;
}

.timeline-card-title p {
  margin: 6px 0 0;
  color: #5d6b82;
  font-size: 13px;
  line-height: 1.6;
}

.timeline-card-chevron {
  color: #68778d;
}

.timeline-card-body {
  padding: 0 24px 20px 28px;
}

.timeline-card-toggle {
  margin-top: 10px;
  border: none;
  background: transparent;
  color: #0f6cbd;
  font-size: 13px;
  cursor: pointer;
  padding: 0;
}

.timeline-card-detail {
  margin-top: 12px;
  border-radius: 16px;
  background: #f8fafc;
  padding: 14px 16px;
  color: #243147;
}

.tone-plan::before {
  background: linear-gradient(180deg, #0f6cbd 0%, #49a2ff 100%);
}

.tone-plan .timeline-card-badge,
.tone-agent .timeline-card-badge {
  background: #eaf4ff;
  color: #0f6cbd;
}

.tone-skill::before,
.tone-completed::before {
  background: linear-gradient(180deg, #15803d 0%, #5bc86d 100%);
}

.tone-skill .timeline-card-badge,
.tone-completed .timeline-card-badge {
  background: #e8f8ec;
  color: #15803d;
}

.tone-tool::before,
.tone-search::before {
  background: linear-gradient(180deg, #8b5cf6 0%, #bf7bff 100%);
}

.tone-tool .timeline-card-badge,
.tone-search .timeline-card-badge {
  background: #f3e8ff;
  color: #7c3aed;
}

.tone-waiting::before {
  background: linear-gradient(180deg, #e8a126 0%, #ffd76b 100%);
}

.tone-waiting .timeline-card-badge {
  background: #fff4dc;
  color: #a86a00;
}

.tone-error::before,
.tone-aborted::before {
  background: linear-gradient(180deg, #cf453c 0%, #ff7a6b 100%);
}

.tone-error .timeline-card-badge,
.tone-aborted .timeline-card-badge {
  background: #ffe7e4;
  color: #b42318;
}
</style>
