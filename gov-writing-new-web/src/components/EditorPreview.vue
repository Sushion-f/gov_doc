<script setup>
import { computed, ref, watch } from "vue";
import { RouterLink } from "vue-router";
import Editor from "@tinymce/tinymce-vue";
import tinymce from "tinymce/tinymce";
import "tinymce/icons/default";
import "tinymce/models/dom";
import "tinymce/themes/silver";
import "tinymce/plugins/code";
import "tinymce/plugins/codesample";
import "tinymce/plugins/image";
import "tinymce/plugins/link";
import "tinymce/plugins/lists";
import "tinymce/plugins/searchreplace";
import "tinymce/plugins/table";
import "tinymce/plugins/wordcount";

import { fetchDocument, saveDocument } from "@/store";

const props = defineProps({
  artifact: {
    type: Object,
    default: null,
  },
  annotations: {
    type: Array,
    default: () => [],
  },
});

const emit = defineEmits(["close"]);

const loading = ref(false);
const saving = ref(false);
const doc = ref(null);
const html = ref("");
const localTitle = ref("");
const renaming = ref(false);
const errorText = ref("");

const nodeId = computed(() => props.artifact?.workspaceNodeId || props.artifact?.nodeId || props.artifact?.id || "");
const effectiveAnnotations = computed(() => doc.value?.annotations || props.annotations || []);
const meta = computed(() => doc.value?.meta || {});
const isEditable = computed(() => Boolean(meta.value.editable));
const isPdfReadOnly = computed(() => meta.value.fileType === "pdf" && !isEditable.value);

const tinyInit = computed(() => ({
  height: 540,
  menubar: false,
  branding: false,
  promotion: false,
  base_url: "/tinymce",
  suffix: ".min",
  license_key: "gpl",
  language: "zh_CN",
  language_url: "/tinymce/langs/zh_CN.js",
  skin_url: "/tinymce/skins/ui/oxide",
  content_css: "/tinymce/skins/content/default/content.css",
  plugins: "lists link table image code codesample searchreplace wordcount",
  toolbar:
    "undo redo | blocks | bold italic underline | bullist numlist | alignleft aligncenter alignright | table link image | searchreplace code codesample",
  readonly: !isEditable.value,
  statusbar: true,
  resize: false,
}));

function plainTextFromHtml(source) {
  return String(source || "")
    .replace(/<br\s*\/?>/gi, "\n")
    .replace(/<\/(p|div|li|h[1-6]|blockquote|tr)>/gi, "\n")
    .replace(/<[^>]+>/g, " ")
    .replace(/\n{3,}/g, "\n\n")
    .replace(/[ \t]+/g, " ")
    .trim();
}

async function loadDrawerDocument() {
  if (!nodeId.value) {
    doc.value = null;
    html.value = "";
    localTitle.value = "";
    return;
  }
  loading.value = true;
  errorText.value = "";
  try {
    const data = await fetchDocument(nodeId.value);
    doc.value = data;
    html.value = data.contentHtml || "<p></p>";
    localTitle.value = data.title || props.artifact?.title || "未命名文档";
    renaming.value = false;
  } catch (error) {
    errorText.value = String(error.message || error);
  } finally {
    loading.value = false;
  }
}

watch(
  () => nodeId.value,
  async () => {
    await loadDrawerDocument();
  },
  { immediate: true }
);

async function handleSave() {
  if (!nodeId.value || saving.value) {
    return;
  }
  saving.value = true;
  errorText.value = "";
  try {
    await saveDocument(nodeId.value, {
      title: localTitle.value,
      content_html: html.value,
      content_text: plainTextFromHtml(html.value),
      annotations: effectiveAnnotations.value,
    });
    await loadDrawerDocument();
  } catch (error) {
    errorText.value = String(error.message || error);
  } finally {
    saving.value = false;
  }
}

function beginRename() {
  if (!doc.value) {
    return;
  }
  renaming.value = true;
}

function finishRename() {
  renaming.value = false;
}

function downloadUrl() {
  if (!nodeId.value) {
    return "#";
  }
  return `${import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000"}/api/agentloop/workspace/download/${nodeId.value}`;
}
</script>

