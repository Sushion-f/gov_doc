<script setup>
import BaseTimelineCard from "@/components/step-cards/BaseTimelineCard.vue";

const props = defineProps({
  event: {
    type: Object,
    required: true,
  },
});

const emit = defineEmits(["open-artifact"]);

function openArtifact() {
  emit("open-artifact", {
    id: props.event?.payload?.artifactId,
    title: props.event?.payload?.title,
    summary: props.event?.payload?.summary,
    artifactType: props.event?.payload?.artifactType,
    workspaceNodeId:
      props.event?.payload?.workspaceNodeId || props.event?.payload?.meta?.workspaceNodeId,
  });
}
</script>

<template>
  <BaseTimelineCard :event="event" icon="description" tone="skill">
    <template #footer>
      <button
        v-if="event?.payload?.workspaceNodeId || event?.payload?.meta?.relativePath"
        class="artifact-open"
        type="button"
        @click="openArtifact"
      >
        打开抽屉编辑
      </button>
    </template>
  </BaseTimelineCard>
</template>

<style scoped>
.artifact-open {
  margin-top: 12px;
  border: none;
  border-radius: 999px;
  padding: 9px 14px;
  background: #e8f8ec;
  color: #15803d;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}
</style>
