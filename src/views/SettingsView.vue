<template>
  <div class="settings-view">
    <!-- 一级菜单页 -->
    <template v-if="page === 'menu'">
      <h1>设置</h1>
      <div class="menu-list">
        <button class="menu-item" v-ripple @click="page = 'appearance'">
          <div class="menu-item__left">
            <span class="menu-item__icon" style="background: rgba(99,102,241,0.15); color: #818cf8">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                <path d="M12 2.69l5.66 5.66a8 8 0 1 1-11.31 0z"/>
              </svg>
            </span>
            <div class="menu-item__text">
              <span class="menu-item__title">外观</span>
              <span class="menu-item__desc">主题、主题色、模糊效果</span>
            </div>
          </div>
          <svg class="menu-item__arrow" width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M8.59 16.59L13.17 12 8.59 7.41 10 6l6 6-6 6z"/></svg>
        </button>
        <button class="menu-item" v-ripple @click="page = 'player'">
          <div class="menu-item__left">
            <span class="menu-item__icon" style="background: rgba(34,197,94,0.15); color: #4ade80">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                <path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/>
              </svg>
            </span>
            <div class="menu-item__text">
              <span class="menu-item__title">播放界面</span>
              <span class="menu-item__desc">歌词显示、动画效果开关</span>
            </div>
          </div>
          <svg class="menu-item__arrow" width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M8.59 16.59L13.17 12 8.59 7.41 10 6l6 6-6 6z"/></svg>
        </button>
        <button class="menu-item" @click="page = 'lyricStyle'">
          <div class="menu-item__left">
            <span class="menu-item__icon" style="background: rgba(251,146,60,0.15); color: #fb923c">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="4 7 4 4 20 4 20 7"/><line x1="9" y1="20" x2="15" y2="20"/><line x1="12" y1="4" x2="12" y2="20"/>
              </svg>
            </span>
            <div class="menu-item__text">
              <span class="menu-item__title">歌词排版</span>
              <span class="menu-item__desc">字号、字重、翻译比例、活跃行放大</span>
            </div>
          </div>
          <svg class="menu-item__arrow" width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M8.59 16.59L13.17 12 8.59 7.41 10 6l6 6-6 6z"/></svg>
        </button>
        <button class="menu-item" @click="page = 'desktopLyric'">
          <div class="menu-item__left">
            <span class="menu-item__icon" style="background: rgba(168,85,247,0.15); color: #a855f7">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                <rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/>
              </svg>
            </span>
            <div class="menu-item__text">
              <span class="menu-item__title">桌面歌词</span>
              <span class="menu-item__desc">独立窗口字号、放大比例、翻译比例</span>
            </div>
          </div>
          <svg class="menu-item__arrow" width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M8.59 16.59L13.17 12 8.59 7.41 10 6l6 6-6 6z"/></svg>
        </button>
        <button class="menu-item" @click="page = 'system'">
          <div class="menu-item__left">
            <span class="menu-item__icon" style="background: rgba(148,163,184,0.15); color: #94a3b8">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>
              </svg>
            </span>
            <div class="menu-item__text">
              <span class="menu-item__title">系统</span>
              <span class="menu-item__desc">自动扫描、语言</span>
            </div>
          </div>
          <svg class="menu-item__arrow" width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M8.59 16.59L13.17 12 8.59 7.41 10 6l6 6-6 6z"/></svg>
        </button>
        <button class="menu-item" v-ripple @click="page = 'about'">
          <div class="menu-item__left">
            <span class="menu-item__icon" style="background: rgba(56,189,248,0.15); color: #38bdf8">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/>
              </svg>
            </span>
            <div class="menu-item__text">
              <span class="menu-item__title">关于</span>
              <span class="menu-item__desc">版本信息、技术栈、致谢</span>
            </div>
          </div>
          <svg class="menu-item__arrow" width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M8.59 16.59L13.17 12 8.59 7.41 10 6l6 6-6 6z"/></svg>
        </button>
      </div>
    </template>

    <!-- 二级页：外观 -->
    <template v-if="page === 'appearance'">
      <header class="sub-header">
        <button class="sub-header__back" v-ripple @click="page = 'menu'">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M15.41 7.41L14 6l-6 6 6 6 1.41-1.41L10.83 12z"/></svg>
        </button>
        <h1 class="sub-header__title">外观</h1>
      </header>
      <section class="settings-section">
        <div class="setting-row">
          <div class="setting-label">
            <span class="setting-title">主题</span>
            <span class="setting-desc">选择界面色彩主题</span>
          </div>
          <el-select v-model="settingsStore.theme" @change="settingsStore.saveSettings()">
            <el-option label="暗色" value="dark" />
            <el-option label="亮色" value="light" />
            <el-option label="跟随系统" value="system" />
          </el-select>
        </div>
        <div class="setting-row">
          <div class="setting-label">
            <span class="setting-title">主题色</span>
            <span class="setting-desc">选择界面强调色</span>
          </div>
          <el-color-picker v-model="settingsStore.accentColor" @change="settingsStore.saveSettings()" />
        </div>
        <div class="setting-row">
          <div class="setting-label">
            <span class="setting-title">跟随系统主题色</span>
            <span class="setting-desc">自动使用 Windows 主题色作为界面强调色</span>
          </div>
          <el-switch v-model="settingsStore.followSystemTheme" @change="settingsStore.saveSettings()" />
        </div>
      </section>
    </template>

    <!-- 二级页：播放界面 -->
    <template v-if="page === 'player'">
      <header class="sub-header">
        <button class="sub-header__back" @click="page = 'menu'">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M15.41 7.41L14 6l-6 6 6 6 1.41-1.41L10.83 12z"/></svg>
        </button>
        <h1 class="sub-header__title">播放界面</h1>
      </header>
      <section class="settings-section">
        <div class="setting-row">
          <div class="setting-label">
            <span class="setting-title">动态流光背景</span>
            <span class="setting-desc">全屏歌词页背景随封面主色动态流动的流光效果（关闭可提升低配设备性能）</span>
          </div>
          <el-switch v-model="settingsStore.enableDynamicBg" @change="settingsStore.saveSettings()" />
        </div>
        <div class="setting-row">
          <div class="setting-label">
            <span class="setting-title">音频律动</span>
            <span class="setting-desc">全屏歌词页光球随音频节奏改变速度与透明度（关闭时光球匀速流动）</span>
          </div>
          <el-switch v-model="settingsStore.enableAudioRhythm" @change="settingsStore.saveSettings()" />
        </div>
        <div class="setting-row">
          <div class="setting-label">
            <span class="setting-title">歌词行模糊</span>
            <span class="setting-desc">远离当前行的歌词行产生模糊效果（关闭可提升低配设备性能）</span>
          </div>
          <el-switch v-model="settingsStore.enableLyricsBlur" @change="settingsStore.saveSettings()" />
        </div>
        <div class="setting-row">
          <div class="setting-label">
            <span class="setting-title">多米诺滚动动画</span>
            <span class="setting-desc">歌词行切换时的级联滚动动画效果（关闭可提升低配设备性能）</span>
          </div>
          <el-switch v-model="settingsStore.enableDominoScroll" @change="settingsStore.saveSettings()" />
        </div>
        <div class="setting-row">
          <div class="setting-label">
            <span class="setting-title">逐字上浮动画</span>
            <span class="setting-desc">当前播放歌词的逐字上浮效果（关闭可提升低配设备性能）</span>
          </div>
          <el-switch v-model="settingsStore.enableWordLift" @change="settingsStore.saveSettings()" />
        </div>
        <div class="setting-row setting-row--slider">
          <div class="setting-label">
            <span class="setting-title">逐字动画帧率</span>
            <span class="setting-desc">控制卡拉OK扫过与上浮动画的刷新率（当前：<b>{{ settingsStore.wordAnimFps === 0 ? '关闭' : settingsStore.wordAnimFps + ' fps' }}</b>）</span>
          </div>
          <el-slider
            v-model="settingsStore.wordAnimFps"
            :min="0" :max="240" :step="5"
            class="setting-slider"
            :marks="{ 0:'关', 30:'30', 60:'60', 120:'120', 144:'144', 240:'240' }"
            @change="settingsStore.saveSettings()"
          />
        </div>
      </section>
    </template>

    <!-- 二级页：歌词排版 -->
    <template v-if="page === 'lyricStyle'">
      <header class="sub-header">
        <button class="sub-header__back" v-ripple @click="page = 'menu'">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M15.41 7.41L14 6l-6 6 6 6 1.41-1.41L10.83 12z"/></svg>
        </button>
        <h1 class="sub-header__title">歌词排版</h1>
      </header>
      <section class="settings-section">
        <div class="setting-row setting-row--slider">
          <div class="setting-label">
            <span class="setting-title">歌词字号</span>
            <span class="setting-desc">调节歌词基准字号（当前：<b>{{ settingsStore.lyricsFontSize }}px</b>）</span>
          </div>
          <el-slider
            v-model="settingsStore.lyricsFontSize"
            :min="12" :max="60" :step="1"
            class="setting-slider"
            @change="settingsStore.saveSettings()"
          />
        </div>
        <div class="setting-row setting-row--slider">
          <div class="setting-label">
            <span class="setting-title">歌词字重</span>
            <span class="setting-desc">利用 MiSans VF 可变轴微调粗细（当前：<b>{{ settingsStore.lyricsFontWeight }}</b>）</span>
          </div>
          <el-slider
            v-model="settingsStore.lyricsFontWeight"
            :min="250" :max="900" :step="50"
            class="setting-slider"
            :marks="{ 250:'轻', 400:'常规', 700:'粗', 900:'超粗' }"
            @change="settingsStore.saveSettings()"
          />
        </div>
        <div class="setting-row setting-row--slider">
          <div class="setting-label">
            <span class="setting-title">翻译词比例</span>
            <span class="setting-desc">相对基准字号的百分比（当前：<b>{{ settingsStore.lyricsTransScale }}%</b> ≈ {{ Math.round(settingsStore.lyricsFontSize * settingsStore.lyricsTransScale / 100) }}px）</span>
          </div>
          <el-slider
            v-model="settingsStore.lyricsTransScale"
            :min="50" :max="100" :step="5"
            class="setting-slider"
            @change="settingsStore.saveSettings()"
          />
        </div>
        <div class="setting-row setting-row--slider">
          <div class="setting-label">
            <span class="setting-title">正在播放行放大</span>
            <span class="setting-desc">活跃行相对基准/翻译的百分比（当前：<b>{{ settingsStore.lyricsActiveScale }}%</b>）</span>
          </div>
          <el-slider
            v-model="settingsStore.lyricsActiveScale"
            :min="100" :max="130" :step="5"
            class="setting-slider"
            @change="settingsStore.saveSettings()"
          />
        </div>
        <div class="setting-row">
          <div class="setting-label">
            <span class="setting-title">恢复歌词默认</span>
            <span class="setting-desc">字号 32px · 字重 700 · 翻译 60% · 放大 115%</span>
          </div>
          <button class="reset-btn" v-ripple @click="settingsStore.resetLyricsDefaults()">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"/>
            </svg>
            恢复默认
          </button>
        </div>
      </section>
    </template>

    <!-- 二级页：桌面歌词 -->
    <template v-if="page === 'desktopLyric'">
      <header class="sub-header">
        <button class="sub-header__back" v-ripple @click="page = 'menu'">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M15.41 7.41L14 6l-6 6 6 6 1.41-1.41L10.83 12z"/></svg>
        </button>
        <h1 class="sub-header__title">桌面歌词</h1>
      </header>
      <section class="settings-section">
        <div class="setting-row setting-row--slider">
          <div class="setting-label">
            <span class="setting-title">字号</span>
            <span class="setting-desc">桌面歌词独立窗口基准字号（当前：<b>{{ settingsStore.desktopLyricsFontSize }}px</b>）</span>
          </div>
          <el-slider
            v-model="settingsStore.desktopLyricsFontSize"
            :min="16" :max="36" :step="1"
            class="setting-slider"
            @change="settingsStore.saveSettings()"
          />
        </div>
        <div class="setting-row setting-row--slider">
          <div class="setting-label">
            <span class="setting-title">活跃行放大</span>
            <span class="setting-desc">正在播放行相对基准字号的百分比（当前：<b>{{ settingsStore.desktopLyricsActiveScale }}%</b> → {{ Math.round(settingsStore.desktopLyricsFontSize * settingsStore.desktopLyricsActiveScale / 100) }}px）</span>
          </div>
          <el-slider
            v-model="settingsStore.desktopLyricsActiveScale"
            :min="100" :max="150" :step="5"
            class="setting-slider"
            @change="settingsStore.saveSettings()"
          />
        </div>
        <div class="setting-row setting-row--slider">
          <div class="setting-label">
            <span class="setting-title">翻译词比例</span>
            <span class="setting-desc">翻译词相对基准字号的百分比（当前：<b>{{ settingsStore.desktopLyricsTransScale }}%</b> → {{ Math.round(settingsStore.desktopLyricsFontSize * settingsStore.desktopLyricsTransScale / 100) }}px）</span>
          </div>
          <el-slider
            v-model="settingsStore.desktopLyricsTransScale"
            :min="40" :max="100" :step="5"
            class="setting-slider"
            @change="settingsStore.saveSettings()"
          />
        </div>
        <div class="setting-row">
          <div class="setting-label">
            <span class="setting-title">视口行数</span>
            <span class="setting-desc">歌词窗口内同时显示的歌词行数（当前：<b>{{ settingsStore.desktopLyricsViewLines }} 句</b>）</span>
          </div>
          <div class="toggle-buttons">
            <button
              v-ripple
              :class="['toggle-btn', { active: settingsStore.desktopLyricsViewLines === 1 }]"
              @click="settingsStore.desktopLyricsViewLines = 1; settingsStore.saveSettingsImmediate()"
            >1 句</button>
            <button
              v-ripple
              :class="['toggle-btn', { active: settingsStore.desktopLyricsViewLines === 2 }]"
              @click="settingsStore.desktopLyricsViewLines = 2; settingsStore.saveSettingsImmediate()"
            >2 句</button>
          </div>
        </div>
        <div class="setting-row">
          <div class="setting-label">
            <span class="setting-title">恢复桌面歌词默认</span>
            <span class="setting-desc">字号 24px · 放大 120% · 翻译 60%</span>
          </div>
          <button class="reset-btn" v-ripple @click="settingsStore.desktopLyricsFontSize = 24; settingsStore.desktopLyricsActiveScale = 120; settingsStore.desktopLyricsTransScale = 60; settingsStore.saveSettingsImmediate()">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"/>
            </svg>
            恢复默认
          </button>
        </div>
      </section>
    </template>

    <!-- 二级页：系统 -->
    <template v-if="page === 'system'">
      <header class="sub-header">
        <button class="sub-header__back" @click="page = 'menu'">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M15.41 7.41L14 6l-6 6 6 6 1.41-1.41L10.83 12z"/></svg>
        </button>
        <h1 class="sub-header__title">系统</h1>
      </header>
      <section class="settings-section">
        <div class="setting-row">
          <div class="setting-label">
            <span class="setting-title">启动时自动扫描</span>
            <span class="setting-desc">应用启动时自动扫描已导入的音乐目录</span>
          </div>
          <el-switch v-model="settingsStore.autoScan" @change="settingsStore.saveSettings()" />
        </div>
      </section>
    </template>

    <!-- 二级页：关于 -->
    <template v-if="page === 'about'">
      <header class="sub-header">
        <button class="sub-header__back" v-ripple @click="page = 'menu'">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M15.41 7.41L14 6l-6 6 6 6 1.41-1.41L10.83 12z"/></svg>
        </button>
        <h1 class="sub-header__title">关于</h1>
      </header>
      <section class="settings-section about-section">
        <div class="about-header">
          <div class="about-logo">
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
              <path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/>
            </svg>
          </div>
          <div class="about-appname">
            <span class="about-appname__title">MelodyBox</span>
            <span class="about-appname__version">Alpha 0.1.0</span>
          </div>
        </div>
        <div class="about-meta">
          <div class="about-meta__row">
            <span>技术栈</span>
            <span>Vue 3 + Electron + Element Plus</span>
          </div>
          <div class="about-meta__row">
            <span>毕业设计</span>
            <span>哈尔滨信息工程学院 2023届 软件工程 王云龙</span>
          </div>
        </div>
        <div class="setting-row" style="margin-top: 24px;">
          <div class="setting-label">
            <span class="setting-title">调试模式</span>
            <span class="setting-desc">开启后将显示律动调试窗口并传输实时参数（重启应用后自动关闭）</span>
          </div>
          <el-switch v-model="settingsStore.debugMode" />
        </div>
      </section>
    </template>
  </div>
