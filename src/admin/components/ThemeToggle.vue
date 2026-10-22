<template>
  <div class="theme-toggle" :class="{ 'theme-toggle--floating': floating }" role="group" aria-label="外观主题">
    <button
      v-for="opt in options"
      :key="opt.value"
      type="button"
      class="theme-toggle__btn"
      :class="{ 'is-active': themeMode === opt.value }"
      :title="opt.label"
      @click="setThemeMode(opt.value)"
    >
      <el-icon :size="15"><component :is="opt.icon" /></el-icon>
    </button>
  </div>
</template>

<script setup>
import { Sunny, Moon, Monitor } from '@element-plus/icons-vue'
import { themeMode, setThemeMode } from '../theme'

defineProps({
  // 登录页无管理壳时使用右上角悬浮样式
  floating: { type: Boolean, default: false }
})

const options = [
  { value: 'light', label: '浅色模式', icon: Sunny },
  { value: 'dark', label: '深色模式', icon: Moon },
  { value: 'system', label: '跟随系统', icon: Monitor }
]
</script>

<style scoped>
.theme-toggle {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  padding: 2px;
  border-radius: 8px;
  background: var(--bg-tertiary);
  border: 1px solid var(--border-color);
}
.theme-toggle--floating {
  position: fixed;
  top: 16px;
  right: 16px;
  z-index: 20;
  background: var(--bg-secondary);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.18);
}
.theme-toggle__btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 26px;
  padding: 0;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: var(--text-tertiary);
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}
.theme-toggle__btn:hover {
  background: var(--hover-bg);
  color: var(--text-primary);
}
.theme-toggle__btn.is-active {
  background: var(--accent-bg);
  color: var(--accent-color);
}
</style>
