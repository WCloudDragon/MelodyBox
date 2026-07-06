<template>
  <div class="admin-page">
    <header class="admin-header">
      <div class="admin-header__left">
        <el-icon size="22"><Monitor /></el-icon>
        <h2>管理后台</h2>
        <span class="admin-badge">仅管理员可见</span>
      </div>
    </header>

    <div class="admin-grid">
      <!-- 左侧：云端曲库管理 -->
      <section class="admin-card admin-card--cloud">
        <div class="admin-card__header">
          <div class="admin-card__title">
            <el-icon size="18"><Cloudy /></el-icon>
            <span>云端曲库管理</span>
            <el-tag size="small" type="info">{{ cloudSongs.length }} 首</el-tag>
          </div>
        </div>

        <div class="admin-card__body">
          <!-- 添加歌曲区域 -->
          <div class="add-section">
            <h4>添加歌曲</h4>
            <p class="hint">选择音频文件（支持多选）或选择整个文件夹</p>

            <div v-if="pendingFiles.length > 0" class="pending-files">
              <div class="pending-files__header">
                <span>待添加 ({{ pendingFiles.length }})</span>
                <el-button text size="small" type="danger" @click="pendingFiles = []">清空</el-button>
              </div>
              <div class="pending-files__list">
                <div v-for="(f, i) in pendingFiles" :key="i" class="pending-file-item">
                  <el-icon size="14"><Document /></el-icon>
                  <span class="truncate">{{ f }}</span>
                  <el-button text size="small" @click="pendingFiles.splice(i, 1)">
                    <el-icon size="12"><Close /></el-icon>
                  </el-button>
                </div>
              </div>
            </div>

            <div class="add-row">
              <el-button @click="pickFiles">
                <el-icon size="14"><Document /></el-icon>
                选择音频文件
              </el-button>
              <el-button @click="pickFolder">
                <el-icon size="14"><FolderAdd /></el-icon>
                选择文件夹
              </el-button>
              <el-button
                type="primary"
                :loading="cloudLoading"
                :disabled="pendingFiles.length === 0"
                @click="addCloudSongs"
              >
                <el-icon size="14"><Plus /></el-icon>
                确认添加
              </el-button>
            </div>
            <p v-if="addResult" class="add-result" :class="addResultType">{{ addResult }}</p>
          </div>

          <!-- 歌曲列表 -->
          <div class="cloud-list">
            <div class="cloud-list__header">
              <span>曲库歌曲</span>
              <div class="cloud-list__header-right">
                <!-- 批量操作栏 -->
                <transition name="batch-bar-fade">
                  <div v-if="selectedSongs.length > 0" class="batch-bar">
                    <span class="batch-bar__count">已选 {{ selectedSongs.length }} 首</span>
                    <el-button size="small" @click="batchSetStatus('online')">批量上架</el-button>
                    <el-button size="small" @click="batchSetStatus('offline')">批量下架</el-button>
                    <el-button size="small" @click="batchSetGenre">批量流派</el-button>
                    <el-popconfirm
                      title="确定批量移除所选歌曲？"
                      confirm-button-text="移除"
                      cancel-button-text="取消"
                      @confirm="batchRemove"
                    >
                      <template #reference>
                        <el-button size="small" type="danger">批量移除</el-button>
                      </template>
                    </el-popconfirm>
                    <el-button size="small" text @click="clearSelection">取消选择</el-button>
                  </div>
                </transition>
                <el-button text size="small" @click="loadCloudData" :loading="cloudLoading">刷新</el-button>
              </div>
            </div>

            <el-table
              ref="tableRef"
              :data="cloudSongs"
              style="width: 100%"
              :max-height="400"
              size="small"
              stripe
              empty-text="云端曲库为空，请添加歌曲"
              v-loading="cloudLoading"
              @selection-change="onSelectionChange"
            >
              <el-table-column type="selection" width="36" />
              <el-table-column prop="title" label="标题" min-width="130" show-overflow-tooltip />
              <el-table-column prop="artist" label="艺术家" width="100" show-overflow-tooltip />
              <el-table-column prop="album" label="专辑" width="100" show-overflow-tooltip />
              <el-table-column prop="genre" label="流派" width="70" show-overflow-tooltip />
              <el-table-column label="状态" width="70">
                <template #default="{ row }">
                  <el-tag
                    size="small"
                    :type="row.status === 'online' ? 'success' : 'info'"
                    effect="dark"
                    style="cursor: pointer"
                    @click="toggleStatus(row)"
                  >
                    {{ row.status === 'online' ? '上架' : '下架' }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column label="时长" width="65">
                <template #default="{ row }">{{ formatDuration(row.duration) }}</template>
              </el-table-column>
              <el-table-column label="操作" width="120" fixed="right">
                <template #default="{ row }">
                  <el-button text size="small" @click="openEditDialog(row)">
                    <el-icon size="14"><Edit /></el-icon>
                  </el-button>
                  <el-popconfirm
                    title="确定移除此歌曲？"
                    confirm-button-text="移除"
                    cancel-button-text="取消"
                    @confirm="removeCloudSong(row.id)"
                  >
                    <template #reference>
                      <el-button text type="danger" size="small">
                        <el-icon size="14"><Delete /></el-icon>
                      </el-button>
                    </template>
                  </el-popconfirm>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </div>
      </section>

      <!-- 右侧上：网络模拟 -->
      <section class="admin-card">
        <div class="admin-card__header">
          <div class="admin-card__title">
            <el-icon size="18"><Connection /></el-icon>
            <span>网络模拟设置</span>
          </div>
        </div>
        <div class="admin-card__body">
          <p class="hint">控制用户播放云端歌曲时感受到的网络延迟</p>
          <div class="network-modes">
            <label
              v-for="m in cloudNetworkModes"
              :key="m.key"
              class="network-mode-card"
              :class="{ active: cloudNetworkMode === m.key }"
              @click="setCloudNetworkMode(m.key)"
            >
              <span class="network-mode-card__icon">{{ m.icon }}</span>
              <div class="network-mode-card__info">
                <strong>{{ m.label }}</strong>
                <small>{{ m.desc }}</small>
              </div>
              <span v-if="cloudNetworkMode === m.key" class="network-mode-card__check">
                <el-icon><Check /></el-icon>
              </span>
            </label>
          </div>
        </div>
      </section>

      <!-- 右侧下：系统信息 -->
      <section class="admin-card">
        <div class="admin-card__header">
          <div class="admin-card__title">
            <el-icon size="18"><InfoFilled /></el-icon>
            <span>系统信息</span>
          </div>
        </div>
        <div class="admin-card__body">
          <div class="info-grid">
            <div class="info-item">
              <span class="info-item__label">本地歌曲</span>
              <span class="info-item__value">{{ stats.localCount }} 首</span>
            </div>
            <div class="info-item">
              <span class="info-item__label">云端歌曲</span>
              <span class="info-item__value">{{ stats.cloudCount }} 首</span>
            </div>
            <div class="info-item">
              <span class="info-item__label">注册用户</span>
              <span class="info-item__value">{{ stats.userCount }} 人</span>
            </div>
            <div class="info-item">
              <span class="info-item__label">歌单数量</span>
              <span class="info-item__value">{{ stats.playlistCount }} 个</span>
            </div>
            <div class="info-item">
              <span class="info-item__label">当前网络模式</span>
              <span class="info-item__value accent">{{ currentModeLabel }}</span>
            </div>
          </div>
        </div>
      </section>
    </div>

    <!-- 元数据编辑弹窗 -->
    <el-dialog
      v-model="editDialogVisible"
      title="编辑云端歌曲元数据"
      width="520px"
      destroy-on-close
    >
      <div class="edit-dialog-body">
        <el-form label-position="top" size="small">
          <el-form-item label="标题">
            <el-input v-model="editForm.title" placeholder="留空恢复 mutagen 默认值" clearable />
            <template #extra><span class="edit-hint">默认: {{ editingSong?.original_title }}</span></template>
          </el-form-item>
          <el-form-item label="艺术家">
            <el-input v-model="editForm.artist" placeholder="留空恢复 mutagen 默认值" clearable />
            <template #extra><span class="edit-hint">默认: {{ editingSong?.original_artist || '无' }}</span></template>
          </el-form-item>
          <el-form-item label="专辑">
            <el-input v-model="editForm.album" placeholder="留空恢复 mutagen 默认值" clearable />
            <template #extra><span class="edit-hint">默认: {{ editingSong?.original_album || '无' }}</span></template>
          </el-form-item>
          <el-form-item label="流派">
            <el-input v-model="editForm.genre" placeholder="留空恢复 mutagen 默认值" clearable />
            <template #extra><span class="edit-hint">默认: {{ editingSong?.original_genre || '无' }}</span></template>
          </el-form-item>
          <el-form-item label="封面 URL">
            <el-input v-model="editForm.cover_url" placeholder="留空恢复 mutagen 封面" clearable />
          </el-form-item>
          <el-form-item label="歌词">
            <el-input v-model="editForm.lyrics" type="textarea" :rows="4" placeholder="留空则无歌词" clearable />
          </el-form-item>
        </el-form>
      </div>
      <template #footer>
        <el-button @click="editDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingMeta" @click="saveMetadata">保存</el-button>
      </template>
    </el-dialog>

    <!-- 批量流派弹窗 -->
    <el-dialog
      v-model="batchGenreVisible"
      title="批量设置流派"
      width="360px"
      destroy-on-close
    >
      <p style="margin: 0 0 12px; font-size: 13px; color: var(--text-secondary);">
        将为已选的 {{ selectedSongs.length }} 首歌曲统一设置流派
      </p>
      <el-input v-model="batchGenreValue" placeholder="输入流派，留空恢复 mutagen 默认" clearable />
      <template #footer>
        <el-button @click="batchGenreVisible = false">取消</el-button>
        <el-button type="primary" :loading="batchGenreLoading" @click="confirmBatchGenre">应用</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { useLibraryStore } from '@/stores/library'
import { usePlaylistStore } from '@/stores/playlist'
import { Monitor, Cloudy, Connection, InfoFilled, Plus, Delete, Check, FolderAdd, Document, Close, Edit } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

const libraryStore = useLibraryStore()
const playlistStore = usePlaylistStore()

const cloudSongs = ref([])
const cloudLoading = ref(false)
const cloudNetworkMode = ref('4g')
const cloudNetworkModes = ref([])
const pendingFiles = ref([])
const addResult = ref('')
const addResultType = ref('')

// 批量操作
const tableRef = ref(null)
const selectedSongs = ref([])
const batchGenreVisible = ref(false)
const batchGenreValue = ref('')
const batchGenreLoading = ref(false)

function onSelectionChange(rows) { selectedSongs.value = rows }
function clearSelection() { tableRef.value?.clearSelection() }

async function batchSetStatus(status) {
  const token = localStorage.getItem('auth-token')
  let done = 0
  for (const s of selectedSongs.value) {
    try {
      await fetch(`http://127.0.0.1:5000/api/cloud/songs/${s.id}/status`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify({ status })
      })
      done++
    } catch {}
  }
  await loadCloudData()
  await libraryStore.loadCloudSongs()
  clearSelection()
  ElMessage.success(`已${status === 'online' ? '上架' : '下架'} ${done} 首歌曲`)
}

