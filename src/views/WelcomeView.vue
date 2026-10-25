<template>
  <div class="welcome">
    <button class="welcome__skip" v-ripple @click="finish(true)">跳过</button>

    <Transition :name="transitionName" mode="out-in">
      <section :key="step" class="welcome__step">
        <!-- 1. 欢迎 -->
        <template v-if="step === 0">
          <div class="welcome__logo">
            <img :src="appIcon" alt="MelodyBox" draggable="false" />
          </div>
          <h1 class="welcome__title">欢迎使用 MelodyBox</h1>
          <p class="welcome__desc">AI 驱动的沉浸式音乐播放器</p>
          <ul class="welcome__features">
            <li>顶尖动效 · 流畅动画与沉浸式界面设计</li>
            <li>双模态 AI 推荐 · 情绪与天气场景</li>
            <li>逐字歌词 · 独立透明桌面歌词窗口</li>
          </ul>
          <div class="welcome__actions">
            <button class="welcome-btn welcome-btn--primary" v-ripple @click="goStep(1)">开始设置</button>
          </div>
        </template>

        <!-- 2. 外观 -->
        <template v-else-if="step === 1">
          <h1 class="welcome__title">选择外观</h1>
          <p class="welcome__desc">随时可以在「设置 → 外观」里修改</p>

          <div class="mode-grid">
            <button
              v-for="m in MODES"
              :key="m.value"
              class="mode-card"
              :class="{ active: settingsStore.theme === m.value }"
              v-ripple
              @click="setTheme(m.value)"
            >
              <span class="mode-card__preview" :class="`mode-card__preview--${m.value}`">
                <span class="mode-card__bar"></span>
                <span class="mode-card__line"></span>
                <span class="mode-card__line mode-card__line--short"></span>
              </span>
              <span class="mode-card__label">{{ m.label }}</span>
            </button>
          </div>

          <div class="appearance-group">
            <div class="sys-accent" @click="toggleSystemAccent">
              <span class="sys-accent__label">跟随系统主题色</span>
              <el-switch v-model="settingsStore.followSystemTheme" :disabled="!isElectron" />
            </div>

            <div class="accent-collapse" :class="{ 'is-open': !settingsStore.followSystemTheme }">
              <div class="accent-collapse__inner" :inert="settingsStore.followSystemTheme">
                <div class="accent">
                  <div class="accent__title">主题色</div>
                  <div class="accent__row">
                    <button
                      v-for="c in ACCENT_PRESETS"
                      :key="c"
                      class="swatch"
                      :class="{ active: sameColor(c) }"
                      :style="{ background: c }"
                      :title="c"
                      @click="setAccent(c)"
                    ></button>
                    <label class="swatch swatch--custom" :class="{ active: isCustomAccent }" :style="{ background: settingsStore.customAccentColor }" title="自定义颜色" @click="onCustomSwatchClick">
                      <input type="color" :value="settingsStore.customAccentColor" @input="onCustomAccent" />
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M12 20h9"/><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4z"/>
                      </svg>
                    </label>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div class="welcome__actions">
            <button class="welcome-btn" v-ripple @click="goStep(0)">上一步</button>
            <button class="welcome-btn welcome-btn--primary" v-ripple @click="goStep(2)">下一步</button>
          </div>
        </template>

        <!-- 3. 导入音乐 -->
        <template v-else>
          <h1 class="welcome__title">导入你的音乐</h1>
          <p class="welcome__desc">选择音乐所在的文件夹，MelodyBox 会自动扫描曲目、读取标签并生成封面</p>

          <div class="import-card">
            <div class="import-card__info">
              <span class="import-card__label">音乐文件夹</span>
              <span class="import-card__value">{{ folderSummary }}</span>
            </div>
            <button
              class="welcome-btn"
              v-ripple
              :disabled="picking || !isElectron"
              @click="pickFolder"
            >{{ isElectron ? '添加文件夹' : '请使用桌面版' }}</button>
          </div>

          <p class="welcome__hint">也可以稍后再添加，在「文件夹」页随时导入更多音乐</p>

          <div class="welcome__actions">
            <button class="welcome-btn" v-ripple @click="goStep(1)">上一步</button>
            <button class="welcome-btn welcome-btn--primary" v-ripple @click="finish()">进入 MelodyBox</button>
          </div>
        </template>
      </section>
    </Transition>

    <div class="welcome__dots">
      <button
          v-for="i in 3"
          :key="i"
          class="dot"
          :class="{ active: step === i - 1 }"
          @click="goStep(i - 1)"
        ></button>
    </div>
  </div>
