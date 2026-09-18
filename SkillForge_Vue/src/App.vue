<template>
  <router-view></router-view>
</template>

<script setup lang="ts">
import { onMounted } from 'vue';
import { useAuthStore } from '@/store/authStore';

const authStore = useAuthStore();

onMounted(() => {
  authStore.checkAuthStatus();
});
</script>

<style>
#app {
  font-family: Avenir, Helvetica, Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  text-align: center;
  color: var(--theme-page-text);
  min-height: 100vh;
}

body, html {
  margin: 0;
  padding: 0;
  height: 100%;
}
</style>