function batchSetGenre() {
  batchGenreValue.value = ''
  batchGenreVisible.value = true
}

async function confirmBatchGenre() {
  const token = localStorage.getItem('auth-token')
  batchGenreLoading.value = true
  const genre = batchGenreValue.value.trim()
  const body = { genre: genre || null }
  let done = 0
  for (const s of selectedSongs.value) {
    try {
      await fetch(`http://127.0.0.1:5000/api/cloud/songs/${s.id}/metadata`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify(body)
      })
      done++
    } catch {}
  }
  batchGenreLoading.value = false
  batchGenreVisible.value = false
  await loadCloudData()
  clearSelection()
  ElMessage.success(`已为 ${done} 首歌曲设置流派`)
}

async function batchRemove() {
  const token = localStorage.getItem('auth-token')
  let done = 0
  for (const s of selectedSongs.value) {
    try {
      await fetch(`http://127.0.0.1:5000/api/cloud/songs/${s.id}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${token}` }
      })
      done++
    } catch {}
  }
  await loadCloudData()
  await libraryStore.loadCloudSongs()
  clearSelection()
  ElMessage.success(`已移除 ${done} 首歌曲`)
}

// 编辑弹窗
const editDialogVisible = ref(false)
const editingSong = ref(null)
const savingMeta = ref(false)
const editForm = reactive({
  title: '', artist: '', album: '', genre: '', cover_url: '', lyrics: ''
})