</template>

<script setup>
defineOptions({ name: 'SettingsView' })
import { ref } from 'vue'
import { useSettingsStore } from '@/stores/settings'
import { useScrollMemory } from '@/composables/useScrollMemory'

const settingsStore = useSettingsStore()
const page = ref('menu')

useScrollMemory('settings', () => document.querySelector('.main-content'))
</script>

<style scoped>
.settings-view { padding: 0 0 100px; }

/* ===== 一级菜单页 ===== */
.settings-view > h1 { font-size: 28px; font-weight: 700; margin: 0 0 28px; letter-spacing: -0.3px; }

.menu-list {
  display: flex; flex-direction: column;
  background: var(--bg-primary);
  border-radius: 14px; overflow: hidden;
  border: 1px solid var(--border-color);
}
.menu-item {
  display: flex; align-items: center; justify-content: space-between;
  width: 100%; padding: 18px 22px;
  background: transparent; border: none; color: inherit;
  cursor: pointer; text-align: left; font: inherit;
  transition: background 0.18s ease;
}
.menu-item:not(:last-child) { border-bottom: 1px solid var(--border-color); }
.menu-item:hover { background: var(--hover-bg); }
.menu-item:active { background: var(--hover-bg-strong); }

.menu-item__left { display: flex; align-items: center; gap: 16px; }
.menu-item__icon {
  display: flex; align-items: center; justify-content: center;
  width: 42px; height: 42px; border-radius: 12px; flex-shrink: 0;
}
.menu-item__text { display: flex; flex-direction: column; gap: 3px; }
.menu-item__title { font-size: 15px; font-weight: 600; line-height: 1.3; }
.menu-item__desc { font-size: 12px; color: var(--text-tertiary); line-height: 1.3; }
.menu-item__arrow { opacity: 0.25; flex-shrink: 0; transition: opacity 0.15s; }
.menu-item:hover .menu-item__arrow { opacity: 0.45; }

