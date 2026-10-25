<template>
  <div class="settings-view">
    <!-- 与路由页切换复用同一组 page-enter / page-leave 关键帧 -->
    <Transition name="settings-page">
    <div :key="page" class="settings-page">
    <!-- 一级菜单页 -->
    <template v-if="page === 'menu'">
      <h1>设置</h1>
      <div class="menu-list">
        <button class="menu-item" v-ripple @click="page = 'appearance'">
          <div class="menu-item__left">
            <span class="menu-item__icon" style="color: #818cf8">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                <path d="M12 2.69l5.66 5.66a8 8 0 1 1-11.31 0z"/>
              </svg>
            </span>
            <div class="menu-item__text">
              <span class="menu-item__title">外观</span>
            </div>
          </div>
          <svg class="menu-item__arrow" width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M8.59 16.59L13.17 12 8.59 7.41 10 6l6 6-6 6z"/></svg>
        </button>
        <button class="menu-item" v-ripple @click="page = 'player'">
          <div class="menu-item__left">
            <span class="menu-item__icon" style="color: #4ade80">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                <path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/>
              </svg>
            </span>
            <div class="menu-item__text">
              <span class="menu-item__title">播放界面</span>
            </div>
          </div>
          <svg class="menu-item__arrow" width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M8.59 16.59L13.17 12 8.59 7.41 10 6l6 6-6 6z"/></svg>
        </button>
        <button class="menu-item" v-ripple @click="page = 'desktopLyric'">
          <div class="menu-item__left">
            <span class="menu-item__icon" style="color: #a855f7">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                <rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/>
              </svg>
            </span>
            <div class="menu-item__text">
              <span class="menu-item__title">桌面歌词</span>
            </div>
          </div>
          <svg class="menu-item__arrow" width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M8.59 16.59L13.17 12 8.59 7.41 10 6l6 6-6 6z"/></svg>
        </button>
      </div>
      <div class="menu-list">
        <button class="menu-item" v-ripple @click="page = 'system'">
          <div class="menu-item__left">
            <span class="menu-item__icon" style="color: #94a3b8">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>
              </svg>
            </span>
            <div class="menu-item__text">
              <span class="menu-item__title">系统</span>
            </div>
          </div>
          <svg class="menu-item__arrow" width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M8.59 16.59L13.17 12 8.59 7.41 10 6l6 6-6 6z"/></svg>
        </button>
        <button class="menu-item" v-ripple @click="page = 'ai'">
          <div class="menu-item__left">
            <span class="menu-item__icon" style="color: #818cf8">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                <path d="M12 2a4 4 0 1 0 0 8 4 4 0 1 0 0-8z"/>
                <path d="M8 14c-3.3 0-6 2.7-6 6v1h20v-1c0-3.3-2.7-6-6-6H8z"/>
                <path d="M17.5 5.5c1.5 0 3 1 3.5 2.5M6.5 5.5c-1.5 0-3 1-3.5 2.5"/>
              </svg>
            </span>
            <div class="menu-item__text">
              <span class="menu-item__title">AI 推荐</span>
            </div>
          </div>
          <svg class="menu-item__arrow" width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M8.59 16.59L13.17 12 8.59 7.41 10 6l6 6-6 6z"/></svg>
        </button>
      </div>
      <div class="menu-list">
        <button class="menu-item" v-ripple @click="page = 'about'">
          <div class="menu-item__left">
            <span class="menu-item__icon" style="color: #38bdf8">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/>
              </svg>
            </span>
            <div class="menu-item__text">
              <span class="menu-item__title">关于</span>
            </div>
          </div>
          <svg class="menu-item__arrow" width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M8.59 16.59L13.17 12 8.59 7.41 10 6l6 6-6 6z"/></svg>
        </button>
      </div>
    </template>

    <!-- 二级页：外观 -->
    <template v-if="page === 'appearance'">
      <ListPageHeader title="外观" :show-play-mode="false" show-back :back-handler="() => page = 'menu'" />
      <div class="settings-group">
        <div class="settings-group__title">主题</div>
        <section class="settings-card">
          <button class="setting-row setting-row--click" v-ripple @click="openPick($event, THEME_OPTIONS, setTheme, settingsStore.theme)">
            <span class="setting-title">主题模式</span>
            <span class="setting-value setting-value--pick">
              {{ labelOf(THEME_OPTIONS, settingsStore.theme) }}
              <svg class="setting-chevron" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>
            </span>
          </button>
          <div class="setting-row setting-row--click" v-ripple @click="toggleSwitch('followSystemTheme')">
            <span class="setting-title">跟随系统主题色</span>
            <el-switch v-model="settingsStore.followSystemTheme" />
          </div>
          <!-- 跟随系统时整行向上收起（grid-rows 0fr → 1fr 动画） -->
          <div class="accent-collapse" :class="{ 'is-open': !settingsStore.followSystemTheme }">
            <div class="accent-collapse__inner" :inert="settingsStore.followSystemTheme">
              <div class="setting-row setting-row--accent">
                <span class="setting-title">主题色</span>
                <div class="accent-swatches">
                  <button
                    v-for="c in accentPresets"
                    :key="c"
                    class="accent-swatch"
                    :class="{ active: sameAccent(c) }"
                    :style="{ background: c }"
                    :title="c"
                    @click="setAccent(c)"
                  ></button>
                  <label
                    class="accent-swatch accent-swatch--custom"
                    :class="{ active: isCustomAccent }"
                    :style="{ background: settingsStore.customAccentColor }"
                    title="自定义颜色"
                    @click="onCustomSwatchClick"
                  >
                    <input type="color" :value="settingsStore.customAccentColor" @input="onCustomAccent" />
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                      <path d="M12 20h9"/><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4z"/>
                    </svg>
                  </label>
                </div>
              </div>
            </div>
          </div>
        </section>
      </div>
    </template>

    <!-- 二级页：播放界面 -->
    <template v-if="page === 'player'">
      <ListPageHeader title="播放界面" :show-play-mode="false" show-back :back-handler="() => page = 'menu'" />
      <div class="settings-group">
        <div class="settings-group__title">歌词字号与比例</div>
        <section class="settings-card">
          <div class="setting-row setting-row--slider">
            <div class="setting-row__head">
              <span class="setting-title">歌词字号</span>
              <span class="setting-value">{{ settingsStore.lyricsFontSize }} px</span>
            </div>
            <el-slider
              v-model="settingsStore.lyricsFontSize"
              :min="12" :max="60" :step="1"
              class="setting-slider"
              @change="settingsStore.saveSettings()"
            />
          </div>
          <div class="setting-row setting-row--slider">
            <div class="setting-row__head">
              <span class="setting-title">歌词字重</span>
              <span class="setting-value">{{ settingsStore.lyricsFontWeight }}</span>
            </div>
            <el-slider
              v-model="settingsStore.lyricsFontWeight"
              :min="250" :max="900" :step="50"
              class="setting-slider"
              @change="settingsStore.saveSettings()"
            />
          </div>
          <div class="setting-row setting-row--slider">
            <div class="setting-row__head">
              <span class="setting-title">翻译词比例</span>
              <span class="setting-value">{{ settingsStore.lyricsTransScale }}% · {{ Math.round(settingsStore.lyricsFontSize * settingsStore.lyricsTransScale / 100) }} px</span>
            </div>
            <el-slider
              v-model="settingsStore.lyricsTransScale"
              :min="50" :max="100" :step="5"
              class="setting-slider"
              @change="settingsStore.saveSettings()"
            />
          </div>
          <div class="setting-row setting-row--slider">
            <div class="setting-row__head">
              <span class="setting-title">活跃行放大</span>
              <span class="setting-value">{{ settingsStore.lyricsActiveScale }}%</span>
            </div>
            <el-slider
              v-model="settingsStore.lyricsActiveScale"
              :min="100" :max="130" :step="5"
              class="setting-slider"
              @change="settingsStore.saveSettings()"
            />
          </div>
          <div class="setting-row">
            <span class="setting-title">恢复歌词默认</span>
            <button class="reset-btn" v-ripple @click="settingsStore.resetLyricsDefaults()">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"/>
              </svg>
              恢复默认
            </button>
          </div>
        </section>
      </div>

      <div class="settings-group">
        <div class="settings-group__title">歌词动画</div>
        <section class="settings-card">
          <div class="setting-row setting-row--click" v-ripple @click="toggleSwitch('enableDynamicBg')">
            <span class="setting-title">动态流光背景</span>
            <el-switch v-model="settingsStore.enableDynamicBg" />
          </div>
          <div class="setting-row setting-row--click" v-ripple @click="toggleSwitch('enableAudioRhythm')">
            <span class="setting-title">音频律动</span>
            <el-switch v-model="settingsStore.enableAudioRhythm" />
          </div>
          <div class="setting-row setting-row--click" v-ripple @click="toggleSwitch('enableLyricsBlur')">
            <span class="setting-title">歌词行模糊</span>
            <el-switch v-model="settingsStore.enableLyricsBlur" />
          </div>
          <div class="setting-row setting-row--click" v-ripple @click="toggleSwitch('enableDominoScroll')">
            <span class="setting-title">多米诺滚动动画</span>
            <el-switch v-model="settingsStore.enableDominoScroll" />
          </div>
          <div class="setting-row setting-row--click" v-ripple @click="toggleSwitch('enableWordLift')">
            <span class="setting-title">逐字上浮动画</span>
            <el-switch v-model="settingsStore.enableWordLift" />
          </div>
          <div class="setting-row setting-row--slider">
            <div class="setting-row__head">
              <span class="setting-title">逐字动画帧率</span>
              <div class="setting-row__tail">
                <el-switch v-model="settingsStore.fpsAdaptive" active-text="自适应" inactive-text="固定" />
                <span class="setting-value">{{ settingsStore.fpsAdaptive ? settingsStore.effectiveWordAnimFps : settingsStore.wordAnimFps }} fps</span>
              </div>
            </div>
            <el-slider
              :model-value="settingsStore.wordAnimFps"
              :min="24" :max="240" :step="1"
              :disabled="settingsStore.fpsAdaptive"
              class="setting-slider"
              @input="onFpsInput"
              @change="onFpsChange"
            />
          </div>
          <button class="setting-row setting-row--click" v-ripple @click="openPick($event, KARAOKE_OPTIONS, setKaraokeMode, settingsStore.lyricKaraokeMode)">
            <span class="setting-title">卡拉OK模式</span>
            <span class="setting-value setting-value--pick">
              {{ labelOf(KARAOKE_OPTIONS, settingsStore.lyricKaraokeMode) }}
              <svg class="setting-chevron" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>
            </span>
          </button>
          <button class="setting-row setting-row--click" v-ripple @click="openPick($event, RHYTHM_FPS_OPTIONS, setRhythmFps, settingsStore.rhythmFps)">
            <span class="setting-title">律动响应帧率</span>
            <span class="setting-value setting-value--pick">
              {{ labelOf(RHYTHM_FPS_OPTIONS, settingsStore.rhythmFps) }}
              <svg class="setting-chevron" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>
            </span>
          </button>
        </section>
      </div>

      <div class="settings-group">
        <div class="settings-group__title">画质与性能</div>
        <section class="settings-card">
          <button class="setting-row setting-row--click" v-ripple @click="openPick($event, QUALITY_OPTIONS, setQualityPreset, settingsStore.qualityPreset)">
            <span class="setting-title">画质档位</span>
            <span class="setting-value setting-value--pick">
              {{ labelOf(QUALITY_OPTIONS, settingsStore.qualityPreset) }}
              <svg class="setting-chevron" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>
            </span>
          </button>
          <div class="setting-row">
            <span class="setting-title">屏幕刷新率</span>
            <div class="setting-row__tail">
              <span class="setting-value">{{ settingsStore.measuredRefresh }} Hz</span>
              <el-button size="small" v-ripple @click="redetectRefresh">重新检测</el-button>
            </div>
          </div>
          <div class="setting-row">
            <span class="setting-title">性能基准测试</span>
            <el-button size="small" type="primary" v-ripple :loading="perf.status === 'running'" @click="startBenchmark">
              {{ perf.status === 'running' ? '测试中' : '运行测试' }}
            </el-button>
          </div>
          <div v-if="perf.status === 'running'" class="setting-row setting-row--stack">
            <el-progress :percentage="perf.progress" :show-text="false" />
            <span class="setting-value">正在测量帧率 {{ perf.liveFps }} FPS</span>
          </div>
          <div v-else-if="perf.result" class="setting-row setting-row--stack">
            <span class="setting-value">平均 {{ perf.result.fps }} FPS · 长任务 {{ perf.result.longMs }} ms · 性能分 {{ perf.result.score }}</span>
            <div class="setting-row__tail">
              <span class="setting-value">推荐 {{ tierLabel(perf.result.tier) }}</span>
              <el-button size="small" type="primary" v-ripple @click="applyBenchmarkTier">应用</el-button>
            </div>
          </div>
          <div v-else-if="cachedBench" class="setting-row setting-row--stack">
            <span class="setting-value">上次测试 {{ cachedBench.fps }} FPS · 推荐 {{ tierLabel(cachedBench.tier) }}</span>
          </div>
        </section>
      </div>
    </template>

    <!-- 二级页：桌面歌词 -->
    <template v-if="page === 'desktopLyric'">
      <ListPageHeader title="桌面歌词" :show-play-mode="false" show-back :back-handler="() => page = 'menu'" />
      <div class="settings-group">
        <div class="settings-group__title">窗口样式</div>
        <section class="settings-card">
          <div class="setting-row setting-row--slider">
            <div class="setting-row__head">
              <span class="setting-title">字号</span>
              <span class="setting-value">{{ settingsStore.desktopLyricsFontSize }} px</span>
            </div>
            <el-slider
              v-model="settingsStore.desktopLyricsFontSize"
              :min="16" :max="36" :step="1"
              class="setting-slider"
              @change="settingsStore.saveSettings()"
            />
          </div>
          <div class="setting-row setting-row--slider">
            <div class="setting-row__head">
              <span class="setting-title">活跃行放大</span>
              <span class="setting-value">{{ settingsStore.desktopLyricsActiveScale }}% · {{ Math.round(settingsStore.desktopLyricsFontSize * settingsStore.desktopLyricsActiveScale / 100) }} px</span>
            </div>
            <el-slider
              v-model="settingsStore.desktopLyricsActiveScale"
              :min="100" :max="150" :step="5"
              class="setting-slider"
              @change="settingsStore.saveSettings()"
            />
          </div>
          <div class="setting-row setting-row--slider">
            <div class="setting-row__head">
              <span class="setting-title">翻译词比例</span>
              <span class="setting-value">{{ settingsStore.desktopLyricsTransScale }}% · {{ Math.round(settingsStore.desktopLyricsFontSize * settingsStore.desktopLyricsTransScale / 100) }} px</span>
            </div>
            <el-slider
              v-model="settingsStore.desktopLyricsTransScale"
              :min="40" :max="100" :step="5"
              class="setting-slider"
              @change="settingsStore.saveSettings()"
            />
          </div>
          <button class="setting-row setting-row--click" v-ripple @click="openPick($event, VIEW_LINES_OPTIONS, setViewLines, settingsStore.desktopLyricsViewLines)">
            <span class="setting-title">视口行数</span>
            <span class="setting-value setting-value--pick">
              {{ labelOf(VIEW_LINES_OPTIONS, settingsStore.desktopLyricsViewLines) }}
              <svg class="setting-chevron" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>
            </span>
          </button>
          <div class="setting-row">
            <span class="setting-title">恢复默认</span>
            <button class="reset-btn" v-ripple @click="settingsStore.desktopLyricsFontSize = 24; settingsStore.desktopLyricsActiveScale = 120; settingsStore.desktopLyricsTransScale = 60; settingsStore.saveSettingsImmediate()">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"/>
              </svg>
              恢复默认
            </button>
          </div>
        </section>
      </div>
    </template>

    <!-- 二级页：系统 -->
    <template v-if="page === 'system'">
      <ListPageHeader title="系统" :show-play-mode="false" show-back :back-handler="() => page = 'menu'" />
      <div class="settings-group">
        <div class="settings-group__title">音乐库</div>
        <section class="settings-card">
          <div class="setting-row setting-row--click" v-ripple @click="toggleSwitch('autoScan')">
            <span class="setting-title">启动时自动扫描</span>
            <el-switch v-model="settingsStore.autoScan" />
          </div>
        </section>
      </div>
    </template>

    <!-- 二级页：AI 推荐 -->
    <template v-if="page === 'ai'">
      <ListPageHeader title="AI 推荐" :show-play-mode="false" show-back :back-handler="() => page = 'menu'" />
      <div class="settings-group">
        <div class="settings-group__title">模型</div>
        <section class="settings-card">
          <div class="setting-row setting-row--stack">
            <span class="setting-title">模型缓存路径</span>
            <span class="setting-value model-path-text">{{ modelDirInput || '默认 · ' + modelDefaultPath }}</span>
            <div class="setting-row__tail">
              <el-button size="small" v-ripple @click="pickModelDir">选择文件夹</el-button>
              <el-button v-if="modelDirInput" size="small" link type="danger" v-ripple @click="modelDirInput = ''">清除</el-button>
              <el-button size="small" type="primary" v-ripple :loading="savingModelDir" @click="saveModelDir">保存</el-button>
            </div>
            <span v-if="modelDirSaved" class="setting-value setting-value--success">
              {{ needRestart ? '已保存，下次启动生效' : '已保存' }}
            </span>
          </div>
        </section>
      </div>
    </template>

    <!-- 二级页：关于 -->
    <template v-if="page === 'about'">
      <ListPageHeader title="关于" :show-play-mode="false" show-back :back-handler="() => page = 'menu'" />
      <div class="about-header">
        <div class="about-logo">
          <img :src="appIcon" alt="MelodyBox" draggable="false" />
        </div>
        <div class="about-appname">
          <span class="about-appname__title">MelodyBox</span>
          <span class="about-appname__version">Alpha 0.1.0</span>
        </div>
      </div>

      <div class="settings-group">
        <div class="settings-group__title">应用信息</div>
        <section class="settings-card">
          <div class="setting-row">
            <span class="setting-title">技术栈</span>
            <span class="setting-value">Vue 3 + Electron + Element Plus</span>
          </div>
          <div class="setting-row">
            <span class="setting-title">毕业设计</span>
            <span class="setting-value">哈尔滨信息工程学院 2023届 软件工程 王云龙</span>
          </div>
        </section>
      </div>

      <div class="settings-group">
        <div class="settings-group__title">其他</div>
        <section class="settings-card">
          <button class="setting-row setting-row--click" v-ripple @click="page = 'licenses'">
            <span class="setting-title">使用开源项目</span>
            <span class="setting-value">{{ licenseTotal }} 项 ›</span>
          </button>
          <button class="setting-row setting-row--click" v-ripple @click="openWelcome">
            <span class="setting-title">重新查看引导</span>
            <span class="setting-value">›</span>
          </button>
          <div class="setting-row setting-row--click" v-ripple @click="toggleSwitch('debugMode', false)">
            <span class="setting-title">调试模式</span>
            <el-switch v-model="settingsStore.debugMode" />
          </div>
        </section>
      </div>
    </template>

    <!-- 二级页：开源许可 -->
    <template v-else-if="page === 'licenses'">
      <ListPageHeader title="使用开源项目" :show-play-mode="false" show-back :back-handler="() => page = 'about'" />
      <section class="licenses-section">
        <p class="licenses-hint">
          以下为本项目直接使用或随包分发的第三方组件。完整许可证文本与版权声明以各项目官方仓库为准，点击条目可用系统浏览器打开项目主页。
        </p>
        <div v-for="group in licenseGroups" :key="group.title" class="license-group">
          <div class="license-group__title">
            <span>{{ group.title }}</span>
            <span class="license-group__count">{{ group.items.length }}</span>
          </div>
          <div class="license-list">
            <button
              v-for="item in group.items"
              :key="item.name"
              class="license-row"
              @click="openLicense(item)"
            >
              <span class="license-row__main">
                <span class="license-row__name">{{ item.name }}</span>
                <span class="license-row__arrow" aria-hidden="true">↗</span>
              </span>
              <span class="license-row__license">{{ item.license }}</span>
            </button>
          </div>
        </div>
        <p class="licenses-foot">感谢以上项目的作者与维护者。</p>
      </section>
    </template>
    </div>
    </Transition>

    <!-- 设置项取值菜单：与右键菜单同款玻璃材质与展开动画，位置跟随鼠标 -->
    <ContextMenu
      :visible="pickMenu.visible"
      :x="pickMenu.x"
      :y="pickMenu.y"
      :items="pickItems"
      animated
      @action="onPickAction"
      @close="pickMenu.visible = false"
    />

  </div>
