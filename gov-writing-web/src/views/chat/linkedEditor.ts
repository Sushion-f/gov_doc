import type { InjectionKey, Ref } from 'vue';

export interface LinkedEditorHost {
  open: (step: Step) => void;
  close: () => void;
  /** 当前在右侧编辑的步骤（与左侧为同引用时左侧 TinyMCE 只读，避免双实例争用） */
  activeStep: Ref<Step | null>;
  isOpen: Ref<boolean>;
}

export const LINKED_EDITOR_KEY: InjectionKey<LinkedEditorHost> = Symbol('policeBrainLinkedEditor');
