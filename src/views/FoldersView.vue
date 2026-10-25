<template>
  <div class="folders-view">
    <div class="folders-view__header">
      <h1>文件夹管理</h1>
      <div class="folders-view__actions">
        <el-button
          class="rescan-all-btn"
          @click="handleRescanAll"
          :disabled="folders.length === 0"
        >
          重新扫描全部
        </el-button>
        <el-button class="add-folder-btn" type="primary" @click="handleAddFolder" :loading="adding" :disabled="!isElectron">
          <el-icon><Plus /></el-icon> 添加文件夹
        </el-button>
      </div>
    </div>

    <p v-if="!isElectron" class="tip">请使用桌面版管理音乐文件夹</p>

    <!-- 统计 -->
    <div class="stats-row" v-if="folders.length > 0">
      <span class="stats-text">共 {{ folders.length }} 个文件夹 · {{ totalTracks }} 首歌曲</span>
    </div>

    <!-- 加载中 -->
    <div v-if="loading" class="loading-state">
      <el-icon class="loading-icon" size="28"><Loading /></el-icon>
      <p>加载中...</p>
    </div>

    <!-- 空状态 -->
    <div v-else-if="folders.length === 0" class="empty-state">
      <el-icon size="48"><FolderOpened /></el-icon>
      <h2>尚未添加音乐文件夹</h2>
      <p>点击「添加文件夹」导入本地音乐</p>
    </div>

    <!-- 文件夹列表 -->
    <div v-else class="folder-list">
      <div
        v-for="folder in folders"
        :key="folder.id"
        class="folder-card"
      >
        <div class="folder-card__icon">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
            <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
          </svg>
        </div>
        <div class="folder-card__info">
          <div class="folder-card__path" :title="folder.path">{{ folder.path }}</div>
          <div class="folder-card__meta">
            <span>{{ folder.trackCount }} 首</span>
            <span>{{ formatDuration(folder.totalDuration) }}</span>
          </div>
        </div>
        <div class="folder-card__actions">
          <el-button text circle size="small" class="folder-rescan" @click="handleRescan(folder)" title="重新扫描">
            <el-icon><Refresh /></el-icon>
          </el-button>
          <el-button
            text
            circle
            size="small"
            type="danger"
            @click="handleRemove(folder)"
            :disabled="libraryStore.isScanning"
            :title="libraryStore.isScanning ? '扫描中不可移除文件夹' : '移除'"
          >
            <el-icon><Delete /></el-icon>
          </el-button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
defineOptions({ name: 'FoldersView' })
import { ref, computed, onMounted, watch } from 'vue'
import { useLibraryStore } from '@/stores/library'
import { useModal } from '@/composables/useModal'
import { ElMessage } from '@/utils/toast'
import { Plus, Refresh, Delete, FolderOpened, Loading } from '@element-plus/icons-vue'
import { useScrollMemory } from '@/composables/useScrollMemory'

import { apiUrl } from '@/config/api'
const libraryStore = useLibraryStore()
const modal = useModal()
const isElectron = computed(() => !!window.electronAPI)

const folders = ref([])
const loading = ref(true)
const adding = ref(false)

useScrollMemory('folders', () => document.querySelector('.main-content'))

const totalTracks = computed(() => folders.value.reduce((s, f) => s + f.trackCount, 0))

function formatDuration(sec) {
  if (!sec || sec <= 0) return '0分钟'
  const m = Math.floor(sec / 60)
  if (m < 60) return `${m}分钟`
  const h = Math.floor(m / 60)
  return `${h}小时${m % 60}分钟`
}

async function loadFolders() {
  loading.value = true
  try {
    const res = await fetch(apiUrl('/api/folders'))
    if (res.ok) folders.value = await res.json()
  } catch { /* 无后端时静默 */ }
  loading.value = false
}

async function handleAddFolder() {
  adding.value = true
  try {
    // 与音乐库空态共用同一条添加路径（选择目录 → 入库 → 全局扫描进度）
    await libraryStore.addFolders()
  } finally {
    adding.value = false
  }
}

async function handleRescan(folder) {
  try {
    await modal.confirm({
      title: '重新扫描',
      message: `重新扫描 ${folder.path}？`,
      confirmText: '确认',
    })
    await libraryStore.rescanFolder(folder.id)
  } catch (e) {
    if (e !== 'cancel' && e !== 'close') ElMessage.error(e.message || '扫描失败')
  }
}

