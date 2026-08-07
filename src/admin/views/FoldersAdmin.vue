<template>
  <div class="folders-admin">
    <header class="folders-admin__header">
      <el-icon size="22"><FolderOpened /></el-icon>
      <h2>文件夹管理</h2>
      <span class="hint">管理服务器上的音乐扫描目录（B/S 管理端）</span>
    </header>

    <!-- 添加扫描目录 -->
    <section class="admin-card">
      <div class="admin-card__header">
        <span>添加扫描目录</span>
      </div>
      <div class="admin-card__body">
        <div class="add-row">
          <el-input
            v-model="pathInput"
            placeholder="输入服务器目录绝对路径，或使用下方目录浏览器"
            clearable
            style="flex: 1"
            @keyup.enter="addPath()"
          />
          <el-button type="primary" :loading="adding" :disabled="!pathInput.trim()" @click="addPath()">
            <el-icon size="14"><Plus /></el-icon>
            添加
          </el-button>
        </div>

        <!-- 服务器目录浏览器 -->
        <div class="browser">
          <div class="browser__toolbar">
            <el-button size="small" text :disabled="!browse.parent" @click="browseTo(browse.parent)">
              ⬆ 上级
            </el-button>
            <span class="browser__path">{{ browse.path || '（盘符根目录）' }}</span>
            <el-button size="small" type="success" :disabled="!browse.path" @click="addPath(browse.path)">
              选择此目录
            </el-button>
          </div>
          <div class="browser__list">
            <div
              v-for="d in browse.subdirs"
              :key="d"
              class="browser__item"
              @click="browseTo(d)"
            >
              <el-icon size="14"><Folder /></el-icon>
              <span class="truncate">{{ displayName(d) }}</span>
            </div>
            <div v-if="browse.loading" class="browser__empty">加载中...</div>
            <div v-else-if="browse.subdirs.length === 0" class="browser__empty">没有子目录</div>
          </div>
        </div>
      </div>
    </section>

    <!-- 扫描进度 -->
    <section v-if="scanning" class="admin-card">
      <div class="admin-card__header"><span>正在扫描...</span></div>
      <div class="admin-card__body">
        <el-progress :percentage="progressPct" />
        <p class="hint">{{ scanProgress.path || '正在分析文件...' }}</p>
      </div>
    </section>

    <!-- 已添加目录 -->
    <section class="admin-card">
      <div class="admin-card__header">
        <span>已添加目录（{{ folders.length }}）</span>
        <el-button size="small" text @click="loadFolders">刷新</el-button>
      </div>
      <div class="admin-card__body">
        <div v-for="f in folders" :key="f.id" class="folder-item">
          <el-icon size="16"><FolderOpened /></el-icon>
          <div class="folder-item__info">
            <div class="folder-item__path">{{ f.path }}</div>
            <div class="folder-item__meta">{{ f.trackCount }} 首 · {{ formatDuration(f.totalDuration) }}</div>
          </div>
          <el-button size="small" text @click="rescanFolder(f.id)">重新扫描</el-button>
          <el-button size="small" text type="danger" @click="removeFolder(f.id)">移除</el-button>
        </div>
        <div v-if="folders.length === 0" class="browser__empty">暂无扫描目录</div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { apiUrl, authHeaders } from '@/config/api'

const folders = ref([])
const adding = ref(false)
const pathInput = ref('')
const scanProgress = ref({ scanning: false, current: 0, total: 0, path: '', inserted: 0, updated: 0, deleted: 0 })
const browse = ref({ path: '', parent: null, subdirs: [], loading: false })

const scanning = computed(() => scanProgress.value.scanning)
const progressPct = computed(() => {
  const { current, total } = scanProgress.value
  if (!total) return 0
  return Math.min(100, Math.round((current / total) * 100))
})

function _headers() {
  return authHeaders(localStorage.getItem('auth-token'))
}

async function loadFolders() {
  try {
    const res = await fetch(apiUrl('/api/folders'), { headers: _headers() })
    if (res.ok) folders.value = await res.json()
  } catch {}
}

async function loadScanProgress() {
  try {
    const res = await fetch(apiUrl('/api/folders/scan-progress'))
    if (res.ok) scanProgress.value = await res.json()
  } catch {}
}

