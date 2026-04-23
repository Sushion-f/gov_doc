<template>
  <aside ref="sidebarRootRef" class="sidebar">
    <div class="sidebar-brand">
      <span class="brand-name">智慧公文智能体</span>
    </div>

    <div class="sidebar-top-actions">
      <button class="btn-new-chat" @click="handleNewChat">
        <el-icon>
          <EditPen />
        </el-icon>
        新对话
      </button>
      <button class="btn-cloud-disk" @click="handleCloudDisk">
        <el-icon>
          <Cloudy />
        </el-icon>
        云盘
      </button>
    </div>

    <nav class="sidebar-nav">
      <div class="nav-section-header">
        <span class="nav-section-title">历史对话</span>
      </div>
      <div v-if="loading" class="nav-loading">
        <el-icon class="is-loading"><Loading /></el-icon>
        <span>加载中...</span>
      </div>
      <template v-else>
        <div
          v-for="item in historyItems"
          :key="item.id"
          class="nav-sub-item"
          :class="{ 'menu-open': openMenuId === item.id, active: currentSessionId === item.id }"
          @click="handleSelectSession(item.id)"
        >
          <el-icon class="history-icon"><ChatDotRound /></el-icon>
          <div class="history-content">
            <span class="history-title">{{ item.title }}</span>
          </div>
          <el-icon v-if="item.pinned" class="history-pin"><Top /></el-icon>
          <button class="nav-sub-item-more" @click.stop="toggleMenu(item.id, $event)">···</button>
          <div v-if="openMenuId === item.id" class="nav-more-dropdown">
            <button @click="handleRename(item)" v-if="!item.isNew">重命名</button>
            <button @click="handlePin(item)">
              {{ item.pinned ? '取消置顶' : '置顶' }}
            </button>
            <button class="danger" @click="handleDelete(item)" v-if="!item.isNew">删除</button>
          </div>
        </div>
      </template>
    </nav>

    <div class="sidebar-footer">
      <button class="btn-switch-version" @click="handleSwitchVersion">
        <el-icon><Switch /></el-icon>
        <span>切换至旧版本</span>
      </button>
      <div class="user-info">
        <div class="user-avatar">{{ userStore.avatarChar }}</div>
        <div class="user-meta">
          <div class="user-name">{{ userStore.displayName }}</div>
          <div class="user-desc">常用模型 {{ userStore.defaultModelLabel }}</div>
        </div>
      </div>
    </div>

    <el-dialog
      v-model="renameDialogVisible"
      title="重命名对话"
      width="400px"
      :close-on-click-modal="false"
      append-to-body
    >
      <el-input v-model="renameTitle" placeholder="请输入新名称" maxlength="50" show-word-limit />
      <template #footer>
        <el-button type="default" @click="renameDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmRename" :loading="renameLoading">确定</el-button>
      </template>
    </el-dialog>
  </aside>
</template>

<script setup lang="ts">
import { deleteConversation, listConversations, updateConversation } from '@/api';
import { useUserStore } from '@/stores/user';
import { ChatDotRound, Cloudy, EditPen, Loading, Switch, Top } from '@element-plus/icons-vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import { onMounted, onUnmounted, ref, watch } from 'vue';

const userStore = useUserStore();

const props = defineProps({
  currentSessionId: {
    type: String,
    default: null,
  },
});

const emit = defineEmits([
  'new-chat',
  'select-session',
  'session-deleted',
  'open-cloud-disk',
  'switch-version',
]);

const handleCloudDisk = () => {
  emit('open-cloud-disk');
};

const handleSwitchVersion = () => {
  emit('switch-version');
};

const loading = ref(false);
const historyItems = ref<ChatSession[]>([]);
const openMenuId = ref<string | null>(null);
const renameDialogVisible = ref(false);
const renameTitle = ref('');
const renameItem = ref<ChatSession | null>(null);
const renameLoading = ref(false);
const sidebarRootRef = ref<HTMLElement | null>(null);
const suppressOutsideCloseOnce = ref(false);
const draftPrefix = 'local-';

