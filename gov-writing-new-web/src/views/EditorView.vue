<script setup>
import { computed, nextTick, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { fetchDocument, saveDocument, state } from "@/store";

const route = useRoute();
const router = useRouter();
const editorRef = ref(null);
const localTitle = ref("未命名文档");
const activeAnnotationId = ref("");

const annotations = computed(() => state.currentDocument?.annotations || []);

async function loadCurrentDocument(id) {
  if (!id) {
    return;
  }
  const doc = await fetchDocument(id);
  localTitle.value = doc.title;
  await nextTick();
  if (editorRef.value) {
    editorRef.value.innerHTML = doc.contentHtml || "<p></p>";
  }
  activeAnnotationId.value = "";
}

onMounted(async () => {
  await loadCurrentDocument(route.params.id);
});

watch(
  () => route.params.id,
  async (id) => {
    await loadCurrentDocument(id);
  }
);

function plainTextFromHtml(html) {
  return html.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();
}

async function handleSave() {
  if (!route.params.id || !editorRef.value) {
    return;
  }
  const html = editorRef.value.innerHTML;
  await saveDocument(route.params.id, {
    title: localTitle.value,
    content_html: html,
    content_text: plainTextFromHtml(html),
    annotations: annotations.value,
  });
}

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

function applyAnnotation(annotation) {
  if (!editorRef.value) {
    return;
  }
  activeAnnotationId.value = annotation.id;
  editorRef.value.focus();
  const resolved = resolveRange(editorRef.value, annotation.start || 0, annotation.end || 0);
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
</script>

<template>
  <section class="route-editor-page">
    <header class="toolbar">
      <button class="btn-back" @click="router.back()">
        <span class="material-symbols-rounded" style="font-size: 16px">arrow_back</span>
        返回
      </button>
      <input v-model="localTitle" class="doc-title-input" type="text" />
      <div class="editor-toolbar-actions">
        <button class="btn-back" @click="handleSave">
          <span class="material-symbols-rounded" style="font-size: 16px">save</span>
          保存
        </button>
      </div>
    </header>

    <div class="route-editor-workbench">
      <aside v-if="annotations.length" class="route-editor-side">
        <div class="route-editor-side-title">联动问题</div>
        <button
          v-for="annotation in annotations"
          :key="annotation.id"
          class="route-annotation-card"
          :class="{ active: activeAnnotationId === annotation.id }"
          @click="applyAnnotation(annotation)"
        >
          <strong>{{ annotation.label }}</strong>
          <span>{{ annotation.description }}</span>
        </button>
      </aside>

      <div class="editor-area">
        <div class="doc-sheet-route">
          <div
            v-if="!state.currentDocument?.contentHtml"
            class="placeholder-text"
          >
            <div class="icon">
              <span class="material-symbols-rounded" style="font-size: 48px; color: #d1d5db">description</span>
            </div>
            <p>文档编辑器</p>
            <p class="sub">点击左侧历史或云盘文档后，可在这里继续编辑正文</p>
          </div>
          <div ref="editorRef" class="doc-sheet-editor" contenteditable="true" />
        </div>
      </div>
    </div>
  </section>
</template>