</template>

<script setup>
defineOptions({ name: 'WelcomeView' })
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useSettingsStore } from '@/stores/settings'
import { useLibraryStore } from '@/stores/library'
import { ONBOARDED_KEY } from '@/router'
import { ACCENT_PRESETS } from '@/data/accentPresets'
import appIcon from '@/assets/app-icon-256.png'

const route = useRoute()
const router = useRouter()
const settingsStore = useSettingsStore()
const libraryStore = useLibraryStore()

const step = ref(0)
// 步骤切换方向：前进从右侧滑入，后退从左侧滑入（对应「下一步/上一步」）
const direction = ref(1)
const transitionName = computed(() => (direction.value > 0 ? 'step-forward' : 'step-back'))
const picking = ref(false)
const isElectron = computed(() => !!window.electronAPI)
// 从「关于 → 重新查看引导」进入：完成后返回原页面
const isReplay = computed(() => route.query.replay === '1')

const MODES = [
  { label: '浅色', value: 'light' },
  { label: '深色', value: 'dark' },
  { label: '跟随系统', value: 'system' }
]

const folderSummary = computed(() => {
  const n = libraryStore.scanDirs.length
  return n > 0 ? `已添加 ${n} 个文件夹` : '尚未选择'
})

function sameColor(c) {
  return (settingsStore.accentColor || '').toLowerCase() === c.toLowerCase()
}

// 当前颜色不在预设里 → 自定义色块显示选中环
const isCustomAccent = computed(() =>
  !settingsStore.followSystemTheme && !ACCENT_PRESETS.some((c) => sameColor(c))
)

function goStep(n) {
  if (n === step.value) return
  direction.value = n > step.value ? 1 : -1
  step.value = n
}

function setTheme(v) {
  settingsStore.theme = v
  settingsStore.saveSettings()
}

function setAccent(c) {
  // 手动选色即退出「跟随系统主题色」，否则选色不会生效
  settingsStore.followSystemTheme = false
  settingsStore.accentColor = c
  settingsStore.saveSettings()
}

function onCustomAccent(e) {
  // 记住本次自定义色，之后切换预设色也不丢失
  settingsStore.customAccentColor = e.target.value
  setAccent(e.target.value)
}

// 已在用自定义色时点击 → 打开取色器调整；否则直接应用上次的自定义色
function onCustomSwatchClick(e) {
  const usingCustom = !settingsStore.followSystemTheme &&
    (settingsStore.accentColor || '').toLowerCase() === (settingsStore.customAccentColor || '').toLowerCase()
  if (usingCustom) return
  e.preventDefault()
  setAccent(settingsStore.customAccentColor)
}

// 整行可点：开关本体不接收点击，避免切换两次
function toggleSystemAccent() {
  if (!isElectron.value) return
  settingsStore.followSystemTheme = !settingsStore.followSystemTheme
}

async function pickFolder() {
  if (picking.value) return
  picking.value = true
  try {
    await libraryStore.addFolders()
  } finally {
    picking.value = false
  }
}

function finish(skip = false) {
  settingsStore.saveSettingsImmediate()
  try { localStorage.setItem(ONBOARDED_KEY, '1') } catch {}
  if (isReplay.value && window.history.state?.back) {
    router.back()
    return
  }
  router.replace('/')
}

function onKeydown(e) {
  if (e.key === 'Escape') { finish(true); return }
  if (e.key === 'ArrowRight' && step.value < 2) goStep(step.value + 1)
  if (e.key === 'ArrowLeft' && step.value > 0) goStep(step.value - 1)
}

onMounted(() => window.addEventListener('keydown', onKeydown))
onBeforeUnmount(() => window.removeEventListener('keydown', onKeydown))
</script>