</template>

<script setup>
defineOptions({ name: 'SettingsView' })
import { ref, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useSettingsStore } from '@/stores/settings'
import { usePerformanceStore } from '@/stores/performance'
import { useScrollMemory } from '@/composables/useScrollMemory'
import ListPageHeader from '@/components/music/ListPageHeader.vue'
import ContextMenu from '@/components/music/ContextMenu.vue'
import { LICENSE_GROUPS, LICENSE_TOTAL } from '@/data/openSourceLicenses'
import { ACCENT_PRESETS } from '@/data/accentPresets'
import appIcon from '@/assets/app-icon-128.png'

const settingsStore = useSettingsStore()
const perf = usePerformanceStore()
const router = useRouter()
const page = ref('menu')

// 关于页 → 重新查看首次引导（replay 模式下完成后返回上一页）
function openWelcome() {
  router.push('/welcome?replay=1')
}

// ==================== 主题色预设 ====================

const accentPresets = ACCENT_PRESETS

function sameAccent(c) {
  return (settingsStore.accentColor || '').toLowerCase() === c.toLowerCase()
}

// 当前颜色不在预设里 → 自定义色块高亮
const isCustomAccent = computed(() =>
  !settingsStore.followSystemTheme && !accentPresets.some((c) => sameAccent(c))
)

