<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from "vue";

const props = defineProps({
  promptMenu: {
    type: Object,
    default: null,
  },
  loading: {
    type: Boolean,
    default: false,
  },
});

const emit = defineEmits(["submit"]);
const customInput = ref("");
const textareaRef = ref(null);

watch(
  () => props.promptMenu,
  () => {
    customInput.value = "";
  }
);

const options = computed(() => props.promptMenu?.promptMenu?.options || props.promptMenu?.options || []);
const title = computed(() => props.promptMenu?.promptMenu?.title || props.promptMenu?.title || "请选择下一步");
const description = computed(
  () => props.promptMenu?.promptMenu?.description || props.promptMenu?.description || ""
);
const sourceState = computed(() => props.promptMenu?.sourceState || "");
const errorDetail = computed(() => props.promptMenu?.errorDetail || "");

const letters = ["A", "B", "C", "D", "E", "F", "G", "H"];

function sourceStateLabel(value) {
  const mapping = {
    legacy_success: "旧接口成功",
    model_success: "模型成功",
    static_template: "静态模板",
    legacy_error: "旧接口失败",
    model_error: "模型失败",
  };
  return mapping[value] || value || "";
}

function handleOption(optionKey) {
  const option = options.value.find((item) => item.key === optionKey) || null;
  emit("submit", {
    selectedOption: optionKey,
    promptMenuInput: optionKey === "custom_input" ? customInput.value : "",
    optionLabel: option?.label || "",
  });
}

function autoResize() {
  const el = textareaRef.value;
  if (!el) {
    return;
  }
  el.style.height = "auto";
  el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
}

watch(customInput, () => {
  autoResize();
});

function onGlobalKeydown(e) {
  if (!props.promptMenu || props.loading) {
    return;
  }
  if (!e.altKey || e.metaKey || e.ctrlKey) {
    return;
  }
  const digit = e.code === "Digit1" ? 1 : e.code === "Digit2" ? 2 : e.code === "Digit3" ? 3 : 0;
  if (!digit) {
    return;
  }
  const opt = options.value[digit - 1];
  if (opt?.key) {
    e.preventDefault();
    handleOption(opt.key);
  }
}

onMounted(() => {
  document.addEventListener("keydown", onGlobalKeydown);
});

onUnmounted(() => {
  document.removeEventListener("keydown", onGlobalKeydown);
});
</script>

<template>
  <section v-if="promptMenu" class="prompt-menu active">
    <div class="prompt-menu-header">
      <div>
        <strong>{{ title }}</strong>
        <p>{{ description }}</p>
        <div v-if="sourceState || errorDetail" class="prompt-menu-meta">
          <span v-if="sourceState" class="result-source-chip" :class="sourceState">
            {{ sourceStateLabel(sourceState) }}
          </span>
          <span v-if="errorDetail" class="result-error-copy">{{ errorDetail }}</span>
        </div>
      </div>
    </div>

    <div class="prompt-option-cards">
      <button
        v-for="(item, index) in options"
        :key="item.key"
        class="option-card"
        type="button"
        :disabled="loading"
        @click="handleOption(item.key)"
      >
        <span class="option-index">{{ letters[index] || String(index + 1) }}</span>
        <span class="option-body">
          <span class="option-label">{{ item.label }}</span>
          <span v-if="item.recommended" class="option-badge">推荐</span>
        </span>
        <span class="option-kbd">⌥{{ index + 1 }}</span>
      </button>
    </div>

    <textarea
      ref="textareaRef"
      v-model="customInput"
      class="composer-input prompt-menu-custom"
      rows="1"
      placeholder="补充说明（可选）；⌥1–3 快速选择上方选项。"
      @keydown.meta.enter.prevent="handleOption('custom_input')"
      @keydown.ctrl.enter.prevent="handleOption('custom_input')"
    />
  </section>
</template>

<style scoped>
.prompt-option-cards {
  display: grid;
  gap: 10px;
}

.option-card {
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: center;
  gap: 12px;
  width: 100%;
  text-align: left;
  padding: 12px 14px;
  border-radius: 14px;
  border: 1px solid rgba(227, 227, 227, 0.95);
  background: rgba(255, 255, 255, 0.98);
  box-shadow: 0 2px 8px rgba(60, 64, 67, 0.06);
  transition: border-color 0.2s ease, box-shadow 0.2s ease, transform 0.15s ease;
}

.option-card:hover:not(:disabled) {
  border-color: rgba(11, 87, 208, 0.35);
  box-shadow: 0 6px 18px rgba(11, 87, 208, 0.12);
  transform: translateY(-1px);
}

.option-card:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.option-index {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 600;
  background: rgba(11, 87, 208, 0.1);
  color: var(--primary-700, #0842a0);
}

.option-body {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.option-label {
  font-size: var(--text-sm);
  color: var(--grey-900, #1f1f1f);
  line-height: 1.45;
}

.option-badge {
  font-size: 11px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 999px;
  background: rgba(11, 87, 208, 0.12);
  color: var(--primary-700, #0842a0);
}

.option-kbd {
  font-size: 11px;
  color: var(--grey-500, #757575);
  white-space: nowrap;
}

.prompt-menu-custom {
  min-height: 40px;
  resize: vertical;
  max-height: 160px;
}
</style>