const stats = reactive({
  localCount: 0,
  cloudCount: 0,
  userCount: 0,
  playlistCount: 0,
})

const currentModeLabel = computed(() => {
  const mode = cloudNetworkModes.value.find(m => m.key === cloudNetworkMode.value)
  return mode ? mode.label : '未知'
})

function formatDuration(sec) {
  if (!sec) return '--:--'
  const m = Math.floor(sec / 60)
  const s = Math.floor(sec % 60)
  return `${m}:${String(s).padStart(2, '0')}`
}

function openEditDialog(song) {
  editingSong.value = song
  // 回显当前覆盖值（优先 custom_，回退空字符串表示未覆盖）
  editForm.title = song.custom_title || ''
  editForm.artist = song.custom_artist || ''
  editForm.album = song.custom_album || ''
  editForm.genre = song.custom_genre || ''
  editForm.cover_url = song.custom_cover_url || ''
  editForm.lyrics = song.custom_lyrics || ''
  editDialogVisible.value = true
}

async function saveMetadata() {
  if (!editingSong.value) return
  const token = localStorage.getItem('auth-token')
  savingMeta.value = true
  try {
    // 空字符串传 null 让后端恢复默认
    const body = {}
    for (const [k, v] of Object.entries(editForm)) {
      body[k] = (v && v.trim()) ? v.trim() : null
    }
    const res = await fetch(`http://127.0.0.1:5000/api/cloud/songs/${editingSong.value.id}/metadata`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify(body)
    })
    if (res.ok) {
      editDialogVisible.value = false
      await loadCloudData()
      ElMessage.success('元数据已更新')
    } else {
      const d = await res.json()
      ElMessage.error(d.error || '保存失败')
    }
  } catch (e) {
    ElMessage.error('请求失败')
  } finally {
    savingMeta.value = false
  }
}

