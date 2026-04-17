<script setup>
import { computed, nextTick, ref, watch } from "vue";
import { useRouter } from "vue-router";
import CliPanel from "@/components/CliPanel.vue";
import CloudFilePicker from "@/components/CloudFilePicker.vue";
import ComposerDock from "@/components/ComposerDock.vue";
import EditorPreview from "@/components/EditorPreview.vue";
import HomeHero from "@/components/HomeHero.vue";
import MessageStream from "@/components/MessageStream.vue";
import {
  abortCurrentRun,
  homeQuickSkills,
  recommendationPrompts,
  runConversation,
  state,
  uploadDocument,
} from "@/store";

const prompt = ref("");
const openedArtifactId = ref("");
const selectedModel = ref("");
const uploadedAttachments = ref([]);
const showCloudPicker = ref(false);
const router = useRouter();
const chatSurface = ref(null);
const cliPanelRef = ref(null);
const cliOpen = ref(false);

const currentMessages = computed(() => state.currentConversation?.messages || []);
const currentArtifacts = computed(() => state.currentConversation?.artifacts || []);
const currentPromptMenu = computed(() => state.currentConversation?.pendingPromptMenu || state.pendingPromptMenu);
const currentArtifact = computed(() =>
  currentArtifacts.value.find((item) => item.id === openedArtifactId.value) || null
);
const currentAnnotations = computed(() => {
  const latestAssistant = [...currentMessages.value].reverse().find((item) => item.role === "assistant");
  return latestAssistant?.annotations || [];
});

const firstLoginPrompts = computed(() => [
  "如何使用该产品？",
  "该产品能帮助我什么？",
]);

const secondLoginPrompts = computed(() => [
  recommendationPrompts.value[0] || "我现在有哪些 skills？",
  recommendationPrompts.value[1] || "结合我最近的写作习惯，今天适合先做什么？",
  "搜索一下关于具身智能的文章",
]);

const currentModel = computed(() => selectedModel.value || state.user?.default_model || "");

watch(
  () => state.user?.default_model,
  (dm) => {
    if (dm && selectedModel.value === "") {
      selectedModel.value = dm;
    }
  },
  { immediate: true }
);

const showFirstLoginPrompts = computed(() =>
  Boolean(state.user?.is_first_login_to_agentloop ?? state.user?.is_first_login_to_new_app)
);
const showReturningPrompts = computed(
  () => !(state.user?.is_first_login_to_agentloop ?? state.user?.is_first_login_to_new_app)
);

async function handleSubmit(text = prompt.value) {
  const content = (text || "").trim();
  if (!content) {
    return;
  }
  await runConversation({
    content,
    model: currentModel.value,
    skill: state.activeQuickSkill || null,
    attachments: uploadedAttachments.value,
  });
  prompt.value = "";
  uploadedAttachments.value = [];
}

async function handlePromptMenuSubmit({ selectedOption, promptMenuInput, optionLabel }) {
  const isCustomInput = selectedOption === "custom_input";
  const resumeContent = isCustomInput ? (promptMenuInput || "").trim() : optionLabel || "继续执行";
  await runConversation({
    content: resumeContent || "继续执行",
    model: currentModel.value,
    skill: null,
    attachments: uploadedAttachments.value,
    resumeFromWaiting: true,
    selectedOption,
    promptMenuInput,
  });
  prompt.value = "";
}

function useQuickSkill(skill) {
  state.activeQuickSkill = skill.key;
  prompt.value = skill.examples?.[0] || "";
}

function clearQuickSkill() {
  state.activeQuickSkill = "";
}

function openArtifact(artifact) {
  if (artifact?.workspaceNodeId) {
    router.push({ name: "editor", params: { id: artifact.workspaceNodeId } });
    return;
  }
  openedArtifactId.value = artifact.id;
}

function closeArtifact() {
  openedArtifactId.value = "";
}

function handleRegenerate() {
  const lastUser = [...currentMessages.value].reverse().find((item) => item.role === "user");
  if (!lastUser) {
    return;
  }
  handleSubmit(lastUser.content);
}

