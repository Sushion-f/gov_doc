<script setup>
import { nextTick, ref } from "vue";
import { requestJson } from "@/api";

const lines = ref([{ type: "system", text: "输入 ls / read <id> / write <id> <内容>。工作区 API 已连接。" }]);
const inputLine = ref("");
const outputRef = ref(null);

function pushLine(type, text) {
  lines.value = [...lines.value, { type, text }];
  nextTick(() => {
    if (outputRef.value) {
      outputRef.value.scrollTop = outputRef.value.scrollHeight;
    }
  });
}

function formatLs(data) {
  if (!Array.isArray(data) || !data.length) {
    return "(空)";
  }
  return data
    .map((item) => {
      const t = item.type === "folder" ? "📁" : "📄";
      return `${t} ${item.name}  [id=${item.id}]`;
    })
    .join("\n");
}

async function runLs() {
  try {
    const res = await requestJson("/api/agentloop/workspace?view=recent");
    pushLine("out", formatLs(res.data));
  } catch (e) {
    pushLine("err", String(e.message || e));
  }
}

async function runRead(nodeId) {
  try {
    const res = await requestJson(`/api/agentloop/workspace/documents/${nodeId}`);
    const d = res.data || {};
    pushLine("out", `--- ${d.title || nodeId} ---\n${(d.contentText || "").slice(0, 8000)}`);
  } catch (e) {
    pushLine("err", String(e.message || e));
  }
}

async function runWrite(nodeId, rest) {
  const content = rest.join(" ").trim();
  if (!content) {
    pushLine("err", "write: 缺少正文内容");
    return;
  }
  try {
    await requestJson(`/api/agentloop/workspace/documents/${nodeId}`, {
      method: "PUT",
      body: JSON.stringify({
        content_html: `<p>${content.replace(/</g, "&lt;")}</p>`,
        content_text: content,
      }),
    });
    pushLine("out", `已写入节点 ${nodeId}`);
  } catch (e) {
    pushLine("err", String(e.message || e));
  }
}

async function handleSubmit() {
  const raw = inputLine.value.trim();
  if (!raw) {
    return;
  }
  pushLine("in", `> ${raw}`);
  inputLine.value = "";
  const parts = raw.split(/\s+/);
  const cmd = (parts[0] || "").toLowerCase();
  const arg1 = parts[1];
  const rest = parts.slice(2);

  if (cmd === "ls") {
    await runLs();
    return;
  }
  if (cmd === "read" && arg1) {
    await runRead(arg1);
    return;
  }
  if (cmd === "write" && arg1) {
    await runWrite(arg1, rest);
    return;
  }
  pushLine("err", "未知命令。使用: ls | read <nodeId> | write <nodeId> <文本>");
}

function onKeydown(e) {
  if (e.key === "Enter") {
    e.preventDefault();
    handleSubmit();
  }
}

defineExpose({
  runLs,
  focusInput() {
    /* optional */
  },
});
</script>

<template>
  <div class="cli-panel">
    <div ref="outputRef" class="cli-output" aria-live="polite">
      <div v-for="(line, idx) in lines" :key="idx" :class="['cli-line', line.type]">
        <pre>{{ line.text }}</pre>
      </div>
    </div>
    <div class="cli-input-row">
      <span class="cli-prompt">$</span>
      <input v-model="inputLine" class="cli-input" type="text" autocomplete="off" @keydown="onKeydown" />
    </div>
  </div>
</template>

<style scoped>
.cli-panel {
  display: flex;
  flex-direction: column;
  gap: 0;
  border-radius: 12px;
  border: 1px solid rgba(60, 64, 67, 0.35);
  background: #1e1e1e;
  color: #d4d4d4;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
  font-size: 12px;
  min-height: 140px;
  max-height: 220px;
  overflow: hidden;
}

.cli-output {
  flex: 1;
  min-height: 80px;
  max-height: 160px;
  overflow-y: auto;
  padding: 10px 12px;
}

.cli-line pre {
  margin: 0 0 6px;
  white-space: pre-wrap;
  word-break: break-word;
  font: inherit;
  line-height: 1.5;
}

.cli-line.in {
  color: #9cdcfe;
}

.cli-line.out {
  color: #ce9178;
}

.cli-line.err {
  color: #f48771;
}

.cli-line.system {
  color: #6a9955;
}

.cli-input-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
  background: #252526;
}

.cli-prompt {
  color: #4ec9b0;
  flex-shrink: 0;
}

.cli-input {
  flex: 1;
  border: none;
  background: transparent;
  color: #d4d4d4;
  outline: none;
  font: inherit;
}
</style>
