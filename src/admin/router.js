import { createRouter, createWebHashHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const routes = [
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/LoginView.vue'),
    props: { minimal: true },
    meta: { title: '管理员登录' },
  },
  {
    path: '/',
    name: 'dashboard',
    component: () => import('@/views/AdminView.vue'),
    meta: { title: '管理后台', requiresAuth: true, requiresAdmin: true },
  },
  {
    path: '/folders',
    name: 'folders',
    component: () => import('@/admin/views/FoldersAdmin.vue'),
    meta: { title: '文件夹管理', requiresAuth: true, requiresAdmin: true },
  },
]

const router = createRouter({
  history: createWebHashHistory(),
  routes,
})

router.beforeEach((to) => {
  const auth = useAuthStore()
  document.title = to.meta.title ? `${to.meta.title} - MelodyBox` : 'MelodyBox 管理后台'

  // 需要登录：跳登录页并记录来源
  if (to.meta.requiresAuth && !auth.isLoggedIn) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }
  // 需要管理员：非管理员回登录页
  if (to.meta.requiresAdmin && !auth.isAdmin) {
    return { path: '/login', replace: true }
  }
  // 已登录管理员访问登录页：直达管理台
  if (to.name === 'login' && auth.isLoggedIn && auth.isAdmin) {
    return { path: '/', replace: true }
  }
})

export default router
