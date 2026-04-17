<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { loadWorkspace, state } from "@/store";

const props = defineProps({
  open: {
    type: Boolean,
    default: false,
  },
});

const emit = defineEmits(["update:open", "confirm", "cancel"]);

const searchQuery = ref("");
const selectedIds = ref([]);

onMounted(() => {
  if (props.open) {
    loadWorkspace(state.workspaceView || "recent");
  }
});

watch(
  () => props.open,
  (isOpen) => {
    if (isOpen) {
      selectedIds.value = [];
      searchQuery.value = "";
      loadWorkspace(state.workspaceView || "recent");
    }
  }
);

const selectableItems = computed(() =>
  (state.workspaceItems || []).filter((item) => item.type === "doc" && item.canSendToConversation !== false)
);

const filteredItems = computed(() => {
  const q = searchQuery.value.trim().toLowerCase();
  if (!q) {
    return selectableItems.value;
  }
  return selectableItems.value.filter((item) => (item.name || "").toLowerCase().includes(q));
});

function toggleRow(id) {
  const cur = selectedIds.value;
  const idx = cur.indexOf(id);
  if (idx >= 0) {
    selectedIds.value = cur.filter((x) => x !== id);
  } else {
    selectedIds.value = [...cur, id];
  }
}

function isSelected(id) {
  return selectedIds.value.includes(id);
}

function onCancel() {
  emit("update:open", false);
  emit("cancel");
}

function onConfirm() {
  const idSet = new Set(selectedIds.value);
  const chosen = selectableItems.value.filter((item) => idSet.has(item.id));
  emit("confirm", chosen);
  emit("update:open", false);
}

function iconClass(type) {
  return type === "folder" ? "folder" : "doc";
}

function iconName(type) {
  return type === "folder" ? "folder" : "description";
}
</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="cloud-picker-overlay" @click.self="onCancel">
      <div class="cloud-picker-modal" role="dialog" aria-modal="true" aria-labelledby="cloud-picker-title">
        <header class="cloud-picker-header">
          <h2 id="cloud-picker-title">从云盘添加</h2>
          <button type="button" class="cloud-picker-close" aria-label="关闭" @click="onCancel">
            <span class="material-symbols-rounded">close</span>
          </button>
        </header>

        <div class="cloud-picker-search">
          <span class="material-symbols-rounded search-icon">search</span>
          <input v-model="searchQuery" type="search" placeholder="搜索文件" autocomplete="off" />
        </div>

        <div class="cloud-picker-table-wrap">
          <table class="cloud-picker-table">
            <thead>
              <tr>
                <th class="col-check" />
                <th>全部文件</th>
                <th class="col-date">修改时间</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="!filteredItems.length" class="empty-row">
                <td colspan="3">
                  <div class="cloud-picker-empty">暂无可用文档，请先在「云盘」页上传或新建。</div>
                </td>
              </tr>
              <tr
                v-for="item in filteredItems"
                :key="item.id"
                class="data-row"
                :class="{ selected: isSelected(item.id) }"
                @click="toggleRow(item.id)"
              >
                <td class="col-check" @click.stop>
                  <label class="checkbox-wrap">
                    <input type="checkbox" :checked="isSelected(item.id)" @change="toggleRow(item.id)" />
                    <span class="checkbox-ui" />
                  </label>
                </td>
                <td>
                  <div class="file-name-cell">
                    <span class="file-icon" :class="iconClass(item.type)">
                      <span class="material-symbols-rounded">{{ iconName(item.type) }}</span>
                    </span>
                    <span class="file-name">{{ item.name }}</span>
                  </div>
                </td>
                <td class="col-date">{{ item.date || "—" }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <footer class="cloud-picker-footer">
          <div class="selection-summary">
            <span class="material-symbols-rounded">cloud</span>
            已选 {{ selectedIds.length }} 个文件
          </div>
          <div class="footer-actions">
            <button type="button" class="btn-ghost" @click="onCancel">取消</button>
            <button type="button" class="btn-primary" :disabled="!selectedIds.length" @click="onConfirm">
              确认添加({{ selectedIds.length }})
            </button>
          </div>
        </footer>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.cloud-picker-overlay {
  position: fixed;
  inset: 0;
  z-index: 1200;
  background: rgba(31, 31, 31, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
}

.cloud-picker-modal {
  width: min(640px, 100%);
  max-height: min(84vh, 720px);
  background: var(--white);
  border-radius: var(--radius-lg);
  box-shadow: var(--surface-shadow);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.cloud-picker-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid var(--outline);
}

.cloud-picker-header h2 {
  margin: 0;
  font-size: var(--text-lg);
  font-weight: 600;
  color: var(--grey-900);
}

.cloud-picker-close {
  width: 36px;
  height: 36px;
  border-radius: var(--radius-full);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--grey-600);
}

.cloud-picker-close:hover {
  background: var(--grey-200);
}

.cloud-picker-search {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 12px 20px;
  padding: 10px 14px;
  border: 1px solid var(--outline);
  border-radius: var(--radius-md);
  background: var(--grey-100);
}

.cloud-picker-search input {
  flex: 1;
  border: none;
  background: transparent;
  outline: none;
  font-size: var(--text-base);
}

.search-icon {
  color: var(--grey-500);
  font-size: 22px;
}

.cloud-picker-table-wrap {
  flex: 1;
  min-height: 200px;
  overflow: auto;
  padding: 0 12px 8px;
}

.cloud-picker-table {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--text-sm);
}

