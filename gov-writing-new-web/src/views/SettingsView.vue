<script setup>
import { computed, onMounted, ref } from "vue";
import {
  addDictionaryEntry,
  clearMemory,
  deleteDictionaryEntry,
  deleteTemplate,
  loadSettings,
  saveMemory,
  saveProfile,
  state,
  uploadTemplate,
} from "@/store";

const activeTab = ref("dictionary");
const defaultModel = ref("");
const preferredSkills = ref("");
const identifyMarkdown = ref("");
const memoryMarkdown = ref("");
const newWord = ref("");
const newWordType = ref("whiteList");
const templateTitle = ref("");
const templateType = ref("");

onMounted(async () => {
  await loadSettings();
  hydrate();
});

const whiteList = computed(() => state.dictionaries.whiteList || []);
const blackList = computed(() => state.dictionaries.blackList || []);
const hasDictionary = computed(() => whiteList.value.length || blackList.value.length);
const hasTemplates = computed(() => (state.templates || []).length > 0);

function hydrate() {
  defaultModel.value = state.settingsProfile?.defaultModel || "";
  preferredSkills.value = (state.settingsProfile?.preferredSkills || []).join(", ");
  identifyMarkdown.value = state.settingsMemory?.identifyMarkdown || "";
  memoryMarkdown.value = state.settingsMemory?.memoryMarkdown || "";
}

async function handleSaveProfile() {
  await saveProfile({
    default_model: defaultModel.value,
    preferred_skills: preferredSkills.value
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean),
    recommendation_summary: state.settingsProfile?.recommendationSummary || null,
  });
}

async function handleSaveMemory() {
  await saveMemory({
    identity: state.settingsMemory?.identity || {},
    memory: state.settingsMemory?.memory || {},
    identify_markdown: identifyMarkdown.value,
    memory_markdown: memoryMarkdown.value,
  });
}

async function handleAddDictionaryEntry() {
  if (!newWord.value.trim()) {
    return;
  }
  await addDictionaryEntry(newWordType.value, newWord.value.trim());
  newWord.value = "";
}

async function handleUploadTemplate(event) {
  const file = event.target.files?.[0];
  if (!file || !templateTitle.value.trim()) {
    return;
  }
  await uploadTemplate({
    title: templateTitle.value.trim(),
    documentType: templateType.value.trim(),
    file,
  });
  templateTitle.value = "";
  templateType.value = "";
  event.target.value = "";
}
</script>

<template>
  <section class="settings-layout">
    <nav class="settings-nav">
      <div class="settings-nav-title">设置</div>
      <button class="settings-nav-item" :class="{ active: activeTab === 'dictionary' }" @click="activeTab = 'dictionary'">
        <span class="material-symbols-rounded">spellcheck</span>
        审核词典
      </button>
      <button class="settings-nav-item" :class="{ active: activeTab === 'template' }" @click="activeTab = 'template'">
        <span class="material-symbols-rounded">text_format</span>
        排版模板
      </button>
      <button class="settings-nav-item" :class="{ active: activeTab === 'memory' }" @click="activeTab = 'memory'">
        <span class="material-symbols-rounded">memory</span>
        记忆
      </button>
    </nav>

    <div class="settings-content">
      <section v-if="activeTab === 'dictionary'" class="settings-panel active">
        <div class="panel-header">审核词典</div>

        <div class="settings-card form-stack">
          <div class="inline-form">
            <select v-model="newWordType" class="text-field compact">
              <option value="whiteList">正词</option>
              <option value="blackList">禁词</option>
            </select>
            <input v-model="newWord" class="text-field" placeholder="输入词条" />
            <button class="btn-add" @click="handleAddDictionaryEntry">添加词条</button>
          </div>
        </div>

        <div v-if="!hasDictionary" class="empty-state">
          <span class="material-symbols-rounded">spellcheck</span>
          <p>暂无审核词典<br />添加自定义词条，智能体将在审核时优先参考</p>
        </div>

        <div v-else class="settings-card settings-grid">
          <section class="settings-section">
            <h3>正词</h3>
            <ul class="token-list">
              <li v-for="item in whiteList" :key="item.id || item.word">
                <span>{{ item.word }}</span>
                <button class="tiny-action" @click="deleteDictionaryEntry(item.id)">删除</button>
              </li>
            </ul>
          </section>
          <section class="settings-section">
            <h3>禁词</h3>
            <ul class="token-list danger">
              <li v-for="item in blackList" :key="item.id || item.word">
                <span>{{ item.word }}</span>
                <button class="tiny-action" @click="deleteDictionaryEntry(item.id)">删除</button>
              </li>
            </ul>
          </section>
        </div>
      </section>

      <section v-if="activeTab === 'template'" class="settings-panel active">
        <div class="panel-header">排版模板</div>

        <div class="settings-card form-stack">
          <div class="inline-form">
            <input v-model="templateTitle" class="text-field" placeholder="模板名称" />
            <input v-model="templateType" class="text-field" placeholder="文种，如 通知 / 汇报" />
            <label class="btn-add template-upload-label">
              上传模板
              <input type="file" hidden @change="handleUploadTemplate" />
            </label>
          </div>
        </div>

        <div v-if="!hasTemplates" class="empty-state">
          <span class="material-symbols-rounded">text_format</span>
          <p>暂无排版模板<br />上传模板文件，智能体将按照格式规范排版公文</p>
        </div>

        <div v-else class="template-list">
          <article v-for="item in state.templates" :key="item.id || item.title" class="template-card">
            <div>
              <strong>{{ item.title }}</strong>
              <span>{{ item.documentType }}</span>
            </div>
            <button class="tiny-action" @click="deleteTemplate(item.id)">删除</button>
          </article>
        </div>
      </section>

      <section v-if="activeTab === 'memory'" class="settings-panel active">
        <div class="panel-header">记忆</div>

        <div class="settings-card form-stack">
          <label class="field">
            <span>默认模型</span>
            <input v-model="defaultModel" class="text-field" />
          </label>

          <label class="field">
            <span>常用技能</span>
            <input v-model="preferredSkills" class="text-field" placeholder="用逗号分隔，如 writing, review" />
          </label>

          <label class="field">
            <span>identify.md</span>
            <textarea v-model="identifyMarkdown" class="code-area" />
          </label>

          <label class="field">
            <span>memory.md</span>
            <textarea v-model="memoryMarkdown" class="code-area" />
          </label>
          <p class="field-hint">`memory.md` 现在是记忆索引入口。系统会自动维护主题文件，请把手工补充内容写在“手工备注”部分。</p>

          <div class="settings-actions">
            <button class="btn-add" @click="handleSaveProfile">保存画像</button>
            <button class="btn-add" @click="handleSaveMemory">保存记忆</button>
            <button class="btn-back" @click="clearMemory">清空记忆</button>
          </div>

          <div class="summary-card">
            <h3>推荐摘要</h3>
            <p>{{ state.settingsProfile?.recommendationSummary || "暂无推荐摘要。" }}</p>
          </div>

          <div class="summary-card">
            <h3>session_summary.md（摘要索引）</h3>
            <pre>{{ state.settingsMemory?.sessionSummaryMarkdown || "暂无会话摘要。" }}</pre>
          </div>
        </div>
      </section>
    </div>
  </section>
</template>