const createLocalDraft = (): ChatSession => {
  const now = new Date().toISOString();
  return {
    id: `${draftPrefix}${Date.now()}`,
    title: '新对话',
    pinned: false,
    isNew: true,
    createdAt: now,
    updatedAt: now,
  };
};

const loadHistory = async () => {
  loading.value = true;
  try {
    const draftItems = historyItems.value.filter((item) => item.isNew);
    const list = (await listConversations()).map((item) => ({
      id: item.id,
      title: item.title,
      pinned: item.pinned,
      updatedAt: item.updatedAt,
      createdAt: item.updatedAt,
    }));
    list.sort((a, b) => {
      if (a.pinned && !b.pinned) return -1;
      if (!a.pinned && b.pinned) return 1;
      return 0;
    });
    historyItems.value = [...draftItems, ...list];
  } catch (error) {
    console.error('加载历史会话失败:', error);
    ElMessage.error('加载历史会话失败');
  } finally {
    loading.value = false;
  }
};

const handleNewChat = async () => {
  if (historyItems.value.some((v) => v.isNew)) {
    ElMessage.warning('已存在新会话');
    return;
  }
  const draft = createLocalDraft();
  historyItems.value.unshift(draft);
  emit('new-chat', draft);
};

const handleSelectSession = (sessionId: string) => {
  if (sessionId !== props.currentSessionId) {
    emit('select-session', sessionId);
  }
  openMenuId.value = null;
};

const toggleMenu = (id: string, event?: MouseEvent) => {
  if (event) event.stopPropagation();
  suppressOutsideCloseOnce.value = true;
  openMenuId.value = openMenuId.value === id ? null : id;
  requestAnimationFrame(() => {
    suppressOutsideCloseOnce.value = false;
  });
};

const closeMenu = () => {
  openMenuId.value = null;
};

const handleRename = (item: ChatSession) => {
  renameItem.value = item;
  renameTitle.value = item.title;
  renameDialogVisible.value = true;
  openMenuId.value = null;
};

const confirmRename = async () => {
  if (!renameTitle.value.trim()) {
    ElMessage.warning('请输入对话名称');
    return;
  }
  renameLoading.value = true;
  try {
    if (renameItem.value) {
      if (!renameItem.value.isNew) {
        await updateConversation(renameItem.value.id, { title: renameTitle.value.trim() });
      }
      const item = historyItems.value.find((i) => i.id === renameItem.value?.id);
      if (item) {
        item.title = renameTitle.value.trim();
      }
      renameDialogVisible.value = false;
      ElMessage.success('重命名成功');
    }
  } catch (error) {
    console.error('重命名失败:', error);
    ElMessage.error('重命名失败');
  } finally {
    renameLoading.value = false;
  }
};

const handlePin = async (item: ChatSession) => {
  if (item.isNew) {
    ElMessage.warning('新会话不支持置顶');
    return;
  }
  try {
    await updateConversation(item.id, { pinned: !item.pinned });
    item.pinned = !item.pinned;
    historyItems.value.sort((a, b) => {
      if (a.pinned && !b.pinned) return -1;
      if (!a.pinned && b.pinned) return 1;
      return 0;
    });
    ElMessage.success(item.pinned ? '已置顶' : '已取消置顶');
  } catch (error) {
    console.error('置顶操作失败:', error);
    ElMessage.error('操作失败');
  }
  openMenuId.value = null;
};