async function addPath(path) {
  const target = (path || pathInput.value || '').trim()
  if (!target) return
  adding.value = true
  try {
    const res = await fetch(apiUrl('/api/folders'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ..._headers() },
      body: JSON.stringify({ path: target }),
    })
    const data = await res.json()
    if (res.ok) {
      ElMessage.success(data.message || '已开始扫描')
      pathInput.value = ''
      loadFolders()
    } else {
      ElMessage.error(data.error || '添加失败')
    }
  } catch {
    ElMessage.error('请求失败')
  } finally {
    adding.value = false
  }
}

async function browseTo(path) {
  browse.value.loading = true
  try {
    const url = path
      ? `${apiUrl('/api/folders/browse')}?path=${encodeURIComponent(path)}`
      : apiUrl('/api/folders/browse')
    const res = await fetch(url, { headers: _headers() })
    const data = await res.json()
    if (res.ok) {
      browse.value.path = data.path
      browse.value.parent = data.parent
      browse.value.subdirs = data.subdirs || []
    } else {
      ElMessage.error(data.error || '浏览失败')
    }
  } catch {
    ElMessage.error('请求失败')
  } finally {
    browse.value.loading = false
  }
}

function displayName(p) {
  const parts = p.replace(/[\\/]+$/, '').split(/[\\/]/)
  return parts[parts.length - 1] || p
}

async function rescanFolder(id) {
  try {
    const res = await fetch(apiUrl(`/api/folders/${id}/rescan`), {
      method: 'POST',
      headers: _headers(),
    })
    const data = await res.json()
    if (res.ok) ElMessage.success(data.message || '开始重新扫描')
    else ElMessage.error(data.error || '操作失败')
  } catch {
    ElMessage.error('请求失败')
  }
}

async function removeFolder(id) {
  try {
    await ElMessageBox.confirm('移除后该目录下的歌曲记录将被删除，确定继续？', '移除目录', {
      type: 'warning',
      confirmButtonText: '移除',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  try {
    const res = await fetch(apiUrl(`/api/folders/${id}`), {
      method: 'DELETE',
      headers: _headers(),
    })
    const data = await res.json()
    if (res.ok) {
      ElMessage.success(data.message || '已移除')
      loadFolders()
    } else {
      ElMessage.error(data.error || '移除失败')
    }
  } catch {
    ElMessage.error('请求失败')
  }
}

function formatDuration(sec) {
  if (!sec) return '--:--:--'
  const h = Math.floor(sec / 3600)
  const m = Math.floor((sec % 3600) / 60)
  const s = Math.floor(sec % 60)
  return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

let pollTimer = null
onMounted(() => {
  loadFolders()
  loadScanProgress()
  browseTo('')
  pollTimer = setInterval(async () => {
    await loadScanProgress()
    if (!scanProgress.value.scanning) {
      // 扫描结束刷新目录统计
      loadFolders()
    }
  }, 2000)
})

onBeforeUnmount(() => {
  if (pollTimer) clearInterval(pollTimer)
})
</script>

<style scoped>
.folders-admin__header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 20px;
}
.folders-admin__header h2 {
  margin: 0;
  font-size: 22px;
}
.hint {
  font-size: 12px;
  color: var(--text-tertiary);
}

.add-row {
  display: flex;
  gap: 10px;
  margin-bottom: 16px;
}

.browser {
  border: 1px solid var(--border-color);
  border-radius: 10px;
  overflow: hidden;
}
.browser__toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  background: var(--bg-secondary);
  border-bottom: 1px solid var(--border-color);
}
.browser__path {
  flex: 1;
  font-size: 12px;
  color: var(--text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  direction: rtl;
  text-align: left;
}
.browser__list {
  max-height: 220px;
  overflow-y: auto;
}
.browser__item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  font-size: 13px;
  cursor: pointer;
  border-bottom: 1px solid var(--border-color);
  transition: background 0.15s;
}
.browser__item:hover {
  background: var(--hover-bg);
}
.browser__empty {
  padding: 16px;
  text-align: center;
  font-size: 12px;
  color: var(--text-tertiary);
}

.folder-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 4px;
  border-bottom: 1px solid var(--border-color);
}
.folder-item:last-child {
  border-bottom: none;
}
.folder-item__info {
  flex: 1;
  min-width: 0;
}
.folder-item__path {
  font-size: 13px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.folder-item__meta {
  font-size: 12px;
  color: var(--text-tertiary);
}
</style>
