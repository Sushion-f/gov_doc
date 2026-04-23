<script setup>
import { computed, nextTick, ref, watch } from "vue";
import CloudFilePicker from "@/components/CloudFilePicker.vue";
import ComposerDock from "@/components/ComposerDock.vue";
import ConversationPlanStrip from "@/components/ConversationPlanStrip.vue";
import EditorPreview from "@/components/EditorPreview.vue";
import HomeHero from "@/components/HomeHero.vue";
import MessageStream from "@/components/MessageStream.vue";
import {
  abortCurrentRun,
  compactConversation,
  homeQuickSkills,
  recommendationPrompts,
  runConversation,
  state,
  uploadDocument,
} from "@/store";

const prompt = ref("");
const selectedModel = ref("");
const uploadedAttachments = ref([]);
const showCloudPicker = ref(false);
const chatSurface = ref(null);
const drawerTarget = ref(null);

const currentMessages = computed(() => state.currentConversation?.messages || []);
const currentArtifacts = computed(() => state.currentConversation?.artifacts || []);
const currentPromptMenu = computed(() => state.currentConversation?.pendingPromptMenu || state.pendingPromptMenu);
const currentTodoList = computed(() => state.currentConversation?.latestTodoList || state.latestTodoList);
const currentWaitingInput = computed(() => {
  if (!currentPromptMenu.value) {
    return null;
  }
  if (currentPromptMenu.value.promptMenu) {
    return currentPromptMenu.value;
  }
  return {
    question: currentPromptMenu.value.question || currentPromptMenu.value.description || "",
    missing_fields: (currentPromptMenu.value.missingItems || []).map((item, index) => ({
      key: `missing_${index + 1}`,
      label: item,
      hint: item,
    })),
    options: currentPromptMenu.value.options || [],
    promptMenu: currentPromptMenu.value,
  };
});
const currentArtifact = computed(() => drawerTarget.value);
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
  drawerTarget.value = artifact;
}

function closeArtifact() {
  drawerTarget.value = null;
}

function stripHtml(html) {
  return String(html || "")
    .replace(/<br\s*\/?>/gi, "\n")
    .replace(/<\/(p|div|li|h[1-6]|blockquote|tr)>/gi, "\n")
    .replace(/<[^>]+>/g, "")
    .replace(/&nbsp;/g, " ")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&amp;/g, "&")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

function latestAssistantSummary(message) {
  const text = stripHtml(message?.contentHtml || message?.content || "");
  if (!text) {
    return "";
  }
  return text.length > 600 ? `${text.slice(0, 599).trim()}…` : text;
}

async function handleRegenerate() {
  const lastUser = [...currentMessages.value].reverse().find((item) => item.role === "user");
  const lastAssistant = [...currentMessages.value].reverse().find((item) => item.role === "assistant");
  if (!lastUser || !lastAssistant) {
    return;
  }
  const effectiveGoal = lastUser?.meta?.effectiveGoal || lastUser?.content || "";
  const latestArtifacts = (currentArtifacts.value || []).slice(-3).map((artifact) => ({
    id: artifact.id,
    artifactType: artifact.artifactType,
    title: artifact.title,
    summary: artifact.summary,
    contentHtml: artifact.contentHtml,
    workspaceNodeId: artifact.workspaceNodeId,
    relativePath: artifact.relativePath || artifact?.meta?.relativePath || null,
    versionPath: artifact.versionPath || artifact?.meta?.versionPath || null,
    sourceSkill: artifact.sourceSkill || artifact?.meta?.sourceSkill || null,
    sourceState: artifact.sourceState || artifact?.meta?.sourceState || null,
    status: artifact.status || artifact?.meta?.status || null,
    errorDetail: artifact.errorDetail || artifact?.meta?.errorDetail || null,
  }));
  await runConversation({
    content: "重新生成",
    model: currentModel.value,
    skill: state.activeQuickSkill || null,
    attachments: uploadedAttachments.value,
    operationContext: {
      intentType: "regenerate",
      rewriteMode: "regenerate",
      baseUserGoal: effectiveGoal,
      latestAssistantSummary: latestAssistantSummary(lastAssistant),
      latestArtifactRefs: latestArtifacts,
    },
  });
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
      title: result.name,
      fileType: result.fileType || "document",
      source: "workspace_upload",
      sourceLabel: result.editable === false ? "只读预览 · 保存将另存 DOCX" : "本地上传 · 点击打开编辑",
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
      sourceLabel: "云盘文件",
    });
  }
  uploadedAttachments.value = next;
}

function openAttachmentDrawer(item) {
  drawerTarget.value = {
    id: item.nodeId || item.id,
    title: item.title || item.name,
    summary: item.summary || item.sourceLabel || "工作区附件",
    workspaceNodeId: item.workspaceNodeId || item.nodeId || item.id,
    artifactType: item.fileType || "document",
  };
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

function onAbortRun() {
  abortCurrentRun();
}

async function handleCompactContext() {
  if (!state.currentConversationId || state.runLoading) {
    return;
  }
  await compactConversation(state.currentConversationId);
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
        />
      </div>

      <ConversationPlanStrip
        :todo-list="currentTodoList"
        :waiting-input="currentWaitingInput"
      />

      <ComposerDock
        v-model:prompt="prompt"
        :prompt-menu="currentPromptMenu"
        :loading="state.runLoading"
        :context-usage="state.contextUsage"
        :compaction-history="state.compactionHistory || []"
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
        @open-attachment="openAttachmentDrawer"
        @select-model="pickModel"
        @prompt-submit="handlePromptMenuSubmit"
        @abort="onAbortRun"
        @compact-context="handleCompactContext"
      />
    </section>
  </div>
</template>