const handleDelete = async (item: ChatSession) => {
  try {
    await ElMessageBox.confirm('确定要删除这个对话吗？', '删除确认', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
    });
    if (!item.isNew) {
      await deleteConversation(item.id);
    }
    const index = historyItems.value.findIndex((i) => i.id === item.id);
    if (index > -1) {
      historyItems.value.splice(index, 1);
    }
    if (item.id === props.currentSessionId) {
      const draft = historyItems.value.find((v) => v.isNew);
      if (draft) {
        emit('new-chat', draft);
      } else {
        const created = createLocalDraft();
        historyItems.value.unshift(created);
        emit('new-chat', created);
      }
    } else {
      emit('session-deleted', item.id);
    }
    ElMessage.success('删除成功');
  } catch (error) {
    if (error !== 'cancel') {
      console.error('删除失败:', error);
      ElMessage.error('删除失败');
    }
  }
  openMenuId.value = null;
};

const addSession = (session: ChatSession) => {
  const exists = historyItems.value.find((i) => i.id === session.id);
  if (!exists) {
    historyItems.value.unshift(session);
  }
};

const replaceSessionId = (fromId: string, toId: string, title?: string) => {
  const item = historyItems.value.find((i) => i.id === fromId);
  if (!item) return;
  item.id = toId;
  item.isNew = false;
  if (title) item.title = title;
};

const updateSessionTitle = (sessionId: string, title: string) => {
  const item = historyItems.value.find((i) => i.id === sessionId);
  if (item && item.isNew) {
    item.title = title;
    item.isNew = false;
  }
};

watch(
  () => props.currentSessionId,
  (newId) => {
    if (newId) {
      const exists = historyItems.value.find((i) => i.id === newId);
      if (!exists) {
        loadHistory();
      }
    }
  }
);

const handleClickOutside = (event: MouseEvent) => {
  if (suppressOutsideCloseOnce.value) return;
  const root = sidebarRootRef.value;
  const target = event.target as Node | null;
  if (!root || !target) return;
  if (!root.contains(target)) openMenuId.value = null;
};

onMounted(() => {
  loadHistory();
  document.addEventListener('click', handleClickOutside);
});

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside);
});

defineExpose({
  addSession,
  replaceSessionId,
  updateSessionTitle,
  loadHistory,
});
</script>

<style scoped lang="scss">
.sidebar {
  width: 220px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  height: 100%;
  background: rgba(255, 255, 255, 0.72);
  backdrop-filter: blur(16px);
  border-right: 1px solid rgba(227, 227, 227, 0.85);
  z-index: 10;
}

.sidebar-brand {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 20px;
  height: 64px;
  flex-shrink: 0;
}

.brand-name {
  font-family: 'Space Grotesk', 'Noto Sans SC', sans-serif;
  font-size: 19px;
  font-weight: 700;
  color: #1f2937;
  letter-spacing: -0.01em;
}

.sidebar-top-actions {
  padding: 4px 12px 8px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.btn-new-chat,
.btn-cloud-disk {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  height: 42px;
  border-radius: 24px;
  font-size: 14px;
  cursor: pointer;
  width: 100%;
  font-family: inherit;
  transition:
    box-shadow 0.18s var(--ease-out),
    transform 0.18s var(--ease-out),
    background 0.18s var(--ease-out);

  .el-icon {
    font-size: 18px;
  }
}

.btn-new-chat {
  background: var(--primary-gradient);
  color: var(--on-primary);
  border: none;
  box-shadow: 0 4px 12px rgba(0, 47, 134, 0.24);

  &:hover {
    box-shadow: 0 4px 12px rgba(0, 47, 134, 0.3);
    transform: translateY(-1px);
  }

  &:active {
    background: var(--primary-pressed);
  }
}

.btn-cloud-disk {
  background: #fff;
  color: #1f2937;
  border: 1px solid var(--outline-variant, #e5e7eb);

  &:hover {
    background: #f9fafb;
    border-color: #d1d5db;
  }

  &:active {
    background: #f3f4f6;
  }

  .el-icon {
    color: var(--primary);
  }
}

.sidebar-nav {
  flex: 1;
  overflow-y: auto;
  padding: 4px 0;
}

.nav-section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 20px 6px;
}

.nav-section-title {
  font-size: 13px;
  font-weight: 500;
  color: #9ca3af;
  letter-spacing: 0.2px;
}

.nav-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 20px;
  color: var(--on-surface-variant);
  font-size: 13px;
}