<style scoped>
.welcome {
  position: relative;
  min-height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 56px 32px 44px;
}
/* 顶部一层主题色晕染，跟随主题色实时变化 */
.welcome::before {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  /* 回退：不支持 color-mix 时仍用基础晕染 */
  background: radial-gradient(720px 420px at 50% 0%, var(--accent-bg), transparent 70%);
  /* 内层高亮光核 + 外层扩散光晕，让顶部光效更明显 */
  background:
    radial-gradient(460px 240px at 50% -4%, color-mix(in srgb, var(--accent-color) 30%, transparent), transparent 70%),
    radial-gradient(900px 430px at 50% 0%, color-mix(in srgb, var(--accent-color) 15%, transparent), transparent 72%);
}

.welcome__skip {
  position: absolute;
  /* 让开顶部 36px 的悬浮窗控条 */
  top: 46px;
  right: 22px;
  height: 30px;
  padding: 0 14px;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: var(--text-tertiary);
  font-size: 13px;
  cursor: pointer;
  transition: background 0.15s ease, color 0.15s ease;
}
.welcome__skip:hover { background: var(--hover-bg); color: var(--text-primary); }

.welcome__step {
  position: relative;
  width: 100%;
  max-width: 560px;
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
}

.welcome__logo img {
  width: 88px;
  height: 88px;
  border-radius: 22px;
  display: block;
}
.welcome__title {
  margin: 22px 0 8px;
  font-size: 30px;
  font-weight: 700;
  letter-spacing: -0.5px;
  color: var(--text-primary);
}
.welcome__desc {
  margin: 0;
  font-size: 14px;
  color: var(--text-tertiary);
}

.welcome__features {
  margin: 26px 0 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 10px;
  font-size: 13px;
  color: var(--text-secondary);
}
.welcome__features li::before {
  content: '';
  display: inline-block;
  width: 5px;
  height: 5px;
  margin-right: 10px;
  border-radius: 50%;
  background: var(--accent-color);
  vertical-align: middle;
}

.welcome__actions {
  margin-top: 34px;
  display: flex;
  gap: 12px;
}

