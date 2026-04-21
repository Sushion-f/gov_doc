<script setup lang="ts">
import { Bell, Setting, User } from '@element-plus/icons-vue';
import { computed } from 'vue';
import { RouterLink, RouterView, useRoute } from 'vue-router';
// 暂时注释掉navigation store，因为我们需要创建对应的ts文件
// import { useNavigationStore } from '../stores/navigation';

const route = useRoute();
// 暂时移除navigation store的使用
// const navigationStore = useNavigationStore();

const navItems = [
  // { label: '警务飞度', path: '/police-latitude' },
  { label: '警务助手', path: '/chat' },
  { label: '接警助手', path: '/alarm-assistant' },
  { label: '警务分析', path: '/police-analytics' },
  { label: '警情预警', path: '/alert-warning' },
];

const currentPath = computed(() => route.path);

const isActive = (targetPath: string) =>
  currentPath.value === targetPath || currentPath.value.startsWith(`${targetPath}/`);

// 暂时注释掉watch，因为我们移除了navigation store的使用
// watch(
//   () => route.fullPath,
//   () => {
//     navigationStore.setVisitedPath(route.path);
//   },
//   { immediate: true },
// );
</script>

<template>
  <div class="layout">
    <!-- <header class="topbar">
      <div class="topbar-brand"></div>
      <nav class="topbar-mod-nav">
        <RouterLink v-for="item in navItems" :key="item.path" :to="item.path" class="nav-item" :class="{ active: isActive(item.path) }">
          {{ item.label }}
        </RouterLink>
      </nav>
      <div class="topbar-actions">
        <button class="topbar-icon-btn">
          <el-icon><Bell /></el-icon>
        </button>
        <button class="topbar-icon-btn">
          <el-icon><Setting /></el-icon>
        </button>
        <div class="topbar-avatar">
          <el-icon><User /></el-icon>
        </div>
      </div>
    </header> -->
    <main class="layout-content">
      <RouterView />
    </main>
  </div>
</template>

<style scoped>
/* ─── Topbar ────────────────────────────────────────────── */
.topbar {
  position: sticky;
  top: 0;
  z-index: 100;
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 32px;
  background: rgba(255, 255, 255, 0.68);
  border-bottom: 1px solid var(--line);
  backdrop-filter: blur(12px) saturate(140%);
  -webkit-backdrop-filter: blur(12px) saturate(140%);
  flex-shrink: 0;
}

.topbar-brand {
  height: 58px;
  width: 270px;
  background: url(@/assets/images/logo.png) no-repeat center;
}

.topbar-brand-logo {
  font-size: 18px;
  font-weight: 700;
  color: var(--primary);
  letter-spacing: -0.01em;
  font-family: 'Space Grotesk', sans-serif;
}

.topbar-brand-sub {
  font-size: 13px;
  font-weight: 500;
  color: var(--gray-500);
}

.topbar-mod-nav {
  display: flex;
  align-items: center;
  gap: 4px;
}

.topbar-mod-nav a {
  position: relative;
  display: inline-flex;
  align-items: center;
  padding: 6px 18px;
  border-radius: var(--radius-md);
  font-size: 14px;
  font-weight: 500;
  color: var(--gray-700);
  text-decoration: none;
  transition: 180ms var(--ease-out);
  white-space: nowrap;
}

.topbar-mod-nav a:hover {
  color: var(--primary);
  background: var(--primary-dim);
}

.topbar-mod-nav a.active {
  color: var(--primary);
  background: rgba(0, 47, 134, 0.1);
  font-weight: 600;
}

.topbar-mod-nav a.active::after {
  content: '';
  position: absolute;
  bottom: -1px;
  left: 18px;
  right: 18px;
  height: 2px;
  border-radius: 2px 2px 0 0;
  background: var(--primary);
}

.topbar-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.topbar-icon-btn {
  width: 36px;
  height: 36px;
  border-radius: var(--radius-md);
  border: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.6);
  color: var(--gray-700);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: 180ms var(--ease-out);
}

.topbar-icon-btn:hover {
  background: #fff;
  border-color: var(--primary-border);
  color: var(--primary);
}

.topbar-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: var(--primary-gradient);
  color: #fff;
  font-size: 14px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  flex-shrink: 0;
}

/* ─── Layout ────────────────────────────────────────────── */
.layout {
  display: flex;
  flex-direction: column;
  height: 100vh;
  overflow: hidden;
}

.layout-content {
  flex: 1;
  overflow: auto;
  background: transparent;
  /* 避免路由切换时滚动条出现/消失导致的横向抖动（Windows 上更明显） */
  scrollbar-gutter: stable;
}
</style>