/* ===== 二级页公共头部 ===== */
.sub-header {
  display: flex; align-items: center; gap: 14px;
  margin-bottom: 24px;
}
.sub-header__back {
  display: flex; align-items: center; justify-content: center;
  width: 38px; height: 38px; border-radius: 12px;
  background: var(--bg-primary); border: 1px solid var(--border-color); color: inherit;
  cursor: pointer; flex-shrink: 0;
  transition: background 0.15s ease;
}
.sub-header__back:hover { background: var(--hover-bg-strong); }
.sub-header__title { font-size: 22px; font-weight: 700; margin: 0; letter-spacing: -0.2px; }

/* ===== 二级页内容 ===== */
.settings-section {
  background: var(--bg-primary);
  border-radius: 14px; padding: 6px 22px;
  border: 1px solid var(--border-color);
}

.setting-row {
  display: flex; align-items: center; justify-content: space-between;
  padding: 16px 0; gap: 24px;
}
.setting-row:not(:last-child) { border-bottom: 1px solid var(--border-color); }

.setting-row--slider {
  flex-direction: column; align-items: stretch;
  padding: 18px 0; gap: 14px;
}
.setting-row--slider .setting-label {
  max-width: none;
}

.setting-label {
  display: flex; flex-direction: column; gap: 3px;
  max-width: 60%; min-width: 0;
}
.setting-title { font-size: 14px; font-weight: 600; line-height: 1.3; }
.setting-desc { font-size: 12px; color: var(--text-tertiary); line-height: 1.4; }
.setting-desc b { color: var(--text-secondary); font-weight: 600; }