.welcome-btn {
  height: 40px;
  padding: 0 22px;
  border-radius: 10px;
  border: 1px solid var(--border-color);
  background: transparent;
  color: var(--text-primary);
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.15s ease, border-color 0.15s ease, color 0.15s ease;
}
.welcome-btn:hover { background: var(--hover-bg-strong); }
.welcome-btn:disabled { opacity: 0.5; cursor: default; }
.welcome-btn--primary {
  background: var(--accent-color);
  border-color: var(--accent-color);
  color: #fff;
}
.welcome-btn--primary:hover {
  background: color-mix(in srgb, var(--accent-color) 88%, #fff);
  border-color: color-mix(in srgb, var(--accent-color) 88%, #fff);
}

/* ---- 主题模式卡片 ---- */
.mode-grid {
  margin-top: 26px;
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  width: 100%;
}
.mode-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding: 12px;
  border-radius: 12px;
  border: 1px solid var(--border-color);
  background: var(--hover-bg);
  cursor: pointer;
  transition: border-color 0.15s ease, background 0.15s ease;
}
.mode-card:hover { background: var(--hover-bg-strong); }
.mode-card.active { border-color: var(--accent-color); background: var(--accent-bg); }
.mode-card__preview {
  width: 100%;
  height: 74px;
  border-radius: 8px;
  /* 不描边：描边会在浅/深色分界处形成多余的边缘色 */
  border: none;
  overflow: hidden;
  background: var(--bg-tertiary);
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 10px;
}
.mode-card__preview--light { background: #f7f7f8; }
.mode-card__preview--dark { background: #1d1d20; }
.mode-card__preview--system {
  /* 与浅色/深色图标同一结构（色条 + 两条灰线），只用左右分色表达"跟随系统"；
     竖直切分不会像对角切分那样在单条边上留下半截异色 */
  background: linear-gradient(90deg, #f7f7f8 0 50%, #1d1d20 50% 100%);
}
.mode-card__bar {
  height: 8px;
  width: 42%;
  border-radius: 4px;
  background: var(--accent-color);
}
.mode-card__line {
  height: 6px;
  border-radius: 3px;
  background: rgba(128, 128, 128, 0.28);
}
.mode-card__line--short { width: 62%; }
.mode-card__label { font-size: 13px; color: var(--text-secondary); }
.mode-card.active .mode-card__label { color: var(--text-primary); }

/* ---- 主题色 ---- */
/* 两行共用同一宽度容器：开关行的 hover 底板与色板（含选中色环外扩 4px）视觉齐平 */
.appearance-group {
  width: 100%;
  max-width: 376px;
  margin: 0 auto;
}
.sys-accent {
  position: relative;
  /* 与色板内容严格同宽同起点：左边缘对齐第一个色块，右边缘对齐最后一个色块 */
  width: calc(100% - 10px);
  margin: 18px 5px 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 0;
  cursor: pointer;
}
/* hover 底板单独向外扩 10px，既有呼吸空间，又不影响文字的静态对齐 */
.sys-accent::before {
  content: '';
  position: absolute;
  inset: 0 -10px;
  border-radius: 10px;
  background: transparent;
  pointer-events: none;
  transition: background 0.15s ease;
}
.sys-accent:hover::before { background: var(--hover-bg); }
/* 整行负责切换，开关本体不接收点击，避免翻转两次 */
.sys-accent :deep(.el-switch) { pointer-events: none; }
.sys-accent__label { font-size: 13px; color: var(--text-secondary); }

/* 跟随系统时色板整块收起（grid-template-rows 0fr ↔ 1fr 高度动画） */
.accent-collapse {
  width: 100%;
  display: grid;
  grid-template-rows: 0fr;
  opacity: 0;
  transition: grid-template-rows 0.3s cubic-bezier(0.2, 0.9, 0.3, 1.0),
              opacity 0.22s ease;
}
.accent-collapse.is-open { grid-template-rows: 1fr; opacity: 1; }
.accent-collapse__inner {
  min-height: 0; overflow: hidden;
  /* 左右留 5px 给选中色环外扩，避免被高度动画的 overflow 裁掉 */
  padding: 0 5px;
}

.accent {
  margin: 0;
  padding: 16px 0 8px;
  width: 100%;
}
.accent__title {
  font-size: 13px;
  color: var(--text-tertiary);
  text-align: center;
  margin-bottom: 10px;
}
.accent__row {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  flex-wrap: wrap;
}
.swatch {
  position: relative;
  width: 30px;
  height: 30px;
  border-radius: 50%;
  border: none;
  cursor: pointer;
  transition: transform 0.15s cubic-bezier(0.34, 1.56, 0.64, 1), box-shadow 0.15s ease;
}
.swatch:hover { transform: scale(1.08); }
.swatch.active {
  box-shadow: 0 0 0 2px var(--bg-secondary), 0 0 0 4px var(--accent-color);
}
.swatch--custom {
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  overflow: hidden;
}
.swatch--custom input {
  position: absolute;
  inset: 0;
  opacity: 0;
  cursor: pointer;
}

/* ---- 导入音乐 ---- */
.import-card {
  margin-top: 28px;
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 16px 18px;
  border-radius: 12px;
  border: 1px solid var(--border-color);
  background: var(--hover-bg);
}
.import-card__info {
  display: flex;
  flex-direction: column;
  gap: 4px;
  text-align: left;
  min-width: 0;
}
.import-card__label { font-size: 13px; color: var(--text-tertiary); }
.import-card__value { font-size: 14px; color: var(--text-primary); }
.welcome__hint {
  margin: 14px 0 0;
  font-size: 12px;
  color: var(--text-tertiary);
}

/* ---- 步骤指示 ---- */
.welcome__dots {
  position: relative;
  margin-top: 38px;
  display: flex;
  gap: 8px;
}
.dot {
  width: 7px;
  height: 7px;
  padding: 0;
  border: none;
  border-radius: 50%;
  background: var(--border-color);
  cursor: pointer;
  transition: background 0.2s ease, width 0.2s ease;
}
.dot.active { width: 18px; border-radius: 4px; background: var(--accent-color); }

/* ---- 步骤切换（方向感知）：前进从右滑入、后退从左滑入 ---- */
.step-forward-enter-active,
.step-forward-leave-active,
.step-back-enter-active,
.step-back-leave-active {
  transition: opacity 0.28s ease, transform 0.28s cubic-bezier(0.2, 0.9, 0.3, 1.0);
}
.step-forward-enter-from { opacity: 0; transform: translateX(26px); }
.step-forward-leave-to { opacity: 0; transform: translateX(-26px); }
.step-back-enter-from { opacity: 0; transform: translateX(-26px); }
.step-back-leave-to { opacity: 0; transform: translateX(26px); }
</style>
