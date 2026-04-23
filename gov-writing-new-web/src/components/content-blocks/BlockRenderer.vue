<script setup>
import ThinkingBlock from "@/components/content-blocks/ThinkingBlock.vue";
import TextBlock from "@/components/content-blocks/TextBlock.vue";
import ToolUseBlock from "@/components/content-blocks/ToolUseBlock.vue";
import ToolResultBlock from "@/components/content-blocks/ToolResultBlock.vue";
import ArtifactRefBlock from "@/components/content-blocks/ArtifactRefBlock.vue";
import TodoListBlock from "@/components/content-blocks/TodoListBlock.vue";
import WaitingUserBlock from "@/components/content-blocks/WaitingUserBlock.vue";
import ContextNoticeBlock from "@/components/content-blocks/ContextNoticeBlock.vue";

const props = defineProps({
  block: { type: Object, required: true },
});

const emit = defineEmits(["open-artifact"]);

const componentMap = {
  thinking: ThinkingBlock,
  text: TextBlock,
  tool_use: ToolUseBlock,
  tool_result: ToolResultBlock,
  artifact_ref: ArtifactRefBlock,
  todo_list: TodoListBlock,
  waiting_user: WaitingUserBlock,
  context_notice: ContextNoticeBlock,
};

function resolveComponent() {
  return componentMap[props.block?.type] || null;
}
</script>

<template>
  <component
    :is="resolveComponent()"
    v-if="resolveComponent()"
    :block="block"
    @open-artifact="emit('open-artifact', $event)"
  />
</template>