.cloud-picker-table th {
  text-align: left;
  padding: 8px 10px;
  color: var(--grey-600);
  font-weight: 500;
  border-bottom: 1px solid var(--outline);
}

.cloud-picker-table .col-check {
  width: 44px;
}

.cloud-picker-table .col-date {
  width: 140px;
  text-align: right;
}

.data-row {
  cursor: pointer;
  border-bottom: 1px solid var(--grey-200);
}

.data-row:hover {
  background: var(--grey-100);
}

.data-row.selected {
  background: rgba(11, 87, 208, 0.06);
}

.cloud-picker-table td {
  padding: 10px;
  vertical-align: middle;
}

.file-name-cell {
  display: flex;
  align-items: center;
  gap: 10px;
}

.file-icon {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.file-icon.doc {
  background: var(--primary-50);
  color: var(--primary-600);
}

.file-icon.folder {
  background: var(--amber-50);
  color: var(--amber-500);
}

.file-name {
  color: var(--grey-900);
  word-break: break-all;
}

.col-date {
  text-align: right;
  color: var(--grey-600);
}

.checkbox-wrap {
  display: inline-flex;
  align-items: center;
  cursor: pointer;
}

.checkbox-wrap input {
  position: absolute;
  opacity: 0;
  width: 0;
  height: 0;
}

.checkbox-ui {
  width: 18px;
  height: 18px;
  border: 2px solid var(--grey-400);
  border-radius: 50%;
  display: inline-block;
  position: relative;
}

.data-row.selected .checkbox-ui {
  border-color: var(--primary-600);
  background: var(--primary-600);
}

.data-row.selected .checkbox-ui::after {
  content: "";
  position: absolute;
  left: 4px;
  top: 1px;
  width: 5px;
  height: 10px;
  border: solid white;
  border-width: 0 2px 2px 0;
  transform: rotate(45deg);
}

.cloud-picker-empty {
  text-align: center;
  padding: 32px 16px;
  color: var(--grey-500);
}

.cloud-picker-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 20px;
  border-top: 1px solid var(--outline);
  background: var(--white);
}

.selection-summary {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: var(--text-sm);
  color: var(--grey-700);
}

.selection-summary .material-symbols-rounded {
  color: var(--primary-600);
  font-size: 20px;
}

.footer-actions {
  display: flex;
  gap: 10px;
}

.btn-ghost {
  padding: 8px 16px;
  border-radius: var(--radius-full);
  border: 1px solid var(--outline);
  background: var(--white);
  color: var(--grey-800);
  font-size: var(--text-sm);
}

.btn-ghost:hover {
  background: var(--grey-100);
}

.btn-primary {
  padding: 8px 18px;
  border-radius: var(--radius-full);
  background: var(--primary-600);
  color: var(--white);
  font-size: var(--text-sm);
  font-weight: 500;
}

.btn-primary:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.btn-primary:not(:disabled):hover {
  background: var(--primary-700);
}
</style>