.nav-sub-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  cursor: pointer;
  border-radius: 10px;
  margin: 2px 8px;
  color: var(--on-surface);
  font-size: 14px;
  font-weight: 400;
  transition: background 0.12s ease;
  position: relative;

  &:hover {
    background: var(--surface-overlay, rgba(0, 0, 0, 0.04));
  }

  &.active {
    background: rgba(0, 47, 134, 0.08);
    color: var(--primary);

    .history-icon {
      color: var(--primary);
    }
  }
}

.history-icon {
  font-size: 18px;
  color: #6b7280;
  flex-shrink: 0;
}

.history-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
  overflow: hidden;
}

.history-title {
  font-size: 14px;
  font-weight: 500;
  color: inherit;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.history-subtitle {
  font-size: 12px;
  color: #9ca3af;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.history-pin {
  font-size: 14px;
  color: #f59e0b;
  flex-shrink: 0;
}

.nav-sub-item-more {
  margin-left: auto;
  opacity: 0;
  width: 22px;
  height: 22px;
  border: none;
  background: none;
  border-radius: 4px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--on-surface-variant);
  font-size: 14px;
  font-weight: 700;
  letter-spacing: 1px;
  flex-shrink: 0;
  transition:
    opacity 0.12s,
    background 0.12s;

  &:hover {
    background: rgba(0, 0, 0, 0.06);
  }
}

.nav-sub-item:hover .nav-sub-item-more,
.nav-sub-item.menu-open .nav-sub-item-more {
  opacity: 1;
}

.nav-more-dropdown {
  position: absolute;
  right: 4px;
  top: 32px;
  z-index: 200;
  background: var(--surface);
  border: 1px solid var(--outline-variant);
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.12);
  min-width: 100px;
  overflow: hidden;
  opacity: 0;
  transform: translateY(-4px);
  transition:
    opacity 0.15s ease,
    transform 0.15s ease;
  pointer-events: none;
}

.nav-sub-item.menu-open .nav-more-dropdown {
  opacity: 1;
  transform: translateY(0);
  pointer-events: auto;
}

.nav-more-dropdown button {
  display: block;
  width: 100%;
  padding: 8px 14px;
  background: none;
  border: none;
  text-align: left;
  font-size: 13px;
  color: var(--on-surface);
  cursor: pointer;
  font-family: inherit;
  transition: background 0.1s;

  &:hover {
    background: var(--surface-variant);
  }

  &.danger {
    color: var(--error, #b3261e);
  }
}

.sidebar-footer {
  flex-shrink: 0;
  padding: 12px 12px 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  border-top: 1px solid var(--outline-variant, #e5e7eb);
  background: transparent;
}

.btn-switch-version {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  height: 40px;
  border-radius: 24px;
  background: #fff;
  color: #4b5563;
  border: 1px solid var(--outline-variant, #e5e7eb);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  width: 100%;
  font-family: inherit;
  transition:
    background 0.18s var(--ease-out),
    border-color 0.18s var(--ease-out);

  &:hover {
    background: #f9fafb;
    border-color: #d1d5db;
    color: #1f2937;
  }

  .el-icon {
    font-size: 16px;
    color: #6b7280;
  }
}

.user-info {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 4px 6px;
}

.user-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: var(--primary-gradient, var(--primary));
  color: var(--on-primary, #fff);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 15px;
  flex-shrink: 0;
  font-family: 'Noto Sans SC', sans-serif;
}

.user-meta {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
  overflow: hidden;
}

.user-name {
  font-size: 14px;
  color: #1f2937;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.user-desc {
  font-size: 12px;
  color: #9ca3af;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.el-icon {
  font-size: 20px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  user-select: none;
}
</style>