async function toggleStatus(song) {
  const token = localStorage.getItem('auth-token')
  const newStatus = song.status === 'online' ? 'offline' : 'online'
  try {
    const res = await fetch(`http://127.0.0.1:5000/api/cloud/songs/${song.id}/status`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify({ status: newStatus })
    })
    if (res.ok) {
      await loadCloudData()
      await libraryStore.loadCloudSongs()
      ElMessage.success(`已${newStatus === 'online' ? '上架' : '下架'}`)
    }
  } catch (e) {
    ElMessage.error('操作失败')
  }
}

async function loadCloudData() {
  const token = localStorage.getItem('auth-token')
  cloudLoading.value = true
  try {
    const [songsRes, modeRes] = await Promise.all([
      fetch('http://127.0.0.1:5000/api/cloud/songs', {
        headers: token ? { 'Authorization': `Bearer ${token}` } : {}
      }),
      fetch('http://127.0.0.1:5000/api/cloud/network-mode', {
        headers: token ? { 'Authorization': `Bearer ${token}` } : {}
      })
    ])
    if (songsRes.ok) {
      const data = await songsRes.json()
      cloudSongs.value = data.songs || []
    }
    if (modeRes.ok) {
      const data = await modeRes.json()
      cloudNetworkMode.value = data.mode
      cloudNetworkModes.value = (data.modes || []).map(m => ({
        ...m,
        icon: modeIcons[m.key] || '🌐',
        desc: modeDescriptions[m.key] || '',
      }))
    }
  } catch (e) {
    ElMessage.error('数据加载失败')
  } finally {
    cloudLoading.value = false
  }
}

const modeIcons = { off: '⚡', '4g': '📶', '3g': '📱', slow: '🐢' }
const modeDescriptions = {
  off: '无延迟，感受不到网络差异',
  '4g': '模拟 4G 网络，300-800ms 随机延迟',
  '3g': '模拟 3G 网络，1-3s 随机延迟',
  slow: '模拟弱网环境，2-5s 随机延迟',
}

