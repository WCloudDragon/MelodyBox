<template>
  <div id="admin-app">
    <!-- 登录页：无管理壳 -->
    <router-view v-if="isLoginRoute" />

    <!-- 管理壳：顶栏 + 内容区 -->
    <div v-else class="admin-shell">
      <header class="admin-topbar">
        <div class="admin-topbar__brand">
          <el-icon size="20"><Monitor /></el-icon>
          <span>MelodyBox 管理后台</span>
          <el-tag size="small" type="warning" effect="dark">B/S 管理端</el-tag>
        </div>
        <nav class="admin-topbar__nav">
          <router-link to="/" class="admin-nav-link" :class="{ active: route.path === '/' }">云端曲库</router-link>
          <router-link to="/folders" class="admin-nav-link" :class="{ active: route.path === '/folders' }">文件夹管理</router-link>
        </nav>
        <div class="admin-topbar__user" v-if="auth.isLoggedIn">
          <el-icon><UserFilled /></el-icon>
          <span class="admin-topbar__username">{{ auth.user?.username }}</span>
          <el-button size="small" text @click="handleLogout">退出登录</el-button>
        </div>
      </header>
      <main class="admin-main">
        <router-view />
      </main>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const isLoginRoute = computed(() => route.name === 'login')

function handleLogout() {
  auth.logout()
  router.push('/login')
}
</script>

<style>
html, body, #admin-app {
  height: 100%;
  margin: 0;
}
.admin-shell {
  display: flex;
  flex-direction: column;
  height: 100%;
}
.admin-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  height: 52px;
  flex-shrink: 0;
  background: var(--bg-secondary);
  border-bottom: 1px solid var(--border-color);
}
.admin-topbar__brand {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 700;
}
.admin-topbar__user {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--text-secondary);
}
.admin-topbar__nav {
  display: flex;
  align-items: center;
  gap: 4px;
}
.admin-nav-link {
  padding: 5px 14px;
  border-radius: 6px;
  color: var(--text-secondary);
  text-decoration: none;
  font-size: 13px;
  transition: background 0.15s, color 0.15s;
}
.admin-nav-link:hover {
  background: var(--hover-bg);
}
.admin-nav-link.active {
  background: var(--bg-tertiary);
  color: var(--text-primary);
  font-weight: 600;
}
.admin-topbar__username {
  font-weight: 600;
}
.admin-main {
  flex: 1;
  overflow: auto;
  padding: 20px;
  background: var(--bg-primary);
}
</style>
