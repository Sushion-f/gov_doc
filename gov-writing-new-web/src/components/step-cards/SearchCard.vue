<script setup>
import { computed } from "vue";
import BaseTimelineCard from "@/components/step-cards/BaseTimelineCard.vue";

const props = defineProps({
  event: {
    type: Object,
    required: true,
  },
});

const citations = computed(
  () =>
    props.event?.payload?.citations ||
    props.event?.payload?.normalizedResult?.citations ||
    props.event?.payload?.normalizedResult?.items ||
    []
);
</script>

<template>
  <BaseTimelineCard :event="event" icon="search" tone="search">
    <div v-if="citations.length" class="search-list">
      <article
        v-for="(citation, index) in citations"
        :key="`${event.id}-${index}`"
        class="search-item"
      >
        <strong>{{ index + 1 }} · {{ citation.title || citation.name || "检索结果" }}</strong>
        <p>{{ citation.description || citation.summary || citation.snippet || "无摘要" }}</p>
        <span class="search-source">{{ citation.source || citation.badge || "来源" }}</span>
      </article>
    </div>
  </BaseTimelineCard>
</template>

<style scoped>
.search-list {
  display: grid;
  gap: 10px;
}

.search-item {
  border-radius: 16px;
  background: #f8fafc;
  padding: 14px 16px;
}

.search-item strong {
  display: block;
  color: #172030;
  font-size: 14px;
}

.search-item p {
  margin: 8px 0;
  color: #58667d;
  font-size: 13px;
  line-height: 1.6;
}

.search-source {
  display: inline-flex;
  align-items: center;
  min-height: 24px;
  padding: 0 8px;
  border-radius: 999px;
  background: #eef2ff;
  color: #4f46e5;
  font-size: 12px;
  font-weight: 600;
}
</style>
