<template>
  <div class="heartbeat-task-output" :class="{ 'stream-hidden': !visible, 'stream-visible': visible }">
    <div class="assistant-text-bubble">
      {{ task.summary }}
    </div>

    <div class="hb-table-container">
      <table class="hb-table">
        <thead>
          <tr>
            <th>序号</th>
            <th>一级热点</th>
            <th>二级热点</th>
            <th>三级热点</th>
            <th>四级热点</th>
            <th>说明</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(item, index) in task.items" :key="index">
            <td>{{ index + 1 }}</td>
            <td>
              <select v-model="item.level1">
                <option value="">请选择</option>
                <option>治安</option>
                <option>交通</option>
                <option>民事</option>
              </select>
            </td>
            <td>
              <select v-model="item.level2">
                <option value="">请选择</option>
                <option>违规行为</option>
                <option>纠纷</option>
                <option>事故</option>
              </select>
            </td>
            <td>
              <select v-model="item.level3">
                <option value="">请选择</option>
                <option>占道</option>
                <option>停车</option>
                <option>噪音</option>
              </select>
            </td>
            <td>
              <span class="hb-editable" :class="{ 'has-content': item.level4 }" contenteditable="true" @blur="updateItem(index, 'level4', $event)">{{ item.level4 }}</span>
            </td>
            <td>
              <span class="hb-editable" :class="{ 'has-content': item.description }" contenteditable="true" @blur="updateItem(index, 'description', $event)">{{ item.description }}</span>
            </td>
            <td>
              <button class="hb-delete-btn" @click="deleteItem(index)" title="删除">×</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="hb-table-actions">
      <button class="btn-hb-save" @click="handleSave">
        <el-icon><Check /></el-icon>
        保存
      </button>
      <button class="btn-hb-cancel" @click="handleCancel">取消</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { HeartbeatTask, HeartbeatTaskItem } from '@/types';
import { Check } from '@element-plus/icons-vue';

type TaskItem = HeartbeatTaskItem;

const props = defineProps({
  task: {
    type: Object as () => HeartbeatTask,
    default: () => ({
      summary: '',
      items: [],
    }),
  },
  visible: {
    type: Boolean,
    default: false,
  },
});

const emit = defineEmits<{
  save: [task: HeartbeatTask];
  cancel: [];
  update: [{ index?: number; field?: string; value?: string; items?: TaskItem[] }];
}>();

const updateItem = (index: number, field: string, event: Event) => {
  emit('update', {
    index,
    field,
    value: (event.target as HTMLElement).textContent,
  });
};

const deleteItem = (index: number) => {
  const newItems = [...props.task.items];
  newItems.splice(index, 1);
  emit('update', { items: newItems });
};

const handleSave = () => {
  emit('save', props.task);
};

const handleCancel = () => {
  emit('cancel');
};
</script>

<style scoped lang="scss">
.heartbeat-task-output {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-top: 8px;

  &.stream-hidden {
    display: none;
  }

  &.stream-visible {
    display: flex;
    animation: fadeIn 0.3s ease;
  }
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.assistant-text-bubble {
  max-width: 88%;
  padding: 12px 16px;
  background: rgba(0, 0, 0, 0.03);
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 12px;
  font-size: 14px;
  line-height: 1.6;
  color: var(--on-surface);
}

.hb-table-container {
  border-radius: 8px;
  border: 1px solid rgba(0, 0, 0, 0.1);
  overflow: hidden;
  background: #fff;
}

.hb-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;

  thead {
    background: rgba(0, 47, 134, 0.05);
  }

  th {
    padding: 10px 8px;
    text-align: center;
    font-weight: 600;
    color: var(--primary);
    border-bottom: 1px solid rgba(0, 0, 0, 0.1);
    font-size: 12px;
  }

  td {
    padding: 8px;
    border-bottom: 1px solid rgba(0, 0, 0, 0.06);
    text-align: center;

    &:last-child {
      border-bottom: none;
    }
  }

  tbody tr {
    &:hover {
      background: rgba(0, 0, 0, 0.02);
    }
  }

  select {
    padding: 4px 8px;
    border: 1px solid rgba(0, 0, 0, 0.15);
    border-radius: 4px;
    font-size: 12px;
    color: var(--on-surface);
    background: #fff;
    cursor: pointer;
    min-width: 80px;

    &:focus {
      outline: none;
      border-color: var(--primary);
    }
  }

  .hb-editable {
    display: inline-block;
    min-width: 60px;
    padding: 4px 6px;
    border: 1px dashed rgba(0, 0, 0, 0.2);
    border-radius: 4px;
    cursor: text;
    transition: all 0.15s ease;

    &:focus {
      outline: none;
      border-color: var(--primary);
      background: rgba(0, 47, 134, 0.02);
    }

    &.has-content {
      border-style: solid;
      border-color: rgba(0, 0, 0, 0.15);
    }

    &:empty::before {
      content: '点击编辑';
      color: var(--on-surface-variant);
      opacity: 0.6;
    }
  }

  .hb-delete-btn {
    width: 24px;
    height: 24px;
    border: none;
    background: rgba(220, 38, 38, 0.1);
    color: #dc2626;
    border-radius: 4px;
    cursor: pointer;
    font-size: 16px;
    line-height: 1;
    transition: all 0.15s ease;

    &:hover {
      background: rgba(220, 38, 38, 0.2);
    }
  }
}

.hb-table-actions {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
  margin-top: 4px;
}

.btn-hb-save {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  background: var(--primary-gradient);
  color: var(--on-primary);
  border: none;
  border-radius: 20px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  font-family: inherit;
  box-shadow: 0 2px 8px rgba(0, 47, 134, 0.2);
  transition: all 0.15s ease;

  &:hover {
    box-shadow: 0 2px 12px rgba(0, 47, 134, 0.3);
    transform: translateY(-1px);
  }

  .el-icon {
    font-size: 15px;
  }
}

.btn-hb-cancel {
  padding: 8px 16px;
  background: rgba(0, 0, 0, 0.04);
  color: var(--on-surface-variant);
  border: 1px solid rgba(0, 0, 0, 0.1);
  border-radius: 20px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  font-family: inherit;
  transition: all 0.15s ease;

  &:hover {
    background: rgba(0, 0, 0, 0.06);
    border-color: rgba(0, 0, 0, 0.15);
  }
}
</style>
