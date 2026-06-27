import { createRouter, createWebHashHistory } from 'vue-router'

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
    meta: { title: '用户中心' }
  },
  {
    path: '/folders',
    name: 'folders',
    component: () => import('@/views/FoldersView.vue'),
    meta: { title: '文件夹管理' }
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
  document.title = to.meta.title ? `${to.meta.title} - MelodyBox` : 'MelodyBox'
})

export default router
