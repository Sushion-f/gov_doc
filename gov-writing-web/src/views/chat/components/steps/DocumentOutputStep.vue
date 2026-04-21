<template>
  <div class="document-output-card">
    <div class="doc-card-header">
      <div class="doc-card-header-main">
        <div class="doc-badge">
          <span class="doc-badge-icon" aria-hidden="true"
            ><el-icon><Document /></el-icon
          ></span>
          <span>文档输出</span>
        </div>
        <h2 class="doc-card-title" v-html="step.label || '生成文档'"></h2>
      </div>
      <!-- <div class="doc-card-actions">
        <button type="button" class="doc-action-btn" title="联动编辑" @click="onLinkedEdit">
          <el-icon><EditPen /></el-icon>
          联动编辑
        </button>
        <button type="button" class="doc-action-btn" title="查看结果" @click="onViewResult">
          <el-icon><View /></el-icon>
          查看结果
        </button>
      </div> -->
    </div>

    <!-- <p v-if="summaryText" class="doc-card-summary">{{ summaryText }}</p> -->

    <div class="doc-preview-panel">
      <TinymceDocEditor v-model="editorBody" compact auto-grow :readonly="leftEditorReadonly" />
    </div>

    <div class="doc-card-footer">
      <span class="doc-footer-hint"></span>
      <button type="button" class="doc-open-editor" @click="onOpenEditor">
        {{ openEditorLabel }}
        <el-icon class="doc-open-chevron"><ArrowRight /></el-icon>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ArrowRight, Document, EditPen, View } from '@element-plus/icons-vue';
import { computed, inject, nextTick, onBeforeUnmount, ref, watch } from 'vue';
import { LINKED_EDITOR_KEY } from '../../linkedEditor';
import TinymceDocEditor from '../TinymceDocEditor.vue';

const props = withDefaults(
  defineProps<{
    step: Step;
    /** true: 实时回答（流式），false: 历史回显（一次性） */
    animated?: boolean;
  }>(),
  { animated: true }
);

const emit = defineEmits<{
  'streaming-complete': [];
}>();

const linkedHost = inject(LINKED_EDITOR_KEY, null);
const displayedBody = ref('');
let streamTimer: number | null = null;
let syncingFromEditor = false;

const rawContent = computed(
  () =>
    (props.step.content && typeof props.step.content === 'object'
      ? props.step.content
      : {}) as Record<string, unknown>
);

const bodyHtml = computed(() => (rawContent.value.body as string) || '');

const openEditorLabel = computed(() => {
  const c = rawContent.value;
  return (c.openEditorLabel as string) || '在右侧编辑器打开';
});

const editorBody = computed({
  get: () => displayedBody.value,
  set: (v: string) => {
    syncingFromEditor = true;
    displayedBody.value = v;
    if (props.step.content && typeof props.step.content === 'object') {
      (props.step.content as any).body = v;
    }
  },
});

const clearStreamTimer = () => {
  if (streamTimer !== null) {
    clearInterval(streamTimer);
    streamTimer = null;
  }
};

const scrollPreviewToBottom = () => {
  nextTick(() => {
    requestAnimationFrame(() => {
      const host = document.querySelector(
        '.doc-preview-panel .tox-edit-area iframe'
      ) as HTMLIFrameElement | null;
      if (host?.contentWindow?.document?.body) {
        const body = host.contentWindow.document.body;
        const doc = host.contentWindow.document.documentElement;
        const height = Math.max(
          body.scrollHeight,
          body.offsetHeight,
          doc?.scrollHeight || 0,
          doc?.offsetHeight || 0
        );
        host.contentWindow.scrollTo({ top: height, behavior: 'auto' });
      }
    });
  });
};

const splitHtmlByBlock = (html: string): string[] => {
  const normalized = (html || '').replace(/\r/g, '');
  const chunks = normalized.match(/[\s\S]*?(?:<\/p>|<\/h[1-6]>|<\/div>|<br\s*\/?>|$)/gi) || [];
  return chunks.map((item) => item.trim()).filter(Boolean);
};

