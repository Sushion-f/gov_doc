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
  <BaseTimelineCard :event="event" icon="person_alert" tone="waiting">
    <template #summary>
      <div v-if="event?.payload?.promptMenu?.options?.length" class="waiting-options">
        <span
          v-for="option in event.payload.promptMenu.options"
          :key="`${event.id}-${option.key}`"
          class="waiting-chip"
        >
          {{ option.label }}
        </span>
      </div>
    </template>
  </BaseTimelineCard>
</template>

<style scoped>
.waiting-options {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.waiting-chip {
  display: inline-flex;
  align-items: center;
  min-height: 28px;
  padding: 0 10px;
  border-radius: 999px;
  background: #fff4dc;
  color: #a86a00;
  font-size: 12px;
  font-weight: 600;
}
</style>
