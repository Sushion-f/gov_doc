import { createRouter, createWebHistory } from "vue-router";
import HomeView from "@/views/HomeView.vue";
import WorkspaceView from "@/views/WorkspaceView.vue";
import EditorView from "@/views/EditorView.vue";
import SettingsView from "@/views/SettingsView.vue";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", name: "home", component: HomeView },
    { path: "/workspace", name: "workspace", component: WorkspaceView },
    { path: "/editor/:id?", name: "editor", component: EditorView, props: true },
    { path: "/settings", name: "settings", component: SettingsView },
  ],
});

export default router;
