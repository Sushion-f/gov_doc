<script setup>
import { computed, ref } from "vue";
import AttachmentChip from "@/components/AttachmentChip.vue";
import ContextMeter from "@/components/ContextMeter.vue";
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
  contextUsage: {
    type: Object,
    default: null,
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
  compactionHistory: {
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
  "open-attachment",
  "compact-context",
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
        <ContextMeter
          v-if="contextUsage"
          class="composer-context-meter"
          :usage="contextUsage"
          :loading="loading"
          :history="compactionHistory"
          @compact="emit('compact-context')"
        />

        <div class="composer-actions-spacer" />

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
      <AttachmentChip
        v-for="item in uploadedAttachments"
        :key="item.nodeId"
        :item="item"
        :removable="true"
        @open="emit('open-attachment', $event)"
        @remove="emit('remove-attachment', $event)"
      />
    </div>
  </div>
</template>

<style scoped>
.attachment-chips {
  flex-direction: column;
  gap: 10px;
}

.composer-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.composer-context-meter {
  margin-right: 4px;
}

.composer-actions-spacer {
  flex: 1;
}
</style>
