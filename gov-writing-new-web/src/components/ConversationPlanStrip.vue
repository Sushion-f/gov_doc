<script setup>
import { computed } from "vue";

const props = defineProps({
  todoList: {
    type: Object,
    default: null,
  },
  waitingInput: {
    type: Object,
    default: null,
  },
});

const steps = computed(() => props.todoList?.steps || []);
const currentStepId = computed(() => props.todoList?.current_step_id || props.todoList?.currentStepId || null);

function stepStatus(step) {
  if (!step) {
    return "pending";
  }
  return step.status || (step.id === currentStepId.value ? "running" : "pending");
}
</script>

<template>
  <div v-if="todoList || waitingInput" class="plan-strip-wrap">
    <section v-if="todoList?.steps?.length" class="plan-strip">
      <div class="plan-strip-head">
        <div class="plan-strip-title">任务计划</div>
        <div class="plan-strip-summary">{{ todoList.summary || "主流程已整理当前执行步骤。" }}</div>
      </div>
      <div class="plan-strip-list">
        <div
          v-for="step in steps"
          :key="step.id"
          class="plan-step"
          :class="[`is-${stepStatus(step)}`]"
        >
          <span class="plan-step-icon material-symbols-rounded">
            {{
              stepStatus(step) === "completed"
                ? "check_circle"
                : stepStatus(step) === "running"
                ? "progress_activity"
                : stepStatus(step) === "failed"
                ? "error"
                : "radio_button_unchecked"
            }}
          </span>
          <div class="plan-step-copy">
            <div class="plan-step-title">{{ step.title }}</div>
            <div class="plan-step-agent">{{ step.agent_label || step.agentLabel || "执行专家" }}</div>
          </div>
        </div>
      </div>
    </section>

    <section v-if="waitingInput" class="plan-waiting">
      <div class="plan-waiting-title">继续执行前需要补充信息</div>
      <div class="plan-waiting-question">
        {{ waitingInput.question || "请先补充必要信息后继续执行。" }}
      </div>
      <ul v-if="waitingInput.missing_fields?.length" class="plan-waiting-list">
        <li v-for="field in waitingInput.missing_fields" :key="field.key">
          {{ field.label || field.hint || field.key }}
        </li>
      </ul>
    </section>
  </div>
</template>

<style scoped>
.plan-strip-wrap {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 14px;
}

.plan-strip,
.plan-waiting {
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: 18px;
  background: #fff;
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.04);
  padding: 14px 16px;
}

.plan-strip-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}

.plan-strip-title,
.plan-waiting-title {
  font-size: 15px;
  font-weight: 700;
  color: #1f2937;
}

.plan-strip-summary,
.plan-waiting-question {
  font-size: 13px;
  color: #6b7280;
}

.plan-strip-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.plan-step {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 14px;
  background: #f8fafc;
}

.plan-step.is-running {
  background: #eff6ff;
}

.plan-step.is-completed {
  background: #f0fdf4;
}

.plan-step.is-failed {
  background: #fef2f2;
}

.plan-step-icon {
  font-size: 18px;
  color: #6b7280;
}

.plan-step.is-running .plan-step-icon {
  color: #2563eb;
}

.plan-step.is-completed .plan-step-icon {
  color: #16a34a;
}

.plan-step.is-failed .plan-step-icon {
  color: #dc2626;
}

.plan-step-title {
  font-size: 14px;
  font-weight: 600;
  color: #111827;
}

.plan-step-agent {
  margin-top: 2px;
  font-size: 12px;
  color: #6b7280;
}

.plan-waiting-list {
  margin: 10px 0 0;
  padding-left: 18px;
  color: #4b5563;
}
</style>