function setAccent(c) {
  // 手动选色即退出「跟随系统主题色」，否则选色不生效
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

// ==================== 设置项取值菜单 ====================

const THEME_OPTIONS = [
  { label: '暗色', value: 'dark' },
  { label: '亮色', value: 'light' },
  { label: '跟随系统', value: 'system' }
]
const KARAOKE_OPTIONS = [
  { label: '原生', value: 'native' },
  { label: '智能', value: 'auto' },
  { label: '全卡拉OK', value: 'always' }
]
const RHYTHM_FPS_OPTIONS = [
  { label: '30 fps', value: 30 },
  { label: '60 fps', value: 60 }
]
const QUALITY_OPTIONS = [
  { label: '自动', value: 'auto' },
  { label: '低', value: 'low' },
  { label: '中', value: 'medium' },
  { label: '高', value: 'high' },
  { label: '自定义', value: 'custom' }
]
const VIEW_LINES_OPTIONS = [
  { label: '1 句', value: 1 },
  { label: '2 句', value: 2 }
]

const pickMenu = ref({ visible: false, x: 0, y: 0 })
const pickItems = ref([])
let pickCommit = null

function labelOf(options, value) {
  return options.find((o) => o.value === value)?.label ?? ''
}

// 菜单坐标取鼠标点击位置，与右键菜单完全一致
function openPick(e, options, commit, current) {
  pickItems.value = options.map((o) => ({
    label: o.label,
    action: o.value,
    active: o.value === current
  }))
  pickCommit = commit
  pickMenu.value = { visible: true, x: e.clientX, y: e.clientY }
}

function onPickAction(value) {
  pickMenu.value.visible = false
  if (pickCommit) pickCommit(value)
}

function setTheme(v) {
  settingsStore.theme = v
  settingsStore.saveSettings()
}
function setKaraokeMode(v) {
  settingsStore.lyricKaraokeMode = v
}
function setRhythmFps(v) {
  settingsStore.rhythmFps = v
  settingsStore.saveSettings()
}
function setViewLines(v) {
  settingsStore.desktopLyricsViewLines = v
  settingsStore.saveSettingsImmediate()
}
function setQualityPreset(v) {
  settingsStore.qualityPreset = v
  onPresetChange(v)
}
// 开关类设置项：整行可点，点行即翻转（persist=false 用于仅前端生效的调试模式）
function toggleSwitch(key, persist = true) {
  settingsStore[key] = !settingsStore[key]
  if (persist) settingsStore.saveSettings()
}

// ==================== 使用开源项目 ====================

const licenseGroups = LICENSE_GROUPS
const licenseTotal = LICENSE_TOTAL

function openLicense(item) {
  const url = item?.url
  if (!url) return
  // 统一交给系统默认浏览器打开，不在应用内新开窗口
  if (window.electronAPI?.openExternal) {
    window.electronAPI.openExternal(url)
    return
  }
  window.open(url, '_blank', 'noopener')
}

// ==================== 性能与画质 ====================

const cachedBench = ref(perf.cachedResult())

function tierLabel(tier) {
  return ({ high: '高画质', medium: '中画质', low: '低画质' }[tier] || tier)
}

async function startBenchmark() {
  const res = await perf.runBenchmark()
  if (res) cachedBench.value = res
}

function applyBenchmarkTier() {
  const tier = perf.result?.tier || cachedBench.value?.tier
  if (!tier) return
  perf.applyTier(tier)
  settingsStore.qualityPreset = tier
}

function onPresetChange(preset) {
  if (preset === 'auto') {
    const cached = cachedBench.value || perf.cachedResult()
    if (cached?.tier) {
      perf.applyTier(cached.tier)
      settingsStore.qualityPreset = cached.tier
    } else {
      startBenchmark()
    }
  } else if (preset !== 'custom') {
    perf.applyTier(preset)
  }
}

// 逐字动画帧率固定档位（24 以下移除，固定档位吸附）
const FPS_OPTIONS = [24, 30, 60, 75, 90, 100, 120, 144, 165, 240]

function snapFps(v) {
  return FPS_OPTIONS.reduce(
    (a, b) => (Math.abs(b - v) < Math.abs(a - v) ? b : a)
  )
}

// 拖动过程中即时吸附到最近档位（一档一档，不显示中间值）
function onFpsInput(v) {
  settingsStore.wordAnimFps = snapFps(v)
}

function onFpsChange(v) {
  settingsStore.wordAnimFps = snapFps(v)
  settingsStore.saveSettings()
}

async function redetectRefresh() {
  await settingsStore.detectRefreshRate()
}

// ==================== AI 模型路径 ====================
import { apiUrl } from '@/config/api'

const modelDirInput = ref('')
const modelDefaultPath = ref('')
const savingModelDir = ref(false)
const modelDirSaved = ref(false)
const needRestart = ref(false)

async function loadModelDir() {
  try {
    const res = await fetch(apiUrl('/api/ai/model-dir'))
    if (res.ok) {
      const data = await res.json()
      modelDirInput.value = data.model_cache_dir || ''
      modelDefaultPath.value = data.default_path || '系统临时目录\\fastembed_cache'
    }
  } catch {}
}

async function pickModelDir() {
  try {
    if (window.electronAPI?.selectSingleFolder) {
      const dir = await window.electronAPI.selectSingleFolder()
      if (dir) modelDirInput.value = dir
    } else {
      // 非 Electron 环境回退到手动输入
      const input = prompt('请输入模型缓存路径（留空使用默认）:', modelDirInput.value)
      if (input !== null) modelDirInput.value = input.trim()
    }
  } catch {
    const input = prompt('请输入模型缓存路径:', modelDirInput.value)
    if (input !== null) modelDirInput.value = input.trim()
  }
}

async function saveModelDir() {
  savingModelDir.value = true
  modelDirSaved.value = false
  try {
    const res = await fetch(apiUrl('/api/ai/model-dir'), {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ model_cache_dir: modelDirInput.value })
    })
    if (res.ok) {
      const data = await res.json()
      needRestart.value = data.need_restart || false
      modelDirSaved.value = true
    }
  } catch (e) {
    console.error('[settings] 保存模型路径失败:', e)
  } finally {
    savingModelDir.value = false
  }
}

