<template>
  <div
    class="tinymce-doc-editor"
    :class="{
      compact: compact,
      'tinymce-doc-editor--panel': variant === 'panel',
    }"
  >
    <Editor
      v-model="inner"
      license-key="gpl"
      :init="editorInit"
      :inline="false"
      :readonly="readonly"
    />
  </div>
</template>

<script setup lang="ts">
import Editor from '@tinymce/tinymce-vue';
import { computed } from 'vue';
import { createDocEditorInit, DOC_CONTENT_STYLE_PANEL } from '../tinymce/docEditorInit';

const props = withDefaults(
  defineProps<{
    modelValue: string;
    compact?: boolean;
    /** 紧凑模式下根据内容自适应高度 */
    autoGrow?: boolean;
    readonly?: boolean;
    /** 右侧联动编辑器：灰底上的「纸张」样式与工具栏胶囊按钮 */
    variant?: 'default' | 'panel';
  }>(),
  { compact: false, autoGrow: false, readonly: false, variant: 'default' }
);

const emit = defineEmits<{
  'update:modelValue': [string];
}>();

const inner = computed({
  get: () => props.modelValue,
  set: (v: string) => emit('update:modelValue', v),
});

const editorInit = computed(() => {
  if (props.variant === 'panel') {
    return createDocEditorInit({
      content_style: DOC_CONTENT_STYLE_PANEL,
      min_height: 380,
      autoresize_min_height: 380,
      autoresize_bottom_margin: 24,
      statusbar: false,
      resize: true,
      fontsize_formats: '12pt 14pt 三号=16pt 18pt 20pt',
    });
  }
  return createDocEditorInit(
    props.compact
      ? props.autoGrow
        ? {
            min_height: 260,
            autoresize_min_height: 260,
            autoresize_bottom_margin: 24,
            plugins: 'lists link',
            resize: false,
          }
        : {
            min_height: 260,
            height: 680,
            plugins: 'lists link',
            resize: false,
          }
      : {
          min_height: 420,
          autoresize_min_height: 420,
        }
  );
});
</script>

<style scoped lang="scss">
.tinymce-doc-editor {
  width: 100%;
  height: 100%;

  &:not(.tinymce-doc-editor--panel) :deep(.tox-tinymce) {
    border-radius: 8px;
    border-color: #e2e8f0 !important;
  }

  &.compact :deep(.tox-tinymce) {
    border-radius: 8px;
  }

  &.tinymce-doc-editor--panel {
    width: 100%;
  }

  :deep(.tox-tinymce) {
    min-height: 500px;
    height: 100% !important;
    .tox-edit-area::before {
      display: none;
    }

    .tox-statusbar {
      display: none;
    }
  }
}
</style>
