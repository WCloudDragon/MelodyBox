<template>
  <div class="login-view">
    <div class="login-card">
      <div class="login-card__logo">
        <img :src="appIcon" alt="MelodyBox" draggable="false" />
      </div>
      <h2 class="login-card__title">{{ minimal ? '管理员登录' : (isLogin ? '欢迎回来' : '创建账户') }}</h2>
      <p class="login-card__desc">{{ minimal ? '请使用管理员账户登录管理后台' : (isLogin ? '登录你的 MelodyBox 账户' : '注册一个新账户以使用全部功能') }}</p>

      <form class="login-form" @submit.prevent="handleSubmit">
        <div class="form-field">
          <label>用户名</label>
          <input v-model="username" type="text" placeholder="输入用户名" required autocomplete="username" />
        </div>
        <div class="form-field">
          <label>密码</label>
          <input v-model="password" type="password" placeholder="输入密码" required autocomplete="current-password" />
        </div>
        <div class="form-field" v-if="!isLogin">
          <label>邮箱（可选）</label>
          <input v-model="email" type="email" placeholder="your@email.com" />
        </div>

        <p class="form-error" v-if="errorMsg">{{ errorMsg }}</p>

        <button class="btn-submit" type="submit" :disabled="loading">
          {{ loading ? '请稍候...' : isLogin ? '登录' : '注册' }}
        </button>
      </form>

      <p class="login-card__switch" v-if="!minimal">
        {{ isLogin ? '还没有账户？' : '已有账户？' }}
        <a href="#" @click.prevent="toggleMode">{{ isLogin ? '立即注册' : '去登录' }}</a>
      </p>
      <p class="login-card__skip" v-if="!minimal">
        <a href="#" @click.prevent="$router.push('/')">跳过登录，离线使用</a>
      </p>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import appIcon from '@/assets/app-icon-128.png'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

const props = defineProps({
  minimal: { type: Boolean, default: false },
})

const isLogin = ref(true)
const username = ref('')
const password = ref('')
const email = ref('')
const errorMsg = ref('')
const loading = ref(false)

function toggleMode() {
  isLogin.value = !isLogin.value
  errorMsg.value = ''
}

async function handleSubmit() {
  errorMsg.value = ''
  loading.value = true
  try {
    if (isLogin.value) {
      await auth.login(username.value, password.value)
    } else {
      await auth.register(username.value, password.value, email.value)
      // 注册成功后自动登录
      await auth.login(username.value, password.value)
    }
    router.push(route.query.redirect || '/')
  } catch (e) {
    errorMsg.value = e.message || '操作失败'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-view {
  display: flex; align-items: center; justify-content: center;
  min-height: 100%; padding: 40px 0;
}
.login-card {
  width: 380px; max-width: 100%;
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: 18px;
  padding: 40px 36px;
  text-align: center;
}
.login-card__logo {
  display: inline-flex; align-items: center; justify-content: center;
  width: 64px; height: 64px; border-radius: 16px;
  overflow: hidden; margin-bottom: 20px;
}
.login-card__logo img {
  width: 100%; height: 100%; object-fit: contain; display: block;
}
.login-card__title { font-size: 22px; font-weight: 700; margin: 0 0 6px; }
.login-card__desc { font-size: 13px; color: var(--text-tertiary); margin: 0 0 28px; }

.login-form { text-align: left; }
.form-field { margin-bottom: 16px; }
.form-field label {
  display: block; font-size: 13px; font-weight: 600;
  color: var(--text-secondary); margin-bottom: 6px;
}
.form-field input {
  width: 100%; padding: 10px 14px;
  background: var(--hover-bg); border: 1px solid var(--border-color);
  border-radius: 10px; color: var(--text-primary); font-size: 14px;
  outline: none; transition: border-color 0.2s;
  box-sizing: border-box;
}
.form-field input:focus { border-color: var(--accent-color); }

.form-error {
  color: #ef4444; font-size: 13px; margin: 0 0 12px;
}

.btn-submit {
  width: 100%; padding: 12px;
  background: var(--accent-color); color: #fff;
  border: none; border-radius: 10px; font-size: 15px; font-weight: 600;
  cursor: pointer; transition: opacity 0.2s;
}
.btn-submit:hover { opacity: 0.9; }
.btn-submit:disabled { opacity: 0.5; cursor: not-allowed; }

.login-card__switch { margin-top: 20px; font-size: 13px; color: var(--text-tertiary); }
.login-card__switch a { color: var(--accent-color); text-decoration: none; font-weight: 600; }
.login-card__skip { margin-top: 12px; }
.login-card__skip a { font-size: 12px; color: var(--text-tertiary); text-decoration: none; }
.login-card__skip a:hover { color: var(--text-secondary); }
</style>
