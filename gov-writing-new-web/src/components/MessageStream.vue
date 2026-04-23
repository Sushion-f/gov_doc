<script setup>
import { computed, ref } from "vue";
import { marked } from "marked";
import AttachmentChip from "@/components/AttachmentChip.vue";
import BlockRenderer from "@/components/content-blocks/BlockRenderer.vue";
import { state, submitFeedback } from "@/store";

marked.use({ breaks: true, gfm: true });

const props = defineProps({
  messages: { type: Array, default: () => [] },
  events: { type: Array, default: () => [] },
  artifacts: { type: Array, default: () => [] },
  plannerStreamingText: { type: String, default: "" },
});

const emit = defineEmits(["open-artifact", "regenerate"]);

const streamEl = ref(null);
const copiedIds = ref(new Set());

const latestAssistantId = computed(() => {
  const last = [...props.messages].reverse().find((item) => item.role === "assistant");
  return last?.id || "";
});

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

function contentBlocksFor(message) {
  const blocks = Array.isArray(message?.contentBlocks) ? message.contentBlocks : [];
  return blocks.filter((item) => item && item.type);
}

function fallbackBlocks(message) {
  // schema v1 的历史消息：没有 contentBlocks，直接给 content 包一个 text block。
  const text = String(message?.content || "").trim();
  if (!text || text === "执行中") {
    const html = String(message?.contentHtml || "").trim();
    if (!html) return [];
    return [{ id: `legacy-${message.id}`, type: "text", text: stripHtml(html) }];
  }
  return [{ id: `legacy-${message.id}`, type: "text", text }];
}

function blocksToRender(message) {
  const blocks = contentBlocksFor(message);
  return blocks.length ? blocks : fallbackBlocks(message);
}

function isStreaming(message) {
  return message.id === latestAssistantId.value && state.runLoading;
}

function messageHeadline(message) {
  const blocks = blocksToRender(message);
  const textBlock = blocks.find((item) => item.type === "text");
  const source = textBlock?.text || message?.content || stripHtml(message?.contentHtml || "");
  const text = String(source || "").trim();
  if (text && text !== "执行中") {
    return text.length > 36 ? `${text.slice(0, 35)}…` : text;
  }
  return "智能体结果";
}

function feedbackFor(messageId) {
  return state.messageFeedbacks?.[messageId] ?? null;
}

async function toggleFeedback(message, type) {
  const cur = feedbackFor(message.id);
  const next = cur === type ? null : type;
  await submitFeedback(message.id, next);
}

async function copyMessage(message) {
  const blocks = blocksToRender(message);
  const text = blocks
    .filter((b) => b.type === "text")
    .map((b) => b.text)
    .join("\n\n") || message.content || stripHtml(message.contentHtml || "");
  try {
    await navigator.clipboard?.writeText(text);
    const next = new Set(copiedIds.value);
    next.add(message.id);
    copiedIds.value = next;
    window.setTimeout(() => {
      const n2 = new Set(copiedIds.value);
      n2.delete(message.id);
      copiedIds.value = n2;
    }, 1500);
  } catch {
    /* ignore */
  }
}
</script>

<template>
  <div ref="streamEl" class="message-stream" :class="{ 'has-messages': messages.length }">
    <div v-for="message in messages" :key="message.id" class="message-row" :class="message.role">
      <div v-if="message.role === 'user'" class="user-bubble">
        <div class="user-bubble-label">
          <span class="material-symbols-rounded">person</span>
          用户
        </div>
        <p>{{ message.content }}</p>
      </div>

      <article v-else class="assistant-card">
        <div class="assistant-header">
          <div class="assistant-meta">
            <div class="assistant-caption">{{ messageHeadline(message) }}</div>
          </div>
          <div class="assistant-status" :class="{ streaming: isStreaming(message) }">
            <span class="pulse" />
            {{ isStreaming(message) ? "执行中" : "已完成" }}
          </div>
        </div>

        <div class="content-blocks">
          <BlockRenderer
            v-for="(block, index) in blocksToRender(message)"
            :key="block.id || `${message.id}-${index}`"
            :block="block"
            @open-artifact="emit('open-artifact', $event)"
          />
        </div>

        <div v-if="message.id === latestAssistantId && artifacts.length" class="summary-list" style="margin-top: 14px">
          <AttachmentChip
            v-for="artifact in artifacts"
            :key="artifact.id"
            :item="artifact"
            preview-label="打开抽屉"
            @open="emit('open-artifact', $event)"
          />
        </div>

        <div class="message-actions">
          <button
            class="message-action"
            type="button"
            aria-label="复制"
            :class="{ 'is-success': copiedIds.has(message.id) }"
            @click="copyMessage(message)"
          >
            <span class="material-symbols-rounded">{{ copiedIds.has(message.id) ? "check" : "content_copy" }}</span>
          </button>
          <button
            class="message-action"
            type="button"
            aria-label="点赞"
            :class="{ active: feedbackFor(message.id) === 'like' }"
            @click="toggleFeedback(message, 'like')"
          >
            <span class="material-symbols-rounded">thumb_up</span>
          </button>
          <button
            class="message-action"
            type="button"
            aria-label="点踩"
            :class="{ active: feedbackFor(message.id) === 'dislike' }"
            @click="toggleFeedback(message, 'dislike')"
          >
            <span class="material-symbols-rounded">thumb_down</span>
          </button>
          <button class="message-action" type="button" aria-label="重新生成" @click="emit('regenerate')">
            <span class="material-symbols-rounded">refresh</span>
          </button>
        </div>
      </article>
    </div>
  </div>
</template>

<style scoped>
.content-blocks {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.message-action.active .material-symbols-rounded {
  font-variation-settings: "FILL" 1, "wght" 500, "GRAD" 0, "opsz" 24;
  color: var(--primary-600, #0b57d0);
}
.message-action.is-success .material-symbols-rounded {
  color: #137333;
  font-variation-settings: "FILL" 1, "wght" 500, "GRAD" 0, "opsz" 24;
}
</style>