// ===== 文件选择 =====

async function pickFiles() {
  try {
    if (window.electronAPI?.selectAudioFiles) {
      const paths = await window.electronAPI.selectAudioFiles()
      if (paths && paths.length > 0) {
        const existing = new Set(pendingFiles.value)
        paths.forEach(p => existing.add(p))
        pendingFiles.value = [...existing]
      }
    } else {
      ElMessage.warning('文件选择器仅在桌面应用中可用')
    }
  } catch (e) {
    ElMessage.error('打开文件选择器失败')
  }
}

async function pickFolder() {
  try {
    if (window.electronAPI?.selectFolderForCloud) {
      const folderPath = await window.electronAPI.selectFolderForCloud()
      if (folderPath) {
        if (!pendingFiles.value.includes(folderPath)) {
          pendingFiles.value = [...pendingFiles.value, folderPath]
        }
      }
    } else {
      ElMessage.warning('文件选择器仅在桌面应用中可用')
    }
  } catch (e) {
    ElMessage.error('打开文件夹选择器失败')
  }
}

async function addCloudSongs() {
  const paths = [...pendingFiles.value]
  if (paths.length === 0) {
    ElMessage.warning('请先选择文件或文件夹')
    return
  }
  const token = localStorage.getItem('auth-token')
  cloudLoading.value = true
  addResult.value = ''
  try {
    const res = await fetch('http://127.0.0.1:5000/api/cloud/songs', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify({ file_paths: paths })
    })
    const data = await res.json()
    if (res.ok) {
      addResult.value = data.message
      addResultType.value = 'success'
      pendingFiles.value = []
      await loadCloudData()
      await libraryStore.loadCloudSongs()
      ElMessage.success(data.message)
    } else {
      addResult.value = data.error || '添加失败'
      addResultType.value = 'error'
      ElMessage.error(addResult.value)
    }
  } catch (e) {
    addResult.value = '请求失败'
    addResultType.value = 'error'
    ElMessage.error('请求失败')
  } finally {
    cloudLoading.value = false
  }
}

async function removeCloudSong(id) {
  const token = localStorage.getItem('auth-token')
  try {
    const res = await fetch(`http://127.0.0.1:5000/api/cloud/songs/${id}`, {
      method: 'DELETE',
      headers: { 'Authorization': `Bearer ${token}` }
    })
    if (res.ok) {
      await loadCloudData()
      await libraryStore.loadCloudSongs()
      ElMessage.success('已移除')
    }
  } catch (e) {
    ElMessage.error('移除失败')
  }
}

async function setCloudNetworkMode(mode) {
  const token = localStorage.getItem('auth-token')
  try {
    const res = await fetch('http://127.0.0.1:5000/api/cloud/network-mode', {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify({ mode })
    })
    if (res.ok) {
      cloudNetworkMode.value = mode
      ElMessage.success(`已切换至 ${modeIcons[mode]} ${cloudNetworkModes.value.find(m => m.key === mode)?.label}`)
    }
  } catch (e) {
    ElMessage.error('切换失败')
  }
}

async function loadStats() {
  try {
    const songsRes = await fetch('http://127.0.0.1:5000/api/music/songs?page=1&page_size=1&source=cloud')
    const usersRes = await fetch('http://127.0.0.1:5000/api/auth/users')

    // 本地计数
    try {
      const lr = await fetch('http://127.0.0.1:5000/api/music/songs?page=1&page_size=1&source=local')
      if (lr.ok) { const d = await lr.json(); stats.localCount = d.total || 0 }
    } catch {}
    if (songsRes.ok) { const d = await songsRes.json(); stats.cloudCount = d.total || 0 }
    if (usersRes.ok) { const d = await usersRes.json(); stats.userCount = (d.users || []).length }
    stats.playlistCount = playlistStore.playlists?.length || 0
  } catch {}
}

onMounted(() => {
  loadCloudData()
  loadStats()
})

watch(() => playlistStore.playlists, () => {
  stats.playlistCount = playlistStore.playlists?.length || 0
})
</script>

