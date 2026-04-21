<template>
  <div class="datasource-menu" :class="{ visible: visible }">
    <span class="dsm-label">{{ label }}</span>
    <button class="dsm-option" @click="handleSelect('auto')">
      <el-icon><Search /></el-icon>
      请自动寻找
    </button>
    <button class="dsm-option" @click="handleSelect('upload')">
      <el-icon><Upload /></el-icon>
      我来选择，点击上传
    </button>
    <button class="dsm-option" @click="handleSelect('manual')">
      <el-icon><Edit /></el-icon>
      都不是，我来补充
    </button>
  </div>
</template>

<script setup lang="ts">
import { Edit, Search, Upload } from '@element-plus/icons-vue';

const props = defineProps({
  visible: {
    type: Boolean,
    default: false,
  },
  label: {
    type: String,
    default: '请提供周报数据来源，或选择其他方式：',
  },
});

const emit = defineEmits<{
  select: [option: string];
}>();

const handleSelect = (option: string) => {
  emit('select', option);
};
</script>

<style scoped lang="scss">
.datasource-menu {
  display: none;
  flex-direction: column;
  gap: 10px;
  padding: 16px;
  animation: fadeIn 0.2s ease;

  &.visible {
    display: flex;
  }
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(-8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.dsm-label {
  font-size: 13px;
  color: var(--on-surface-variant);
  text-align: center;
  margin-bottom: 4px;
}

.dsm-option {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 16px;
  background: rgba(0, 0, 0, 0.02);
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 10px;
  font-size: 14px;
  font-weight: 500;
  color: var(--on-surface);
  cursor: pointer;
  font-family: inherit;
  text-align: left;
  transition: all 0.15s ease;

  &:hover {
    background: rgba(0, 47, 134, 0.06);
    border-color: rgba(0, 47, 134, 0.2);
    color: var(--primary);
    transform: translateY(-1px);
    box-shadow: 0 2px 8px rgba(0, 47, 134, 0.1);
  }

  &:active {
    transform: translateY(0);
  }

  .el-icon {
    font-size: 20px;
    color: var(--primary);
  }
}
</style>