.setting-slider {
  width: 100%;
}

/* Element Plus slider 覆盖：与开关按钮大小统一 */
:deep(.setting-slider .el-slider__button) {
  width: 16px; height: 16px;
}
:deep(.setting-slider .el-slider__marks-text) {
  font-size: 10px; color: var(--text-tertiary);
}

/* ===== 恢复按钮 ===== */
.reset-btn {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 8px 16px; border-radius: 9px;
  background: var(--hover-bg); border: 1px solid var(--border-color);
  color: var(--text-secondary); font-size: 13px; font-weight: 500;
  cursor: pointer; transition: all 0.15s ease;
}
.reset-btn:hover {
  background: var(--hover-bg-strong);
  color: var(--text-primary);
}

/* ===== 关于页 ===== */
.about-section {
  padding: 28px 28px 32px;
}

.about-header {
  display: flex; flex-direction: column; align-items: center; gap: 14px;
  margin-bottom: 28px;
}
.about-logo {
  display: flex; align-items: center; justify-content: center;
  width: 64px; height: 64px; border-radius: 18px;
  background: linear-gradient(135deg, rgba(99,102,241,0.25), rgba(168,85,247,0.2));
  color: #a78bfa;
}
.about-appname { text-align: center; }
.about-appname__title {
  display: block; font-size: 22px; font-weight: 700; letter-spacing: -0.3px;
}
.about-appname__version {
  display: block; font-size: 13px; color: var(--text-tertiary); margin-top: 3px;
}

.about-meta {
  display: flex; flex-direction: column;
  background: var(--hover-bg);
  border-radius: 11px; padding: 4px 0; border: 1px solid var(--border-color);
}
.about-meta__row {
  display: flex; justify-content: space-between; align-items: center;
  padding: 11px 16px; font-size: 13px; color: var(--text-secondary);
}
.about-meta__row:not(:last-child) { border-bottom: 1px solid var(--border-color); }
.about-meta__row span:first-child { color: var(--text-tertiary); font-weight: 500; }

.toggle-buttons {
  display: flex; gap: 8px;
}
.toggle-btn {
  padding: 6px 20px; border-radius: 8px; border: 1px solid var(--border-color);
  background: var(--bg-secondary); color: var(--text-secondary);
  font-size: 13px; font-weight: 600; cursor: pointer;
  transition: all 0.18s ease;
}
.toggle-btn.active {
  background: var(--accent-color); color: #fff; border-color: var(--accent-color);
}
.toggle-btn:hover:not(.active) { background: var(--hover-bg); }
</style>