// 进入 AI 页面时加载当前配置
watch(page, (val) => {
  if (val === 'ai') loadModelDir()
})

useScrollMemory('settings', () => document.querySelector('.main-content'))
</script>

<style scoped>
.settings-view { position: relative; padding: 0 var(--page-pad-x, 12px) 100px; }
/* 页头吸附基准对齐全站：默认 sticky top 为 --content-top，会整体下移一个页头上方背景带
   设置页的卡片本身已按 --page-pad-x 内缩，页头不再重复内缩，否则返回按钮会比卡片右移 12px */
.settings-view :deep(.list-page-header) {
  top: 0;
  padding-left: 0;
  padding-right: 0;
}

/* 二级页切换：与路由页同一套动画参数（进入 0.5s 放大淡入，离开 0.25s 缩小淡出）
   离开页脱离文档流叠在上层，进入页留在流内撑住高度，避免过渡期间滚动条抖动 */
.settings-page-enter-active {
  animation: page-enter 0.5s cubic-bezier(0.2, 0.9, 0.3, 1.0) both;
}
.settings-page-leave-active {
  animation: page-leave 0.25s cubic-bezier(0.2, 0.9, 0.3, 1.0) both;
  position: absolute;
  top: 0;
  left: var(--page-pad-x, 12px);
  right: var(--page-pad-x, 12px);
  z-index: 1;
  pointer-events: none;
}

