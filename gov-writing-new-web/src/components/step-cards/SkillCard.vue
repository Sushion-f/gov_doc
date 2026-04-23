<script setup>
import BaseTimelineCard from "@/components/step-cards/BaseTimelineCard.vue";

defineProps({
  event: {
    type: Object,
    required: true,
  },
});
</script>

<template>
  <BaseTimelineCard :event="event" icon="auto_awesome" tone="skill">
    <template #summary>
      <div v-if="event?.payload?.sourceState" class="skill-meta">
        <span class="skill-chip">{{ event.payload.sourceState }}</span>
      </div>
    </template>
  </BaseTimelineCard>
</template>

<style scoped>
.skill-meta {
  display: flex;
  gap: 8px;
}

.skill-chip {
  display: inline-flex;
  align-items: center;
  min-height: 28px;
  padding: 0 10px;
  border-radius: 999px;
  background: #e8f8ec;
  color: #15803d;
  font-size: 12px;
  font-weight: 600;
}
</style>
