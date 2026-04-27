<template>
  <div class="decision-bar">
    <div class="decision-card">
      <div class="decision-head">
        <span class="decision-title">{{ prompt }}</span>
        <button class="close-btn" type="button" @click="$emit('close')">×</button>
      </div>
      <p v-if="description" class="decision-desc">{{ description }}</p>
      <div class="decision-actions">
        <button
          v-for="opt in options"
          :key="opt.id"
          type="button"
          class="action-btn"
          :class="opt.variant || 'default'"
          @click="$emit('action', opt)"
        >
          {{ opt.label }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  prompt: string;
  description?: string;
  options: Array<{
    id: string;
    label: string;
    variant?: 'default' | 'primary' | 'ghost';
    sendText?: string;
  }>;
}>();

defineEmits<{
  action: [
    option: {
      id: string;
      label: string;
      variant?: 'default' | 'primary' | 'ghost';
      sendText?: string;
    }
  ];
  close: [];
}>();
</script>

<style scoped lang="scss">
.decision-bar {
  width: 100%;
  max-width: 760px;
  position: absolute;
  bottom: 0;
  left: 50%;
  transform: translateX(-50%);
  padding: 18px 0;
  z-index: 1000;
}

.decision-card {
  border: 1px solid #e4e8ee;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.96);
  backdrop-filter: blur(10px);
  padding: 14px 16px;
  box-shadow: 0 8px 20px rgba(15, 23, 42, 0.08);
}

.decision-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}

.decision-title {
  font-size: 15px;
  font-weight: 600;
  color: #1f1f1f;
}

.close-btn {
  border: none;
  background: transparent;
  color: #8b96a5;
  font-size: 18px;
  cursor: pointer;
  line-height: 1;
}

.decision-desc {
  margin: 6px 0 20px;
  font-size: 12px;
  color: #6b7280;
}

.decision-actions {
  display: flex;
  gap: 8px;
}

.action-btn {
  height: 34px;
  border-radius: 17px;
  border: 1px solid #dce3ea;
  padding: 0 14px;
  font-size: 13px;
  cursor: pointer;
  background: #fff;
  color: #374151;

  &.primary {
    border-color: #1d4ed8;
    background: #1d4ed8;
    color: #fff;
  }

  &.ghost {
    background: #f8fafc;
  }
}
</style>
