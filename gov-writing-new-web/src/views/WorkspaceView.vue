<script setup>
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import {
  createDocument,
  createFolder,
  deleteNode,
  downloadNode,
  loadWorkspace,
  moveNode,
  renameNode,
  sendNodeToConversation,
  state,
  uploadDocument,
} from "@/store";

const router = useRouter();
const openMenuId = ref("");

onMounted(() => {
  loadWorkspace();
});

async function handleCreateDocument() {
  const name = window.prompt("文档名称", "未命名文档");
  if (!name) {
    return;
  }
  const id = await createDocument(name);
  router.push({ name: "editor", params: { id } });
}

async function handleCreateFolder() {
  const name = window.prompt("文件夹名称", "新建文件夹");
  if (!name) {
    return;
  }
  await createFolder(name);
}

async function handleRename(item) {
  const name = window.prompt("请输入新名称", item.name);
  if (!name) {
    return;
  }
  await renameNode(item.id, name);
  openMenuId.value = "";
}

async function handleMove(item) {
  const parentId = window.prompt("请输入目标文件夹 ID，留空移动到根目录", item.parentId || "");
  await moveNode(item.id, parentId || null);
  openMenuId.value = "";
}

async function handleUpload(event) {
  const file = event.target.files?.[0];
  if (!file) {
    return;
  }
  await uploadDocument(file);
  event.target.value = "";
}

async function handleSendToConversation(item) {
  const result = await sendNodeToConversation(item.id);
  openMenuId.value = "";
  router.push({ name: "home" });
  window.setTimeout(() => {
    window.location.hash = "";
  }, 0);
  return result;
}

function toggleMenu(id) {
  openMenuId.value = openMenuId.value === id ? "" : id;
}

function iconClass(type) {
  return type === "folder" ? "folder" : "doc";
}

function iconName(type) {
  return type === "folder" ? "folder" : "description";
}

async function handleDelete(item) {
  await deleteNode(item.id);
  openMenuId.value = "";
}
</script>

<template>
  <section class="workspace-page">
    <div class="workspace-header">
      <span class="workspace-title">工作目录</span>

      <div class="header-actions">
        <div class="dropdown-wrapper">
          <button class="btn-primary-sm" @click="handleCreateDocument">
            <span class="material-symbols-rounded" style="font-size: 16px">add</span>
            新建
          </button>
        </div>

        <button class="btn-secondary" @click="handleCreateFolder">
          <span class="material-symbols-rounded" style="font-size: 16px">create_new_folder</span>
          文件夹
        </button>

        <label class="btn-secondary workspace-upload">
          <span class="material-symbols-rounded" style="font-size: 16px">upload</span>
          上传
          <input type="file" hidden @change="handleUpload" />
        </label>
      </div>

      <div class="storage-ring">
        <svg width="64" height="64" viewBox="0 0 64 64">
          <circle class="ring-bg" cx="32" cy="32" r="26" />
          <circle class="ring-fill" cx="32" cy="32" r="26" />
        </svg>
        <div class="ring-label">
          <span class="ring-value">589</span>
          <span class="ring-unit">MB 剩余</span>
        </div>
      </div>
    </div>

    <div class="main-tabs">
      <button class="main-tab" :class="{ active: state.workspaceView === 'recent' }" @click="loadWorkspace('recent')">
        最近
      </button>
      <button class="main-tab" :class="{ active: state.workspaceView === 'mine' }" @click="loadWorkspace('mine')">
        我的
      </button>
      <button class="main-tab" :class="{ active: state.workspaceView === 'ai' }" @click="loadWorkspace('ai')">
        AI文档
      </button>
    </div>

    <div class="file-list-header">
      <span class="file-all-link">全部文件 ›</span>
      <button class="btn-secondary workspace-filter">
        <span class="material-symbols-rounded" style="font-size: 15px">filter_list</span>
        筛选
      </button>
    </div>

    <table class="file-table">
      <thead>
        <tr>
          <th>名称</th>
          <th>所有者</th>
          <th>最近打开</th>
          <th class="col-action"></th>
        </tr>
      </thead>
      <tbody>
        <tr v-if="!state.workspaceItems.length" class="file-row empty-row">
          <td colspan="4">
            <div class="workspace-empty">当前视图暂无文件，先新建文档或上传文件。</div>
          </td>
        </tr>
        <tr v-for="item in state.workspaceItems" :key="item.id" class="file-row">
          <td @click="item.type === 'doc' ? router.push({ name: 'editor', params: { id: item.id } }) : null">
            <div class="file-name-cell">
              <span class="file-icon" :class="iconClass(item.type)">
                <span class="material-symbols-rounded">{{ iconName(item.type) }}</span>
              </span>
              <span>{{ item.name }}</span>
            </div>
          </td>
          <td class="file-owner">{{ item.owner || "-" }}</td>
          <td class="file-date">{{ item.date || "-" }}</td>
          <td class="action-cell">
            <div class="dropdown-anchor">
              <button class="btn-more" @click="toggleMenu(item.id)">
                <span class="material-symbols-rounded">more_horiz</span>
              </button>
              <div class="floating-menu workspace-row-menu" v-if="openMenuId === item.id">
                <button
                  v-if="item.canSendToConversation"
                  class="floating-menu-item"
                  @click="handleSendToConversation(item)"
                >
                  移至对话
                </button>
                <button v-if="item.canMove" class="floating-menu-item" @click="handleMove(item)">移动</button>
                <button v-if="item.canDownload" class="floating-menu-item" @click="downloadNode(item.id)">下载</button>
                <button v-if="item.canRename" class="floating-menu-item" @click="handleRename(item)">重命名</button>
                <button v-if="item.canDelete" class="floating-menu-item danger" @click="handleDelete(item)">删除</button>
              </div>
            </div>
          </td>
        </tr>
      </tbody>
    </table>
  </section>
</template>