<template>
  <aside class="preview-drawer" :class="{ open: !!artifact }" :aria-hidden="artifact ? 'false' : 'true'">
    <div class="preview-drawer-head">
      <div class="preview-drawer-title">
        <span class="preview-drawer-icon material-symbols-rounded">
          {{ isPdfReadOnly ? "picture_as_pdf" : "description" }}
        </span>
        <div class="preview-drawer-copy">
          <input
            v-if="renaming"
            v-model="localTitle"
            class="preview-drawer-title-input"
            type="text"
            @blur="finishRename"
            @keydown.enter.prevent="finishRename"
          />
          <h3 v-else @dblclick="beginRename">{{ localTitle || artifact?.title || "未命名文档" }}</h3>
          <p>{{ artifact?.summary || meta.readOnlyReason || "在抽屉中查看并继续编辑工作区文档。" }}</p>
        </div>
      </div>
      <button class="icon-ghost" type="button" aria-label="关闭编辑器" @click="emit('close')">
        <span class="material-symbols-rounded">close</span>
      </button>
    </div>

    <div v-if="isPdfReadOnly" class="preview-drawer-banner">
      PDF 只读，保存时会自动另存为 DOCX 后继续编辑。
    </div>

    <div v-if="loading" class="preview-drawer-loading">正在加载文档内容…</div>
    <div v-else-if="errorText" class="preview-drawer-error">{{ errorText }}</div>
    <div v-else class="preview-drawer-body">
      <div v-if="effectiveAnnotations.length" class="preview-drawer-annotations">
        <button
          v-for="annotation in effectiveAnnotations"
          :key="annotation.id"
          class="preview-drawer-annotation"
          type="button"
        >
          <strong>{{ annotation.label }}</strong>
          <span>{{ annotation.description }}</span>
        </button>
      </div>

      <div class="preview-drawer-editor">
        <Editor
          v-model="html"
          license-key="gpl"
          api-key="no-api-key"
          :init="tinyInit"
        />
      </div>
    </div>

    <div class="preview-drawer-foot">
      <div class="preview-drawer-meta">
        {{ meta.fileType ? `${String(meta.fileType).toUpperCase()} · ${isEditable ? "可编辑" : "只读预览"}` : "" }}
      </div>
      <div class="preview-drawer-actions">
        <a v-if="nodeId" class="secondary-pill" :href="downloadUrl()" target="_blank" rel="noreferrer">下载</a>
        <RouterLink
          v-if="nodeId"
          class="secondary-pill"
          :to="{ name: 'editor', params: { id: nodeId } }"
        >
          打开完整编辑页
        </RouterLink>
        <button class="primary-pill" type="button" :disabled="saving || !nodeId" @click="handleSave">
          {{ saving ? "保存中…" : isPdfReadOnly ? "保存为 DOCX" : "保存" }}
        </button>
      </div>
    </div>
  </aside>
</template>

<style scoped>
.preview-drawer {
  position: fixed;
  top: 24px;
  right: 24px;
  bottom: 24px;
  width: min(780px, calc(100vw - 48px));
  border-radius: 28px;
  background: #fff;
  box-shadow: 0 24px 60px rgba(18, 31, 53, 0.16);
  border: 1px solid rgba(17, 24, 39, 0.08);
  display: flex;
  flex-direction: column;
  transform: translateX(calc(100% + 40px));
  opacity: 0;
  pointer-events: none;
  transition: transform 220ms ease, opacity 220ms ease;
  z-index: 40;
}

.preview-drawer.open {
  transform: translateX(0);
  opacity: 1;
  pointer-events: auto;
}

.preview-drawer-head,
.preview-drawer-foot {
  padding: 20px 24px;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.preview-drawer-head {
  border-bottom: 1px solid rgba(17, 24, 39, 0.08);
}

.preview-drawer-title {
  display: flex;
  gap: 14px;
  min-width: 0;
}

.preview-drawer-icon {
  width: 44px;
  height: 44px;
  border-radius: 14px;
  background: #eef5ff;
  color: #0f6cbd;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.preview-drawer-copy {
  min-width: 0;
}

.preview-drawer-copy h3 {
  margin: 0;
  font-size: 18px;
  color: #132033;
}

.preview-drawer-copy p {
  margin: 6px 0 0;
  color: #6a7688;
  font-size: 13px;
}

.preview-drawer-title-input {
  width: min(420px, 100%);
  border: 1px solid #c8d4e8;
  border-radius: 12px;
  padding: 10px 12px;
  font-size: 16px;
}

.preview-drawer-banner,
.preview-drawer-loading,
.preview-drawer-error {
  margin: 18px 24px 0;
  padding: 12px 14px;
  border-radius: 14px;
  font-size: 13px;
}

.preview-drawer-banner {
  background: #fff7e6;
  color: #8a5a00;
}

.preview-drawer-loading {
  background: #f5f8fc;
  color: #506077;
}

.preview-drawer-error {
  background: #fff1f2;
  color: #b42318;
}

.preview-drawer-body {
  flex: 1;
  min-height: 0;
  padding: 18px 24px;
  display: flex;
  gap: 18px;
}

.preview-drawer-annotations {
  width: 220px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
  overflow: auto;
}

.preview-drawer-annotation {
  border: 1px solid rgba(17, 24, 39, 0.08);
  background: #fafcff;
  border-radius: 16px;
  padding: 12px;
  text-align: left;
}

.preview-drawer-annotation strong {
  display: block;
  color: #152033;
  margin-bottom: 6px;
}

.preview-drawer-annotation span {
  color: #6b7280;
  font-size: 12px;
  line-height: 1.5;
}

.preview-drawer-editor {
  min-width: 0;
  flex: 1;
}

.preview-drawer-meta {
  color: #6b7280;
  font-size: 12px;
}

.preview-drawer-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

@media (max-width: 960px) {
  .preview-drawer {
    top: 12px;
    right: 12px;
    bottom: 12px;
    left: 12px;
    width: auto;
  }

  .preview-drawer-body {
    flex-direction: column;
  }

  .preview-drawer-annotations {
    width: auto;
    max-height: 160px;
  }
}
</style>
