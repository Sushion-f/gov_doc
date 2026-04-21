<template>
  <RouterView />
</template>

<script setup lang="ts">
import { onMounted } from 'vue';
import { useRouter } from 'vue-router';

const router = useRouter();

onMounted(() => {
  // 检查本地存储中是否有token
  const token = localStorage.getItem('token');
  if (!token) {
    // 如果没有token，重定向到登录页
    // router.push('/login')
  }
});
</script>