async function handleLocalUpload(event) {
  const file = event.target.files?.[0];
  if (!file) {
    return;
  }
  const result = await uploadDocument(file);
  uploadedAttachments.value = [
    ...uploadedAttachments.value,
    {
      nodeId: result.id,
      name: result.name,
      source: "workspace_upload",
    },
  ];
  event.target.value = "";
}

function pickModel(model) {
  selectedModel.value = model.modelName;
}

function handleCloudSelect() {
  showCloudPicker.value = true;
}

function onCloudPickerConfirm(items) {
  const next = [...uploadedAttachments.value];
  const existing = new Set(next.map((a) => a.nodeId));
  for (const item of items || []) {
    if (!item?.id || existing.has(item.id)) {
      continue;
    }
    existing.add(item.id);
    next.push({
      nodeId: item.id,
      name: item.name,
      source: "workspace",
    });
  }
  uploadedAttachments.value = next;
}

function removeAttachment(item) {
  uploadedAttachments.value = uploadedAttachments.value.filter((a) => a.nodeId !== item.nodeId);
}

function scrollChatToBottom() {
  const el = chatSurface.value;
  if (!el) {
    return;
  }
  el.scrollTop = el.scrollHeight;
}

watch(
  () => currentMessages.value.length,
  async () => {
    await nextTick();
    scrollChatToBottom();
  }
);

watch(
  () => state.streamScrollTick,
  async () => {
    await nextTick();
    scrollChatToBottom();
  }
);

function onSuggestCli() {
  cliOpen.value = true;
  nextTick(() => {
    cliPanelRef.value?.runLs?.();
  });
}

function onAbortRun() {
  abortCurrentRun();
}
</script>

<template>
  <div class="conversation-layout" :class="{ 'editor-open': !!currentArtifact }">
    <CloudFilePicker v-model:open="showCloudPicker" @confirm="onCloudPickerConfirm" />

    <EditorPreview :artifact="currentArtifact" :annotations="currentAnnotations" @close="closeArtifact" />

    <section class="chat-column">
      <div ref="chatSurface" class="chat-surface" :class="{ 'is-empty': !currentMessages.length }">
        <HomeHero
          v-if="!currentMessages.length"
          :show-first-login-prompts="showFirstLoginPrompts"
          :show-returning-prompts="showReturningPrompts"
          :first-login-prompts="firstLoginPrompts"
          :second-login-prompts="secondLoginPrompts"
          @select="handleSubmit"
        />

        <MessageStream
          v-else
          :messages="currentMessages"
          :events="state.currentEvents"
          :artifacts="currentArtifacts"
          :planner-streaming-text="state.streamingPlannerReasoning"
          @open-artifact="openArtifact"
          @regenerate="handleRegenerate"
          @suggest-cli="onSuggestCli"
        />
      </div>

      <div class="cli-panel-bar">
        <button
          class="cli-toggle"
          type="button"
          :aria-expanded="cliOpen"
          aria-label="命令行"
          @click="cliOpen = !cliOpen"
        >
          <span class="material-symbols-rounded">terminal</span>
          命令行
        </button>
      </div>
      <CliPanel v-show="cliOpen" ref="cliPanelRef" />

      <ComposerDock
        v-model:prompt="prompt"
        :prompt-menu="currentPromptMenu"
        :loading="state.runLoading"
        :model-options="state.modelOptions"
        :current-model="currentModel"
        :uploaded-attachments="uploadedAttachments"
        :active-quick-skill="state.activeQuickSkill"
        :skills="homeQuickSkills"
        @submit="handleSubmit"
        @select-skill="useQuickSkill"
        @clear-skill="clearQuickSkill"
        @local-upload="handleLocalUpload"
        @cloud-select="handleCloudSelect"
        @remove-attachment="removeAttachment"
        @select-model="pickModel"
        @prompt-submit="handlePromptMenuSubmit"
        @abort="onAbortRun"
      />
    </section>
  </div>
</template>
