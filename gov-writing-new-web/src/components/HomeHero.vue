<script setup>
defineProps({
  showFirstLoginPrompts: {
    type: Boolean,
    default: false,
  },
  showReturningPrompts: {
    type: Boolean,
    default: true,
  },
  firstLoginPrompts: {
    type: Array,
    default: () => [],
  },
  secondLoginPrompts: {
    type: Array,
    default: () => [],
  },
});

const emit = defineEmits(["select"]);
</script>

<template>
  <div class="empty-state">
    <h1>有什么我能帮你的吗</h1>

    <section class="recommend-card">
      <div class="recommend-header">
        <div>
          <h2>推荐问题</h2>
        </div>
      </div>

      <div class="recommend-groups">
        <div class="recommend-group">
          <div class="recommend-group-label" />
          <div class="chip-row" v-if="showFirstLoginPrompts">
            <button
              v-for="item in firstLoginPrompts"
              :key="item"
              class="question-chip"
              type="button"
              @click="emit('select', item)"
            >
              {{ item }}
            </button>
          </div>
        </div>

        <div class="recommend-group">
          <div class="recommend-group-label" />
          <div class="chip-row" v-if="showReturningPrompts">
            <button
              v-for="item in secondLoginPrompts"
              :key="item"
              class="question-chip"
              type="button"
              @click="emit('select', item)"
            >
              {{ item }}
            </button>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>
