<template>
  <div class="welcome-section">
    <div class="welcome-center">
      <h1 class="welcome-heading">有什么我能帮你的吗？</h1>

      <!-- 推荐问题卡片 -->
      <div class="recommended-card">
        <div class="recommended-header">推荐问题</div>
        <div class="recommended-content">
          <!-- 首次登录 -->
          <div class="recommended-group">
            <div class="recommended-questions">
              <div
                v-for="(question, index) in questions"
                :key="index"
                class="question-chip"
                @click="handleQuestionClick(question)"
              >
                <el-icon><component :is="question.icon"></component></el-icon>
                {{ question.text }}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ChatRound } from '@element-plus/icons-vue';

interface Question {
  icon: any;
  text: string;
}

const emit = defineEmits<{
  'question-click': [text: string];
}>();

const questions: Question[] = [
  { icon: ChatRound, text: '如何使用该功能？' },
  { icon: ChatRound, text: '帮我生成一篇关于反诈的工作报告' },
  { icon: ChatRound, text: '对当前派警工单的警情类型进行分析' },
];

const handleQuestionClick = (question: Question) => {
  emit('question-click', question.text);
};
</script>

<style scoped lang="scss">
.welcome-section {
  width: 100%;
  max-width: 760px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 32px;
  flex: 1;
}

.welcome-center {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 32px;
  width: 100%;
}

.welcome-heading {
  font-size: 36px;
  font-weight: 700;
  text-align: center;
  line-height: 1.5;
  font-family: 'Space Grotesk', 'Noto Sans SC', sans-serif;
}

.recommended-card {
  width: 100%;
  border: 1px solid var(--glass-brd);
  border-radius: var(--radius-lg);
  background: var(--glass-bg);
  backdrop-filter: blur(14px) saturate(130%);
  -webkit-backdrop-filter: blur(14px) saturate(130%);
  padding: 20px;
  position: relative;
  box-shadow: var(--shadow-3);
  transition:
    box-shadow 0.2s var(--ease-out),
    transform 0.2s var(--ease-out);

  &:hover {
    box-shadow: var(--shadow-4);
    transform: translateY(-1px);
  }

  .recommended-header {
    font-size: 18px;
    line-height: 1.3;
    font-weight: 600;
    color: #1f1f1f;
    margin-bottom: 12px;
  }
}

.recommended-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding-top: 4px;
}

.recommended-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.recommended-group-label {
  font-size: 12px;
  font-weight: 500;
  color: var(--on-surface-variant);
}

.recommended-questions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.question-chip {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 0 14px;
  height: 34px;
  background: rgba(0, 0, 0, 0.04);
  border: 1px solid rgba(0, 0, 0, 0.1);
  border-radius: 20px;
  font-size: 13px;
  font-weight: 500;
  color: var(--on-surface);
  cursor: pointer;
  white-space: nowrap;
  transition:
    background 0.12s ease,
    border-color 0.12s ease;

  &:hover {
    background: var(--primary-dim);
    border-color: var(--primary-border);
    color: var(--primary);

    .el-icon {
      color: var(--primary);
    }
  }
}

.el-icon {
  font-size: 15px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  user-select: none;
  color: var(--on-surface-variant);
}

.recommended-divider {
  height: 1px;
  background: var(--outline-variant);
}
</style>