const renderBody = (html: string) => {
  clearStreamTimer();
  if (!props.animated) {
    displayedBody.value = html;
    scrollPreviewToBottom();
    emit('streaming-complete');
    return;
  }

  const chunks = splitHtmlByBlock(html);
  displayedBody.value = '';
  if (!chunks.length) {
    emit('streaming-complete');
    return;
  }
  let idx = 0;
  streamTimer = window.setInterval(() => {
    if (idx < chunks.length) {
      displayedBody.value += chunks[idx];
      scrollPreviewToBottom();
      idx++;
      return;
    }
    clearStreamTimer();
    emit('streaming-complete');
  }, 90);
};

watch(
  () => [bodyHtml.value, props.animated] as const,
  ([html]) => {
    if (syncingFromEditor) {
      syncingFromEditor = false;
      return;
    }
    renderBody(html || '');
  },
  { immediate: true }
);

onBeforeUnmount(() => {
  clearStreamTimer();
});

const leftEditorReadonly = computed(() => {
  const h = linkedHost;
  if (!h) return false;
  return h.isOpen.value && h.activeStep.value === props.step;
});

const openPanel = () => {
  linkedHost?.open(props.step);
};

const onLinkedEdit = () => {
  openPanel();
};

const onViewResult = () => {
  openPanel();
};

const onOpenEditor = () => {
  openPanel();
};
</script>

<style scoped lang="scss">
.document-output-card {
  width: 100%;
  border-radius: 16px;
  border: 1px solid #e2e8f0;
  background: #ffffff;
  box-shadow: 0 2px 12px rgba(15, 23, 42, 0.06);
  overflow: hidden;
}

.doc-card-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding: 16px 18px 12px;
}

.doc-card-header-main {
  flex: 1;
  min-width: 0;
}

.doc-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: 12px;
  background: rgba(59, 130, 246, 0.12);
  color: #2563eb;
  font-size: 12px;
  font-weight: 600;
  margin-bottom: 10px;
}

.doc-badge-icon {
  font-size: 14px;
  line-height: 1;
  display: inline-flex;
}

.doc-card-title {
  margin: 0;
  font-size: 17px;
  font-weight: 700;
  color: #0f172a;
  line-height: 1.45;
  word-break: break-word;
}

.doc-card-actions {
  display: flex;
  flex-shrink: 0;
  gap: 8px;
}

.doc-action-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  border-radius: 10px;
  border: 1px solid #e2e8f0;
  background: #fff;
  color: #475569;
  font-size: 13px;
  cursor: pointer;
  transition: background 0.15s ease, border-color 0.15s ease, color 0.15s ease;

  &:hover {
    background: #f8fafc;
    border-color: #cbd5e1;
    color: #1e293b;
  }

  .el-icon {
    font-size: 16px;
  }
}

.doc-card-summary {
  margin: 0 18px 14px;
  font-size: 13px;
  line-height: 1.7;
  color: #64748b;
}

.doc-preview-panel {
  margin: 0 16px 16px;
  border-radius: 12px;
  border: 1px solid #e8ecf1;
  overflow: hidden;

  :deep(.tox-tinymce) {
    border: none;

    .tox-edit-area::before {
      display: none;
    }

    .tox-statusbar {
      display: none;
    }
  }
}

.doc-card-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 18px 16px;
  border-top: 1px solid #f1f5f9;
}

.doc-footer-hint {
  font-size: 12px;
  color: #94a3b8;
  line-height: 1.5;
  flex: 1;
  min-width: 0;
}

.doc-open-editor {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 0;
  border: none;
  background: none;
  font-size: 13px;
  font-weight: 600;
  color: #2563eb;
  cursor: pointer;
  white-space: nowrap;
  transition: color 0.15s ease;

  &:hover {
    color: #1d4ed8;
  }
}

.doc-open-chevron {
  font-size: 14px;
}
</style>