async function handleRescanAll() {
  try {
    await modal.confirm({
      title: '重新扫描全部',
      message: `将按添加顺序依次重新扫描全部 ${folders.value.length} 个文件夹。`,
      confirmText: '开始扫描',
    })
    await libraryStore.rescanAllFolders()
  } catch (e) {
    if (e !== 'cancel' && e !== 'close') ElMessage.error(e.message || '扫描启动失败')
  }
}

async function handleRemove(folder) {
  if (libraryStore.isScanning) {
    ElMessage.warning('扫描进行中，暂不可移除文件夹')
    return
  }
  try {
    await modal.confirm({
      title: '确认移除',
      message: `确定移除「${folder.path}」吗？\n该目录下的 ${folder.trackCount} 首歌曲将从库中清除。`,
      confirmText: '确认移除',
      danger: true
    })
    const res = await fetch(apiUrl(`/api/folders/${folder.id}`), { method: 'DELETE' })
    const data = await res.json()
    if (!res.ok) { ElMessage.error(data.error); return }
    ElMessage.success(data.message)
    await loadFolders()
    libraryStore.loadFromApi()
  } catch (e) {
    if (e !== 'cancel' && e !== 'close') ElMessage.error(e.message || '移除失败')
  }
}

onMounted(loadFolders)

// 扫描结束后重新拉取文件夹统计（曲目数/时长）
watch(() => libraryStore.foldersVersion, loadFolders)
</script>

<style scoped>
.folders-view { padding: 0 0 100px; }

.folders-view__header {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 28px;
}
.folders-view__header h1 { font-size: 28px; font-weight: 700; margin: 0; letter-spacing: -0.3px; }
.folders-view__actions { display: flex; align-items: center; gap: 10px; }

/* 「重新扫描全部」：描边按钮（与顶栏同规格）；与主操作同高保证一行对齐 */
.rescan-all-btn {
  --el-button-bg-color: transparent;
  --el-button-border-color: var(--border-color);
  --el-button-text-color: var(--text-secondary);
  --el-button-hover-bg-color: var(--hover-bg-strong);
  --el-button-hover-border-color: var(--border-color);
  --el-button-hover-text-color: var(--text-primary);
  --el-button-active-bg-color: var(--hover-bg-strong);
  --el-button-active-border-color: var(--border-color);
  height: 34px;
  border-radius: 8px;
}
.add-folder-btn { height: 34px; border-radius: 8px; }

.tip { font-size: 13px; color: var(--text-tertiary); margin: -16px 0 24px; }

/* 统计 */
.stats-row { margin-bottom: 20px; }
.stats-text { font-size: 13px; color: var(--text-tertiary); }

/* 加载 / 空状态 */
.loading-state, .empty-state {
  display: flex; flex-direction: column; align-items: center;
  padding: 80px 0; color: var(--text-tertiary); gap: 12px;
}
.loading-icon { animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.empty-state h2 { font-size: 18px; margin: 0; color: var(--text-secondary); }
.empty-state p { font-size: 13px; margin: 0; }

/* 文件夹卡片 */
.folder-list {
  display: flex; flex-direction: column; gap: 8px;
}
.folder-card {
  display: flex; align-items: center; gap: 14px;
  background: var(--bg-primary); border: 1px solid var(--border-color);
  border-radius: 12px; padding: 14px 18px;
  transition: border-color 0.15s;
}
.folder-card:hover { border-color: var(--accent-color); }

.folder-card__icon {
  display: flex; align-items: center; justify-content: center;
  width: 44px; height: 44px; border-radius: 10px;
  background: rgba(59,130,246,0.12); color: #60a5fa;
  flex-shrink: 0;
}
.folder-card__info {
  flex: 1; min-width: 0;
  display: flex; flex-direction: column; gap: 4px;
}
.folder-card__path {
  font-size: 14px; font-weight: 600; color: var(--text-primary);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.folder-card__meta {
  display: flex; gap: 12px;
  font-size: 12px; color: var(--text-tertiary);
}
.folder-card__actions {
  display: flex; gap: 2px; flex-shrink: 0;
}
</style>
