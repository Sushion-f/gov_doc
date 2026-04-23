<script setup>
import { computed, ref } from "vue";
import { marked } from "marked";

marked.use({ breaks: true, gfm: true });

const props = defineProps({
  event: {
    type: Object,
    required: true,
  },
});

const expanded = ref(false);

const payload = computed(() => props.event?.payload || {});
const toolName = computed(() => payload.value.toolName || props.event?.title?.replace(/^CLI 工具 ·\s*/, "") || "workspace.ls");
const command = computed(() => payload.value.command || props.event?.detail || "");
const output = computed(() => payload.value.output || "");
const preview = computed(() => {
  const text = String(output.value || "");
  return text.length <= 1200 ? text : `${text.slice(0, 1200).trimEnd()}\n...`;
});

const renderedPreview = computed(() => {
  if (toolName.value === "workspace.cat") {
    return marked.parse(`\`\`\`text\n${preview.value}\n\`\`\``);
  }
  return marked.parse(`\`\`\`text\n${preview.value}\n\`\`\``);
});

const renderedOutput = computed(() => marked.parse(`\`\`\`text\n${output.value}\n\`\`\``));
</script>

<template>
  <article class="cli-card">
    <button class="cli-card-header" type="button" @click="expanded = !expanded">
      <div class="cli-card-title">
        <span class="cli-card-badge">&gt;_</span>
        <div>
          <strong>CLI 工具 · {{ toolName }}</strong>
          <p>{{ command }}</p>
        </div>
      </div>
      <span class="material-symbols-rounded cli-card-chevron">{{ expanded ? "expand_less" : "expand_more" }}</span>
    </button>

    <div class="cli-card-body">
      <div class="cli-card-output markdown-body" v-html="renderedPreview" />
      <button class="cli-card-toggle" type="button" @click="expanded = !expanded">
        {{ expanded ? "收起完整输出" : "展开完整输出" }}
      </button>
      <div v-if="expanded" class="cli-card-full markdown-body" v-html="renderedOutput" />
    </div>
  </article>
</template>

<style scoped>
.cli-card {
  border-radius: 24px;
  border: 1px solid rgba(37, 62, 95, 0.12);
  background: #fff;
  box-shadow: 0 10px 30px rgba(28, 42, 61, 0.06);
  overflow: hidden;
  position: relative;
}

.cli-card::before {
  content: "";
  position: absolute;
  inset: 0 auto 0 0;
  width: 4px;
  background: linear-gradient(180deg, #0f6cbd 0%, #49a2ff 100%);
}

.cli-card-header {
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

.cli-card-title {
  display: flex;
  gap: 12px;
  align-items: flex-start;
}

.cli-card-title strong {
  display: block;
  font-size: 15px;
  color: #152033;
}

.cli-card-title p {
  margin: 6px 0 0;
  color: #5d6b82;
  font-size: 13px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
}

.cli-card-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 34px;
  height: 34px;
  border-radius: 10px;
  background: #eaf4ff;
  color: #0f6cbd;
  font-weight: 700;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
}

.cli-card-chevron {
  color: #68778d;
}

.cli-card-body {
  padding: 0 24px 20px 28px;
}

.cli-card-output,
.cli-card-full {
  border-radius: 16px;
  background: #0f1722;
  color: #dce7f5;
  overflow: auto;
}

.cli-card-toggle {
  margin-top: 10px;
  border: none;
  background: transparent;
  color: #0f6cbd;
  font-size: 13px;
  cursor: pointer;
  padding: 0;
}

:deep(pre) {
  margin: 0;
  padding: 16px 18px;
  font-size: 12px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
}
</style>
