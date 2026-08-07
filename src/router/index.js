import { createRouter, createWebHashHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const routes = [
  {
    path: '/',
    name: 'home',
    component: () => import('@/views/HomeView.vue'),
    meta: { title: '首页' }
  },
  {
    path: '/library',
    name: 'library',
    component: () => import('@/views/LibraryView.vue'),
    meta: { title: '音乐库' }
  },
  {
    path: '/albums',
    name: 'albums',
    component: () => import('@/views/AlbumsView.vue'),
    meta: { title: '专辑' }
  },
  {
    path: '/artists',
    name: 'artists',
    component: () => import('@/views/ArtistsView.vue'),
    meta: { title: '艺术家' }
  },
  {
    path: '/album/:id?',
    name: 'album',
    component: () => import('@/views/AlbumView.vue'),
    meta: { title: '专辑' }
  },
  {
    path: '/artist/:name?',
    name: 'artist',
    component: () => import('@/views/ArtistView.vue'),
    meta: { title: '歌手' }
  },
  {
    path: '/playlist/:id?',
    name: 'playlist',
    component: () => import('@/views/PlaylistView.vue'),
    meta: { title: '歌单' }
  },
  {
    path: '/settings',
    name: 'settings',
    component: () => import('@/views/SettingsView.vue'),
    meta: { title: '设置' }
  },
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/LoginView.vue'),
    meta: { title: '登录' }
  },
  {
    path: '/user',
    name: 'user',
    component: () => import('@/views/UserView.vue'),
    meta: { title: '用户中心', requiresAuth: true }
  },
  {
    path: '/folders',
    name: 'folders',
    component: () => import('@/views/FoldersView.vue'),
    meta: { title: '文件夹管理' }
  },
  {
    path: '/history',
    name: 'history',
    component: () => import('@/views/HistoryView.vue'),
    meta: { title: '播放历史' }
  },
  {
    path: '/top-plays',
    name: 'topPlays',
    component: () => import('@/views/TopPlaysView.vue'),
    meta: { title: '播放次数' }
  },
  {
    path: '/track-info',
    name: 'trackInfo',
    component: () => import('@/views/TrackInfoView.vue'),
    meta: { title: '音轨信息' }
  },
  {
    path: '/recommend',
    name: 'recommend',
    component: () => import('@/views/RecommendPlaylistView.vue'),
    meta: { title: '推荐' }
  },
  {
    path: '/desktop-lyrics',
    name: 'desktopLyrics',
    component: () => import('@/views/DesktopLyricsView.vue'),
    meta: { title: '桌面歌词' }
  },
  {
    path: '/rhythm-debug',
    name: 'rhythmDebug',
    component: () => import('@/views/RhythmDebugView.vue'),
    meta: { title: '律动日志' }
  }
]

const router = createRouter({
  history: createWebHashHistory(),
  routes
})

router.beforeEach((to) => {
  const auth = useAuthStore()
  document.title = to.meta.title ? `${to.meta.title} - MelodyBox` : 'MelodyBox'

  // 需要登录的页面：未登录跳转登录页，并记录来源
  if (to.meta.requiresAuth && !auth.isLoggedIn) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }
  // 需要管理员权限的页面：非管理员回到首页
  if (to.meta.requiresAdmin && !auth.isAdmin) {
    return { path: '/', replace: true }
  }
  // 已登录用户访问登录页：回到首页
  if (to.path === '/login' && auth.isLoggedIn) {
    return { path: '/', replace: true }
  }
})

export default router
