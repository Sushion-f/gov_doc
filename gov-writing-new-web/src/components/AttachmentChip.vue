<script setup>
import { computed } from "vue";

const props = defineProps({
  item: {
    type: Object,
    required: true,
  },
  removable: {
    type: Boolean,
    default: false,
  },
  previewLabel: {
    type: String,
    default: "右滑预览",
  },
});

const emit = defineEmits(["open", "remove"]);

const title = computed(() => props.item?.title || props.item?.name || "未命名文件");
const subtitle = computed(() => props.item?.summary || props.item?.sourceLabel || "点击打开抽屉预览");
const iconName = computed(() => {
  const type = String(props.item?.fileType || props.item?.artifactType || "").toLowerCase();
  if (type.includes("pdf")) return "picture_as_pdf";
  if (type.includes("sheet") || type.includes("xlsx")) return "table_chart";
  if (type.includes("ppt") || type.includes("presentation")) return "slideshow";
  return "description";
});
</script>

<template>
  <div
    class="attachment-chip-card"
    role="button"
    tabindex="0"
    @click="emit('open', item)"
    @keydown.enter.prevent="emit('open', item)"
    @keydown.space.prevent="emit('open', item)"
  >
    <span class="attachment-chip-icon">
      <span class="material-symbols-rounded">{{ iconName }}</span>
    </span>
    <span class="attachment-chip-copy">
      <strong>{{ title }}</strong>
      <small>{{ subtitle }}</small>
    </span>
    <span class="attachment-chip-preview">
      {{ previewLabel }}
      <span class="material-symbols-rounded">chevron_right</span>
    </span>
    <button
      v-if="removable"
      class="attachment-chip-remove"
      type="button"
      aria-label="移除附件"
      @click.stop="emit('remove', item)"
    >
      <span class="material-symbols-rounded">close</span>
    </button>
  </div>
</template>

<style scoped>
.attachment-chip-card {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 14px 16px;
  border-radius: 18px;
  border: 1px solid rgba(31, 41, 55, 0.08);
  background: linear-gradient(180deg, #ffffff 0%, #f9fbfe 100%);
  box-shadow: 0 8px 24px rgba(24, 39, 75, 0.06);
  text-align: left;
  position: relative;
}

.attachment-chip-icon {
  width: 42px;
  height: 42px;
  border-radius: 14px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: #eef5ff;
  color: #0f6cbd;
  flex-shrink: 0;
}

.attachment-chip-copy {
  display: flex;
  flex-direction: column;
  min-width: 0;
  gap: 4px;
}

.attachment-chip-copy strong {
  color: #122033;
  font-size: 14px;
  line-height: 1.3;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.attachment-chip-copy small {
  color: #66768d;
  font-size: 12px;
  line-height: 1.3;
}

.attachment-chip-preview {
  margin-left: auto;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: #0f6cbd;
  font-size: 12px;
  white-space: nowrap;
}

.attachment-chip-remove {
  position: absolute;
  top: 8px;
  right: 8px;
  width: 28px;
  height: 28px;
  border-radius: 999px;
  border: none;
  background: rgba(15, 23, 42, 0.04);
  color: #6b7280;
}
</style>
