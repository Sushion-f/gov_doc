<script setup>
const props = defineProps({
  block: { type: Object, required: true },
});

const emit = defineEmits(["open-artifact"]);

function openArtifact() {
  emit("open-artifact", {
    id: props.block?.artifact_id,
    artifactId: props.block?.artifact_id,
    workspaceNodeId: props.block?.workspace_node_id,
    title: props.block?.title,
    version: props.block?.version,
  });
}
</script>

<template>
  <button type="button" class="block-artifact-ref" @click="openArtifact">
    <span class="material-symbols-rounded">description</span>
    <div class="body">
      <div class="title">{{ block.title || "产物" }}</div>
      <div v-if="block.summary" class="summary">{{ block.summary }}</div>
      <div class="meta">
        <span v-if="block.version">v{{ block.version }}</span>
        <span>打开文档</span>
      </div>
    </div>
    <span class="material-symbols-rounded arrow">chevron_right</span>
  </button>
</template>

<style scoped>
.block-artifact-ref {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  padding: 12px 16px;
  border-radius: 14px;
  border: 1px solid rgba(37, 99, 235, 0.25);
  background: linear-gradient(135deg, rgba(37, 99, 235, 0.05), rgba(124, 58, 237, 0.05));
  cursor: pointer;
  transition: transform 0.12s ease;
}
.block-artifact-ref:hover {
  transform: translateY(-1px);
}
.body {
  flex: 1;
  text-align: left;
}
.title {
  font-weight: 600;
  font-size: 14px;
  color: #0f172a;
}
.summary {
  margin-top: 4px;
  font-size: 12px;
  color: #64748b;
}
.meta {
  display: flex;
  gap: 10px;
  margin-top: 4px;
  font-size: 11px;
  color: #2563eb;
}
.arrow {
  color: #94a3b8;
}
</style>
