<template>
  <div class="user-view">
    <!-- 未登录 -->
    <template v-if="!auth.isLoggedIn">
      <div class="user-view__empty">
        <div class="empty-card">
          <div class="empty-card__icon">
            <el-icon size="64"><User /></el-icon>
          </div>
          <h2>尚未登录</h2>
          <p>登录后可管理账户信息</p>
          <el-button type="primary" size="large" @click="$router.push('/login')">前往登录</el-button>
        </div>
      </div>
    </template>

    <!-- 已登录 -->
    <template v-else>
      <h1>用户中心</h1>

      <!-- 个人信息 -->
      <section class="card">
        <h3 class="card__title">个人信息</h3>
        <div class="info-grid">
          <div class="info-row">
            <span class="info-row__label">用户名</span>
            <span class="info-row__value">{{ auth.user?.username }}</span>
          </div>
          <div class="info-row">
            <span class="info-row__label">邮箱</span>
            <span class="info-row__value">{{ auth.user?.email || '未设置' }}</span>
          </div>
          <div class="info-row">
            <span class="info-row__label">角色</span>
            <span class="info-row__value">
              <span class="role-tag" :class="{ 'role-tag--admin': auth.isAdmin }">
                {{ auth.isAdmin ? '管理员' : '普通用户' }}
              </span>
            </span>
          </div>
          <div class="info-row">
            <span class="info-row__label">会员等级</span>
            <span class="info-row__value">
              <span class="member-tag" :class="`member-tag--${auth.membershipType}`">
                {{ membershipLabel }}
              </span>
            </span>
          </div>
          <div class="info-row">
            <span class="info-row__label">注册时间</span>
            <span class="info-row__value">{{ formatDate(auth.user?.created_at) }}</span>
          </div>
        </div>
      </section>

      <!-- 账户安全 -->
      <section class="card">
        <h3 class="card__title">账户安全</h3>
        <div class="info-grid">
          <div class="info-row info-row--action">
            <div class="info-row__text">
              <span class="info-row__label">修改密码</span>
              <span class="info-row__hint">定期更换密码可提升账户安全性</span>
            </div>
            <button class="action-btn action-btn--primary" v-ripple @click="showChangePwdDialog">
              修改
            </button>
          </div>
        </div>
      </section>

      <!-- 会话管理 -->
      <section class="card">
        <h3 class="card__title">会话管理</h3>
        <div class="info-row info-row--action">
          <div class="info-row__text">
            <span class="info-row__label">退出登录</span>
            <span class="info-row__hint">退出当前账户，返回未登录状态</span>
          </div>
          <button class="action-btn" v-ripple @click="handleLogout">退出</button>
        </div>
      </section>

      <!-- 危险操作 -->
      <section class="card card--danger">
        <h3 class="card__title" style="color: #ef4444">危险操作</h3>
        <p class="card__warning">
          <el-icon><WarningFilled /></el-icon>
          注销账户将永久删除您的所有个人数据，包括设置、歌单、播放统计等，且不可恢复
        </p>
        <button
          class="action-btn action-btn--danger"
          v-ripple
          @click="handleDeleteAccount"
          :disabled="auth.isAdmin"
        >
          注销账户
        </button>
        <p v-if="auth.isAdmin" class="card__hint">管理员账户不可自行注销</p>
      </section>
    </template>
  </div>
</template>

<script setup>
defineOptions({ name: 'UserView' })
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useModal } from '@/composables/useModal'
import { ElMessage } from '@/utils/toast'
import { User, WarningFilled } from '@element-plus/icons-vue'
import { useScrollMemory } from '@/composables/useScrollMemory'

const router = useRouter()
const auth = useAuthStore()
const modal = useModal()

useScrollMemory('user', () => document.querySelector('.main-content'))

const membershipLabel = computed(() => {
  const map = { free: '免费用户', vip: 'VIP 会员', svip: 'SVIP 会员' }
  return map[auth.membershipType] || '免费用户'
})

function formatDate(dateStr) {
  if (!dateStr) return '未知'
  try {
    return new Date(dateStr).toLocaleDateString('zh-CN', {
      year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit'
    })
  } catch { return dateStr }
}

async function handleLogout() {
  try {
    await modal.confirm({
      title: '退出登录',
      message: '确定要退出登录吗？',
      confirmText: '退出',
    })
    auth.logout()
    ElMessage.success('已退出登录')
    router.push('/')
  } catch {}
}

async function showChangePwdDialog() {
  try {
    const oldPwd = await modal.prompt({
      title: '修改密码',
      message: '请输入旧密码',
      confirmText: '下一步',
      inputType: 'password',
      inputPlaceholder: '旧密码'
    })
    if (!oldPwd) return

    const newPwd = await modal.prompt({
      title: '修改密码',
      message: '请输入新密码（至少6位）',
      confirmText: '确认修改',
      inputType: 'password',
      inputPlaceholder: '新密码',
      inputValidator: (v) => v && v.length >= 6 ? true : '密码至少6位'
    })
    if (!newPwd) return

    await auth.changePassword(oldPwd, newPwd)
    ElMessage.success('密码修改成功，请重新登录')
    auth.logout()
    router.push('/login')
  } catch (e) {
    if (e !== 'cancel' && e !== 'close') {
      ElMessage.error(e.message || '操作取消')
    }
  }
}

