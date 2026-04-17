<script setup>
import { onMounted } from "vue";
import AppSidebar from "@/components/AppSidebar.vue";
import { bootstrapApp, state } from "@/store";

onMounted(() => {
  bootstrapApp();
});
</script>

<template>
  <div class="app-shell" :class="{ 'sidebar-collapsed': state.sidebarCollapsed }">
    <AppSidebar />
    <main class="main-shell">
      <div class="stage">
        <div v-if="state.errorMessage" class="banner-error">{{ state.errorMessage }}</div>
        <RouterView />
      </div>
    </main>
  </div>
</template>
