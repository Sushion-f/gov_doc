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
  <BaseTimelineCard
    :event="event"
    icon="help"
    tone="tool"
    title="未知事件"
    :subtitle="event?.detail || event?.eventType || '未识别的事件类型'"
  />
</template>
