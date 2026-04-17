<script setup>
import { computed, ref } from "vue";
import PromptMenu from "@/components/PromptMenu.vue";

const props = defineProps({
  prompt: {
    type: String,
    default: "",
  },
  promptMenu: {
    type: Object,
    default: null,
  },
  loading: {
    type: Boolean,
    default: false,
  },
  modelOptions: {
    type: Array,
    default: () => [],
  },
  currentModel: {
    type: String,
    default: "",
  },
  uploadedAttachments: {
    type: Array,
    default: () => [],
  },
  activeQuickSkill: {
    type: String,
    default: "",
  },
  skills: {
    type: Array,
    default: () => [],
  },
});

const emit = defineEmits([
  "update:prompt",
  "submit",
  "abort",
  "select-skill",
  "clear-skill",
  "local-upload",
  "cloud-select",
  "select-model",
  "prompt-submit",
  "remove-attachment",
]);

const attachmentMenuOpen = ref(false);
const modelMenuOpen = ref(false);

const currentSkill = computed(() => props.skills.find((item) => item.key === props.activeQuickSkill) || null);

function onPromptInput(event) {
  emit("update:prompt", event.target.value);
}

function onLocalUpload(event) {
  emit("local-upload", event);
  attachmentMenuOpen.value = false;
}

function onSelectModel(model) {
  emit("select-model", model);
  modelMenuOpen.value = false;
}

function onCloudSelect() {
  emit("cloud-select");
  attachmentMenuOpen.value = false;
}

function onKeydown(event) {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    emit("submit");
  }
}
</script>

<template>
  <div class="composer-dock">
    <PromptMenu
      v-if="promptMenu"
      :prompt-menu="promptMenu"
      :loading="loading"
      @submit="emit('prompt-submit', $event)"
    />

    <div class="skill-context" :class="{ active: !!currentSkill }">
      <div v-if="currentSkill">
        <strong>{{ currentSkill.title }}</strong>
        <p>{{ currentSkill.examples?.[0] }}</p>
      </div>
      <button v-if="currentSkill" class="icon-ghost" type="button" @click="emit('clear-skill')">
        <span class="material-symbols-rounded">close</span>
      </button>
    </div>

    <div class="composer-card">
      <div class="dropdown-anchor">
        <button class="icon-pill" type="button" aria-label="附件菜单" @click="attachmentMenuOpen = !attachmentMenuOpen">
          <span class="material-symbols-rounded">add</span>
        </button>
        <div class="dropdown-menu" :class="{ open: attachmentMenuOpen }">
          <label class="dropdown-item">
            <span class="material-symbols-rounded">upload_file</span>
            本地上传
            <input type="file" hidden @change="onLocalUpload" />
          </label>
          <button class="dropdown-item" type="button" @click="onCloudSelect">
            <span class="material-symbols-rounded">folder_open</span>
            从云盘添加
          </button>
        </div>
      </div>

      <textarea
        class="composer-input"
        rows="1"
        :value="prompt"
        placeholder="输入任务目标，或先选择一个 skill 进入对应示例流程"
        @input="onPromptInput"
        @keydown="onKeydown"
      />

      <div class="composer-actions">
        <div class="dropdown-anchor">
          <button class="ghost-pill selected" type="button" aria-label="模型选择" @click="modelMenuOpen = !modelMenuOpen">
            <span class="material-symbols-rounded" style="font-size: 18px">neurology</span>
            <span>{{ currentModel || "Minimax" }}</span>
            <span class="material-symbols-rounded" style="font-size: 18px">expand_more</span>
          </button>
          <div class="dropdown-menu align-right" :class="{ open: modelMenuOpen }">
            <button
              v-for="item in modelOptions"
              :key="item.modelName"
              class="dropdown-item"
              type="button"
              @click="onSelectModel(item)"
            >
              <span class="material-symbols-rounded">
                {{ currentModel === item.modelName ? "check_circle" : "radio_button_unchecked" }}
              </span>
              {{ item.modelDisplayName || item.modelName }}
            </button>
          </div>
        </div>

        <button
          v-if="!loading"
          class="send-button"
          type="button"
          aria-label="发送"
          @click="emit('submit')"
        >
          <span class="material-symbols-rounded">arrow_upward</span>
        </button>
        <button
          v-else
          class="send-button abort"
          type="button"
          aria-label="暂停"
          @click="emit('abort')"
        >
          <span class="material-symbols-rounded">stop_circle</span>
        </button>
      </div>
    </div>

    <div class="skill-strip">
      <button
        v-for="skill in skills"
        :key="skill.key"
        class="skill-chip"
        :class="{ active: activeQuickSkill === skill.key }"
        type="button"
        @click="emit('select-skill', skill)"
      >
        {{ skill.title }}
      </button>
    </div>

    <div class="chip-row attachment-chips" v-if="uploadedAttachments.length">
      <span v-for="item in uploadedAttachments" :key="item.nodeId" class="attachment-chip">
        <span class="material-symbols-rounded chip-file-icon">description</span>
        <span class="chip-name">{{ item.name }}</span>
        <button
          type="button"
          class="chip-remove"
          aria-label="移除附件"
          @click.stop="emit('remove-attachment', item)"
        >
          <span class="material-symbols-rounded">close</span>
        </button>
      </span>
    </div>
  </div>
</template>

<style scoped>
.attachment-chips {
  flex-wrap: wrap;
  gap: 8px;
}

.attachment-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 8px 6px 10px;
  border-radius: 10px;
  background: var(--primary-50, #e8f0fe);
  border: 1px solid var(--outline, #e4e4e2);
  font-size: 13px;
  color: var(--grey-900, #1f1f1f);
  max-width: 100%;
}

.chip-file-icon {
  font-size: 18px;
  color: var(--primary-600, #0b57d0);
}

.chip-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 220px;
}

.chip-remove {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 2px;
  border-radius: 6px;
  color: var(--grey-600, #5e5e5e);
}

.chip-remove:hover {
  background: rgba(0, 0, 0, 0.06);
}
</style>