async function handleDeleteAccount() {
  try {
    await modal.confirm({
      title: '注销账户',
      message: '注销后所有个人数据将被永久删除且不可恢复。确定继续？',
      confirmText: '确认注销',
      danger: true
    })
    const pwd = await modal.prompt({
      title: '注销账户',
      message: '请输入密码确认注销',
      confirmText: '确认注销',
      inputType: 'password',
      inputPlaceholder: '输入密码'
    })
    if (!pwd) return
    await auth.deleteAccount(pwd)
    ElMessage.success('账户已注销')
    router.push('/')
  } catch (e) {
    if (e !== 'cancel' && e !== 'close') {
      ElMessage.error(e.message || '操作取消')
    }
  }
}
</script>

<style scoped>
.user-view { padding: 0 0 100px; }

.user-view > h1 { font-size: 28px; font-weight: 700; margin: 0 0 28px; letter-spacing: -0.3px; }

/* 未登录空状态 */
.user-view__empty {
  display: flex; align-items: center; justify-content: center;
  min-height: 60vh;
}
.empty-card { text-align: center; }
.empty-card__icon {
  display: inline-flex; align-items: center; justify-content: center;
  width: 112px; height: 112px; border-radius: 24px;
  background: linear-gradient(135deg, rgba(99,102,241,0.15), rgba(168,85,247,0.1));
  color: #818cf8; margin-bottom: 24px;
}
.empty-card h2 { font-size: 22px; font-weight: 700; margin: 0 0 8px; }
.empty-card p { font-size: 14px; color: var(--text-tertiary); margin: 0 0 24px; }

/* 卡片 */
.card {
  background: var(--bg-primary);
  border-radius: 14px; padding: 22px 26px;
  border: 1px solid var(--border-color);
  margin-bottom: 20px;
}
.card--danger { border-color: rgba(239, 68, 68, 0.25); }
.card__title {
  font-size: 16px; font-weight: 700; margin: 0 0 18px;
}
.card__warning {
  display: flex; align-items: flex-start; gap: 8px;
  font-size: 13px; color: #f87171; margin: 0 0 16px; line-height: 1.5;
}
.card__hint { font-size: 12px; color: var(--text-tertiary); margin: 8px 0 0; }

/* 信息行 */
.info-grid {
  display: flex; flex-direction: column;
}
.info-row {
  display: flex; align-items: center; justify-content: space-between;
  padding: 12px 0;
}
.info-row:not(:last-child) { border-bottom: 1px solid var(--border-color); }
.info-row__label { font-size: 13px; color: var(--text-tertiary); font-weight: 500; min-width: 70px; }
.info-row__value { font-size: 14px; color: var(--text-primary); font-weight: 600; text-align: right; }

.info-row--action {
  gap: 16px;
}
.info-row__text {
  display: flex; flex-direction: column; gap: 3px; flex: 1; min-width: 0;
}
.info-row__hint { font-size: 12px; color: var(--text-tertiary); line-height: 1.4; }

/* 角色/会员标签 */
.role-tag {
  display: inline-block; padding: 3px 10px; border-radius: 6px;
  font-size: 12px; font-weight: 600;
  background: var(--hover-bg); color: var(--text-secondary);
}
.role-tag--admin {
  background: rgba(251,146,60,0.15); color: #fb923c;
}
.member-tag {
  display: inline-block; padding: 3px 10px; border-radius: 6px;
  font-size: 12px; font-weight: 600;
}
.member-tag--free { background: var(--hover-bg); color: var(--text-tertiary); }
.member-tag--vip { background: rgba(59,130,246,0.15); color: #60a5fa; }
.member-tag--svip { background: rgba(239,68,68,0.15); color: #f87171; }

/* 操作按钮 */
.action-btn {
  padding: 8px 20px; border-radius: 9px;
  border: 1px solid var(--border-color);
  background: var(--bg-primary); color: var(--text-secondary);
  font-size: 13px; font-weight: 600; cursor: pointer;
  flex-shrink: 0;
  transition: all 0.15s ease;
  font-family: inherit;
}
.action-btn:hover {
  background: var(--hover-bg-strong); color: var(--text-primary);
}
.action-btn--primary {
  background: var(--accent-color); color: #fff; border-color: var(--accent-color);
}
.action-btn--primary:hover { opacity: 0.9; color: #fff; }
.action-btn--danger {
  color: #ef4444; border-color: rgba(239,68,68,0.3);
}
.action-btn--danger:hover {
  background: rgba(239,68,68,0.1); color: #ef4444;
}
.action-btn:disabled { opacity: 0.35; cursor: not-allowed; }
</style>
