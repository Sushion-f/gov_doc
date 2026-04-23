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
  <BaseTimelineCard :event="event" icon="checklist" tone="plan">
    <template #summary>
      <div v-if="event?.payload?.plan?.steps?.length" class="plan-summary">
        <span
          v-for="step in event.payload.plan.steps"
          :key="`${event.id}-${step.index}`"
          class="plan-chip"
        >
          {{ step.title || step.skillName || `步骤 ${step.index}` }}
        </span>
      </div>
    </template>
  </BaseTimelineCard>
</template>

<style scoped>
.plan-summary {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.plan-chip {
  display: inline-flex;
  align-items: center;
  min-height: 28px;
  padding: 0 10px;
  border-radius: 999px;
  background: #edf6ff;
  color: #0f6cbd;
  font-size: 12px;
  font-weight: 600;
}
</style>