/* ===== 一级菜单页 ===== */
.settings-page > h1 { font-size: 28px; font-weight: 700; margin: 0 0 28px; letter-spacing: -0.3px; }

.menu-list {
  display: flex; flex-direction: column;
  background: var(--bg-primary);
  border-radius: 14px; overflow: hidden;
  border: 1px solid var(--border-color);
  margin-bottom: 26px;
}
.menu-list:last-child { margin-bottom: 0; }
.menu-item {
  display: flex; align-items: center; justify-content: space-between;
  width: 100%; height: 48px; padding: 0 18px;
  background: transparent; border: none; color: inherit;
  cursor: pointer; text-align: left; font: inherit;
  transition: background 0.18s ease;
}
.menu-item:hover { background: var(--hover-bg); }
.menu-item:active { background: var(--hover-bg-strong); }

.menu-item__left { display: flex; align-items: center; gap: 16px; }
.menu-item__icon {
  display: flex; align-items: center; justify-content: center;
  width: 22px; height: 22px; flex-shrink: 0;
}
.menu-item__text { display: flex; flex-direction: column; gap: 3px; }
.menu-item__title { font-size: 15px; font-weight: 400; line-height: 1.3; }
.menu-item__arrow { opacity: 0.25; flex-shrink: 0; transition: opacity 0.15s; }
.menu-item:hover .menu-item__arrow { opacity: 0.45; }

