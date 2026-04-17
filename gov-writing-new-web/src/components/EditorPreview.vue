<script setup>
import { computed, nextTick, ref, watch } from "vue";
import { RouterLink } from "vue-router";

/** UMD 脚本（见 public/html-docx.js），避免 Vite 无法打包该旧版 bundle */
let htmlDocxLoading = null;
function loadHtmlDocx() {
  if (typeof window !== "undefined" && window.htmlDocx?.asBlob) {
    return Promise.resolve(window.htmlDocx);
  }
  if (!htmlDocxLoading) {
    htmlDocxLoading = new Promise((resolve, reject) => {
      const s = document.createElement("script");
      s.src = `${import.meta.env.BASE_URL}html-docx.js`;
      s.async = true;
      s.dataset.htmlDocx = "1";
      s.onload = () => {
        htmlDocxLoading = null;
        resolve(window.htmlDocx);
      };
      s.onerror = () => {
        htmlDocxLoading = null;
        reject(new Error("无法加载 Word 导出库"));
      };
      document.head.appendChild(s);
    });
  }
  return htmlDocxLoading;
}

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
const activeAnnotationId = ref("");
const sheetRef = ref(null);

const metaPairs = computed(() => {
  if (!props.artifact) {
    return [];
  }
  const title = props.artifact.title?.trim() || "未命名文档";
  return [
    ["类型", props.artifact.artifactType || "document"],
    ["标题", title],
    ["摘要", props.artifact.summary || "可在此继续查看和编辑正文。"],
  ];
});

function sanitizeEditorHtml(value) {
  const raw = value || "";
  if (!raw) {
    return "";
  }
  if (typeof document === "undefined") {
    return raw;
  }
  const tmp = document.createElement("div");
  tmp.innerHTML = raw;
  tmp.querySelectorAll(".planner-stream-panel, .reasoning-panel, h2.writing-thought").forEach((el) => el.remove());
  return tmp.innerHTML;
}

watch(
  () => props.artifact?.contentHtml,
  async (value) => {
    await nextTick();
    if (sheetRef.value) {
      sheetRef.value.innerHTML = sanitizeEditorHtml(value);
    }
    activeAnnotationId.value = "";
  },
  { immediate: true }
);

function resolveRange(root, start, end) {
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  let cursor = 0;
  let startNode = null;
  let endNode = null;
  let startOffset = 0;
  let endOffset = 0;

  while (walker.nextNode()) {
    const node = walker.currentNode;
    const length = node.textContent?.length || 0;
    const nextCursor = cursor + length;
    if (!startNode && start <= nextCursor) {
      startNode = node;
      startOffset = Math.max(start - cursor, 0);
    }
    if (!endNode && end <= nextCursor) {
      endNode = node;
      endOffset = Math.max(end - cursor, 0);
      break;
    }
    cursor = nextCursor;
  }

  if (!startNode || !endNode) {
    return null;
  }
  return { startNode, startOffset, endNode, endOffset };
}

function focusAnnotation(annotation) {
  if (!sheetRef.value) {
    return;
  }
  activeAnnotationId.value = annotation.id;
  const resolved = resolveRange(sheetRef.value, annotation.start || 0, annotation.end || 0);
  if (!resolved) {
    return;
  }
  const selection = window.getSelection();
  const range = document.createRange();
  range.setStart(resolved.startNode, resolved.startOffset);
  range.setEnd(resolved.endNode, resolved.endOffset);
  selection?.removeAllRanges();
  selection?.addRange(range);
  resolved.startNode.parentElement?.scrollIntoView({ behavior: "smooth", block: "center" });
}

async function downloadWord() {
  if (!sheetRef.value) {
    return;
  }
  const html = sheetRef.value.innerHTML || "<p></p>";
  const { asBlob } = await loadHtmlDocx();
  const blob = asBlob(`<!DOCTYPE html><html><head><meta charset="utf-8"></head><body>${html}</body></html>`);
  const name = `${(props.artifact?.title || "文档").replace(/[/\\?%*:|"<>]/g, "-")}.docx`;
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}

function downloadPdf() {
  window.print();
}
</script>

<template>
  <aside class="editor-panel" :aria-hidden="artifact ? 'false' : 'true'">
    <div class="editor-header">
      <button class="icon-ghost" type="button" aria-label="关闭编辑器" @click="emit('close')">
        <span class="material-symbols-rounded">close</span>
      </button>
    </div>

    <div class="editor-meta" v-if="artifact">
      <div v-for="[label, value] in metaPairs" :key="label" class="editor-stat">
        <label>{{ label }}</label>
        <strong>{{ value }}</strong>
      </div>
    </div>

    <div class="editor-toolbar" aria-label="富文本工具栏">
      <div class="toolbar-group">
        <button class="toolbar-button active" type="button">正文</button>
        <button class="toolbar-button" type="button">标题</button>
        <button class="toolbar-button" type="button">引用</button>
      </div>
      <div class="toolbar-divider" />
      <div class="toolbar-group">
        <button class="toolbar-button" type="button">
          <span class="material-symbols-rounded" style="font-size: 16px">format_bold</span>
          加粗
        </button>
        <button class="toolbar-button" type="button">
          <span class="material-symbols-rounded" style="font-size: 16px">format_list_bulleted</span>
          列表
        </button>
      </div>
      <div class="toolbar-divider" />
      <div class="toolbar-group">
        <div class="toolbar-badge">
          <span class="material-symbols-rounded" style="font-size: 16px">text_fields</span>
          仿宋_GB2312 三号
        </div>
      </div>
    </div>

    <div class="editor-main" :class="{ 'no-issues': !annotations.length }">
      <div class="editor-issue-list">
        <button
          v-for="annotation in annotations"
          :key="annotation.id"
          class="editor-issue-item"
          :class="{ active: activeAnnotationId === annotation.id }"
          type="button"
          @click="focusAnnotation(annotation)"
        >
          <strong>{{ annotation.label }}</strong>
          <span>{{ annotation.description }}</span>
        </button>
      </div>

      <div class="editor-sheet-wrap">
        <div ref="sheetRef" class="editor-sheet" contenteditable="true">
          <p v-if="!artifact">点击结果文件后，可在右侧编辑器继续修改正文。</p>
        </div>
      </div>
    </div>

    <div class="editor-footer">
      <div class="editor-footer-text">
        {{ artifact?.summary || "点击结果文件后，可在右侧查看和编辑正文。" }}
      </div>
      <div class="footer-actions">
        <button v-if="artifact" class="secondary-pill" type="button" @click="downloadWord">下载 Word</button>
        <button v-if="artifact" class="secondary-pill" type="button" @click="downloadPdf">下载 PDF</button>
        <RouterLink
          v-if="artifact?.workspaceNodeId"
          class="secondary-pill"
          :to="{ name: 'editor', params: { id: artifact.workspaceNodeId } }"
        >
          打开完整编辑页
        </RouterLink>
        <button class="primary-pill" type="button" @click="emit('close')">关闭</button>
      </div>
    </div>
  </aside>
</template>