<style scoped>
.admin-page {
  flex: 1;
  overflow-y: auto;
  padding: 24px 32px;
}

.admin-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 28px;
}

.admin-header__left {
  display: flex;
  align-items: center;
  gap: 10px;
  color: var(--text-primary);
}

.admin-header__left h2 {
  margin: 0;
  font-size: 22px;
  font-weight: 700;
}

.admin-badge {
  font-size: 11px;
  padding: 3px 8px;
  border-radius: 6px;
  background: rgba(251, 146, 60, 0.12);
  color: #fb923c;
  font-weight: 600;
  letter-spacing: 0.5px;
}

.admin-grid {
  display: grid;
  grid-template-columns: 1fr 360px;
  gap: 20px;
  align-items: start;
}

.admin-card {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 14px;
  overflow: hidden;
}

.admin-card--cloud {
  grid-row: span 2;
}

.admin-card__header {
  padding: 18px 20px 0;
}

.admin-card__title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}

.admin-card__body {
  padding: 16px 20px 20px;
}

.hint {
  margin: 0 0 12px 0;
  font-size: 12px;
  color: var(--text-tertiary);
}

/* 待添加文件列表 */
.pending-files {
  margin-bottom: 12px;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  overflow: hidden;
}

.pending-files__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  background: var(--bg-tertiary);
  font-size: 12px;
  color: var(--text-secondary);
}

.pending-files__list {
  max-height: 160px;
  overflow-y: auto;
}

.pending-file-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  font-size: 12px;
  color: var(--text-primary);
  border-bottom: 1px solid var(--border-color);
}

.pending-file-item:last-child {
  border-bottom: none;
}

.pending-file-item .truncate {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 添加区域 */
.add-section {
  margin-bottom: 20px;
  padding-bottom: 20px;
  border-bottom: 1px solid var(--border-color);
}

.add-section h4 {
  margin: 0 0 4px 0;
  font-size: 14px;
}

.add-row {
  display: flex;
  gap: 10px;
  align-items: center;
}

.add-result {
  margin: 8px 0 0;
  font-size: 12px;
}

.add-result.success { color: #22c55e; }
.add-result.error { color: #ef4444; }

/* 歌曲列表 */
.cloud-list__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
  font-size: 13px;
  color: var(--text-secondary);
}

.cloud-list__header-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.batch-bar {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  background: var(--accent-bg);
  border: 1px solid var(--accent-color);
  border-radius: 8px;
  transition: opacity 0.2s;
}

.batch-bar__count {
  font-size: 12px;
  font-weight: 600;
  color: var(--accent-color);
  margin-right: 4px;
}

.batch-bar-fade-enter-active,
.batch-bar-fade-leave-active { transition: opacity 0.2s; }
.batch-bar-fade-enter-from,
.batch-bar-fade-leave-to { opacity: 0; }

/* 网络模式卡片 */
.network-modes {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.network-mode-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  border-radius: 10px;
  border: 1px solid var(--border-color);
  background: var(--bg-tertiary);
  cursor: pointer;
  transition: all 0.2s;
}

.network-mode-card:hover {
  background: var(--hover-bg-strong);
}

.network-mode-card.active {
  border-color: var(--accent-color);
  background: var(--accent-bg);
}

.network-mode-card__icon {
  font-size: 22px;
  width: 36px;
  text-align: center;
  flex-shrink: 0;
}

.network-mode-card__info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.network-mode-card__info strong {
  font-size: 13px;
  color: var(--text-primary);
}

.network-mode-card__info small {
  font-size: 11px;
  color: var(--text-tertiary);
}

.network-mode-card__check {
  color: var(--accent-color);
  font-size: 18px;
}

/* 系统信息 */
.info-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 10px 12px;
  border-radius: 8px;
  background: var(--bg-tertiary);
}

.info-item__label {
  font-size: 11px;
  color: var(--text-tertiary);
}

.info-item__value {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-primary);
}

.info-item__value.accent {
  color: var(--accent-color);
}

/* 编辑弹窗 */
.edit-dialog-body {
  max-height: 60vh;
  overflow-y: auto;
  padding-right: 4px;
}

.edit-hint {
  font-size: 11px;
  color: var(--text-tertiary);
}
</style>