/* ===== 二级页：类目卡片（与开源项目页同一基准） ===== */
.settings-group { margin-bottom: 26px; }
.settings-group__title {
  display: flex; align-items: baseline; gap: 8px;
  margin-bottom: 10px; padding-left: 2px;
  font-size: 13px; font-weight: 600; color: var(--text-tertiary);
}
.settings-card {
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: 14px; overflow: hidden;
}

.setting-row {
  display: flex; align-items: center; justify-content: space-between;
  width: 100%; height: 48px; gap: 16px; padding: 0 18px;
  transition: background 0.15s ease;
}
.setting-row:hover { background: var(--hover-bg); }
.setting-row--stack {
  height: auto; min-height: 48px; padding: 12px 18px;
  flex-direction: column; align-items: stretch; justify-content: center; gap: 10px;
}
.setting-row--slider {
  height: 96px; padding: 12px 18px;
  flex-direction: column; align-items: stretch; justify-content: center; gap: 10px;
}
.setting-row--click {
  background: none; border: none; color: inherit; font: inherit;
  text-align: left; cursor: pointer; transition: background 0.15s ease;
}
.setting-row--click:hover { background: var(--hover-bg-strong); }
/* 开关交给整行处理，避免点开关时触发两次翻转 */
.setting-row--click :deep(.el-switch) { pointer-events: none; }
.setting-row__head {
  display: flex; align-items: center; justify-content: space-between; gap: 12px;
}
.setting-row__tail { display: flex; align-items: center; gap: 10px; flex-shrink: 0; }

