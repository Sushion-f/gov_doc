<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  createConversation,
  deleteConversation,
  renameConversation,
  selectConversation,
  state,
} from "@/store";

const router = useRouter();
const route = useRoute();

const openHistoryMenuId = ref("");
const userMenuOpen = ref(false);

const initials = computed(() => {
  if (!state.user?.name) {
    return "GW";
  }
  return state.user.name.slice(0, 1);
});

async function handleNewConversation() {
  const id = await createConversation();
  userMenuOpen.value = false;
  openHistoryMenuId.value = "";
  router.push({ name: "home" });
  await selectConversation(id);
}

async function openConversation(id) {
  openHistoryMenuId.value = "";
  await selectConversation(id);
  router.push({ name: "home" });
}

async function togglePin(item) {
  await renameConversation(item.id, { pinned: !item.pinned });
  openHistoryMenuId.value = "";
}

async function renameItem(item) {
  const title = window.prompt("请输入新会话名称", item.title);
  if (!title) {
    return;
  }
  await renameConversation(item.id, { title });
  openHistoryMenuId.value = "";
}

async function removeItem(id) {
  await deleteConversation(id);
  openHistoryMenuId.value = "";
}

function toggleHistoryMenu(id) {
  openHistoryMenuId.value = openHistoryMenuId.value === id ? "" : id;
}

function goWorkspace() {
  userMenuOpen.value = false;
  router.push({ name: "workspace" });
}

function goHome() {
  openHistoryMenuId.value = "";
  userMenuOpen.value = false;
  router.push({ name: "home" });
}

function goSettings() {
  openHistoryMenuId.value = "";
  userMenuOpen.value = false;
  router.push({ name: "settings" });
}

function switchToLegacy() {
  if (state.user?.legacy_system_url) {
    window.location.href = state.user.legacy_system_url;
  }
}

function toggleUserMenu() {
  userMenuOpen.value = !userMenuOpen.value;
}

function handleLogout() {
  openHistoryMenuId.value = "";
  userMenuOpen.value = false;
  if (state.user?.logout_url) {
    window.location.href = state.user.logout_url;
    return;
  }
  state.currentConversationId = null;
  state.currentConversation = null;
  state.currentEvents = [];
  state.activeQuickSkill = "";
  state.errorMessage = "已退出当前会话。";
  router.push({ name: "home" });
}

function closeFloatingMenus() {
  openHistoryMenuId.value = "";
  userMenuOpen.value = false;
}

onMounted(() => {
  document.addEventListener("click", closeFloatingMenus);
});

onBeforeUnmount(() => {
  document.removeEventListener("click", closeFloatingMenus);
});
</script>

<template>
  <aside class="sidebar">
    <div class="brand-block">
      <div class="brand-row">
        <div class="brand-copy">
          <div class="brand-title">智慧公文智能体</div>
        </div>
        <button class="sidebar-toggle" @click.stop="state.sidebarCollapsed = !state.sidebarCollapsed">
          <span class="material-symbols-rounded">
            {{ state.sidebarCollapsed ? "right_panel_open" : "left_panel_close" }}
          </span>
        </button>
      </div>
    </div>

    <div class="sidebar-actions">
      <button class="sidebar-button primary" @click.stop="handleNewConversation">
        <span class="material-symbols-rounded">edit_square</span>
        <span class="sidebar-label">新对话</span>
      </button>
      <button
        class="sidebar-button secondary"
        :class="{ active: route.name === 'home' }"
        @click.stop="goHome"
      >
        <span class="material-symbols-rounded">home</span>
        <span class="sidebar-label">首页</span>
      </button>
      <button
        class="sidebar-button secondary"
        :class="{ active: route.name === 'workspace' }"
        @click.stop="goWorkspace"
      >
        <span class="material-symbols-rounded">cloud</span>
        <span class="sidebar-label">云盘</span>
      </button>
    </div>

    <div class="section-label">历史对话</div>

    <div class="history-list">
      <div
        v-for="item in state.conversations"
        :key="item.id"
        class="history-item"
        :class="{ active: item.id === state.currentConversationId, pinned: item.pinned }"
      >
        <button class="history-main" @click.stop="openConversation(item.id)">
          <span class="material-symbols-rounded">chat</span>
          <span class="history-item-body">
            <span class="history-item-title">{{ item.title }}</span>
            <span class="history-item-meta">
              <span class="history-item-pin material-symbols-rounded">keep</span>
              {{ item.meta || "刚刚更新" }}
            </span>
          </span>
        </button>

        <button class="history-actions-trigger" @click.stop="toggleHistoryMenu(item.id)">
          <span class="material-symbols-rounded">more_horiz</span>
        </button>

        <div class="history-menu" :class="{ open: openHistoryMenuId === item.id }">
          <button @click.stop="togglePin(item)">
            <span class="material-symbols-rounded">{{ item.pinned ? "keep_off" : "keep" }}</span>
            {{ item.pinned ? "取消置顶" : "置顶" }}
          </button>
          <button @click.stop="renameItem(item)">
            <span class="material-symbols-rounded">edit</span>
            重命名
          </button>
          <button class="danger" @click.stop="removeItem(item.id)">
            <span class="material-symbols-rounded">delete</span>
            删除
          </button>
        </div>
      </div>
    </div>

    <div class="sidebar-footer">
      <button class="version-button" @click.stop="switchToLegacy">
        <span class="material-symbols-rounded">compare_arrows</span>
        切换至旧版本
      </button>

      <div class="user-card" @click.stop="toggleUserMenu">
        <div class="user-avatar">{{ initials }}</div>
        <div class="user-info">
          <strong>{{ state.user?.name || "未登录" }}</strong>
        </div>

        <div class="user-popup" :class="{ open: userMenuOpen }" @click.stop>
          <button class="user-popup-item" @click.stop="goSettings">
            <span class="material-symbols-rounded">settings</span>
            设置
          </button>
          <button class="user-popup-item logout-item" @click.stop="handleLogout">
            <span class="material-symbols-rounded">logout</span>
            退出登录
          </button>
        </div>
      </div>
    </div>
  </aside>
</template>
