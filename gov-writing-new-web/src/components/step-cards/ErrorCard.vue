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
  <BaseTimelineCard :event="event" icon="error" tone="error" />
</template>