.setting-title { font-size: 15px; font-weight: 400; color: var(--text-primary); }
.setting-value { font-size: 13px; color: var(--text-tertiary); }
.setting-value--success { color: #22c55e; }

.model-path-text {
  max-width: 100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}

/* 取值项：整行可点，右侧显示当前值与箭头 */
.setting-value--pick { display: inline-flex; align-items: center; gap: 6px; }
.setting-chevron { opacity: 0.55; flex-shrink: 0; }

/* 主题色预设色板 */
.setting-row--accent {
  height: auto;
  min-height: 48px;
  padding: 10px 18px;
  gap: 14px;
}
/* 跟随系统主题色时整行收起：grid-template-rows 0fr ↔ 1fr 平滑改变高度 */
.accent-collapse {
  display: grid;
  grid-template-rows: 0fr;
  opacity: 0;
  transition: grid-template-rows 0.3s cubic-bezier(0.2, 0.9, 0.3, 1.0),
              opacity 0.22s ease;
}
.accent-collapse.is-open { grid-template-rows: 1fr; opacity: 1; }
.accent-collapse__inner { min-height: 0; overflow: hidden; }
.accent-swatches {
  display: flex; align-items: center; justify-content: flex-end;
  flex-wrap: wrap; gap: 10px;
}
.accent-swatch {
  position: relative;
  width: 24px; height: 24px;
  padding: 0; border: none; border-radius: 50%;
  cursor: pointer;
  transition: transform 0.15s cubic-bezier(0.34, 1.56, 0.64, 1), box-shadow 0.15s ease;
}
.accent-swatch:hover { transform: scale(1.1); }
.accent-swatch.active {
  box-shadow: 0 0 0 2px var(--bg-primary), 0 0 0 4px var(--accent-color);
}
.accent-swatch--custom {
  display: flex; align-items: center; justify-content: center;
  color: #fff; overflow: hidden;
}
.accent-swatch--custom input {
  position: absolute; inset: 0;
  opacity: 0; cursor: pointer;
}

/* 滑块：粗轨道 + 白色圆形滑块（填充部分为主题色） */
.setting-slider { width: 100%; }
:deep(.setting-slider .el-slider__runway) {
  height: 22px; margin: 0; border-radius: 999px;
  background: var(--hover-bg-strong);
}
:deep(.setting-slider .el-slider__bar) {
  height: 22px; border-radius: 999px;
  background: var(--accent-color);
}
:deep(.setting-slider .el-slider__button-wrapper) { top: -7px; }
:deep(.setting-slider .el-slider__button) {
  width: 22px; height: 22px;
  border: none; background: #fff;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.28);
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
.about-header {
  display: flex; flex-direction: column; align-items: center; gap: 14px;
  margin-bottom: 26px; padding-top: 4px;
}
.about-logo {
  display: flex; align-items: center; justify-content: center;
  width: 64px; height: 64px; border-radius: 18px; overflow: hidden;
}
.about-logo img {
  width: 100%; height: 100%; object-fit: contain; display: block;
}
.about-appname { text-align: center; }
.about-appname__title {
  display: block; font-size: 22px; font-weight: 700; letter-spacing: -0.3px;
}
.about-appname__version {
  display: block; font-size: 13px; color: var(--text-tertiary); margin-top: 3px;
}

/* ===== 开源许可页：不设外层内容区，每个类目独立成卡 ===== */
.licenses-section { padding: 0 0 32px; }
.licenses-hint {
  margin: 0 0 22px; padding-left: 2px;
  font-size: 13px; font-weight: 600; line-height: 1.7;
  color: var(--text-tertiary);
}
.license-group { margin-bottom: 26px; }
.license-group__title {
  display: flex; align-items: baseline; gap: 8px;
  margin-bottom: 10px; padding-left: 2px;
  font-size: 13px; font-weight: 600; color: var(--text-tertiary);
}
.license-group__count {
  font-size: 11px; font-weight: 500; color: var(--text-tertiary); opacity: 0.65;
}
.license-list {
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: 14px; overflow: hidden;
}
.license-row {
  display: flex; align-items: center; justify-content: space-between; gap: 16px;
  width: 100%; height: 48px; padding: 0 18px;
  background: none; border: none;
  color: var(--text-secondary); font-size: 13px; text-align: left; cursor: pointer;
  transition: background 0.15s ease;
}
.license-row:hover { background: var(--hover-bg-strong); }
.license-row__main { display: flex; align-items: center; gap: 6px; min-width: 0; }
.license-row__name {
  min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.license-row__license {
  flex-shrink: 0; max-width: 190px; padding: 3px 8px; border-radius: 6px;
  border: 1px solid var(--border-color); background: var(--bg-secondary);
  font-size: 11px; line-height: 1.4; color: var(--text-tertiary);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.license-row__arrow {
  font-size: 11px; color: var(--text-tertiary);
  opacity: 0; transform: translate(0, 0);
  transition: opacity 0.15s ease, transform 0.15s ease;
}
.license-row:hover .license-row__arrow { opacity: 0.75; transform: translate(1px, -1px); }
.licenses-foot {
  margin: 2px 0 0; padding-left: 2px;
  font-size: 13px; font-weight: 600; color: var(--text-tertiary);
}
</style>
