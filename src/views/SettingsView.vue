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
              <span class="menu-item__desc">歌词显示、动画效果、画质档位与性能测试</span>
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
        <button class="menu-item" v-ripple @click="page = 'ai'">
          <div class="menu-item__left">
            <span class="menu-item__icon" style="background: rgba(129,140,248,0.15); color: #818cf8">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                <path d="M12 2a4 4 0 1 0 0 8 4 4 0 1 0 0-8z"/>
                <path d="M8 14c-3.3 0-6 2.7-6 6v1h20v-1c0-3.3-2.7-6-6-6H8z"/>
                <path d="M17.5 5.5c1.5 0 3 1 3.5 2.5M6.5 5.5c-1.5 0-3 1-3.5 2.5"/>
              </svg>
            </span>
            <div class="menu-item__text">
              <span class="menu-item__title">AI 推荐</span>
              <span class="menu-item__desc">模型缓存路径</span>
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
            <span class="setting-desc" v-if="settingsStore.fpsAdaptive">
              自适应：屏幕 {{ settingsStore.measuredRefresh }}Hz，实际按 <b>{{ settingsStore.effectiveWordAnimFps }}fps</b>（上限 240）
            </span>
            <span class="setting-desc" v-else>控制卡拉OK扫过的刷新率（当前：<b>{{ settingsStore.wordAnimFps }} fps</b>）</span>
          </div>
          <div class="setting-fps">
            <el-switch v-model="settingsStore.fpsAdaptive" active-text="自适应" inactive-text="固定" />
            <el-slider
              :model-value="settingsStore.wordAnimFps"
              :min="24" :max="240" :step="1"
              :disabled="settingsStore.fpsAdaptive"
              class="setting-slider"
              :marks="FPS_MARKS"
              @input="onFpsInput"
              @change="onFpsChange"
            />
          </div>
        </div>
        <div class="setting-row" v-if="settingsStore.fpsAdaptive">
          <div class="setting-label">
            <span class="setting-title">刷新率检测</span>
            <span class="setting-desc">实测当前屏幕刷新率（更换显示器后可重新检测）</span>
          </div>
          <el-button size="small" @click="redetectRefresh">重新检测</el-button>
        </div>
        <div class="setting-row">
          <div class="setting-label">
            <span class="setting-title">律动响应帧率</span>
            <span class="setting-desc">全屏歌词页光球随音频的更新频率（低帧更省电，视觉差异小）</span>
          </div>
          <el-radio-group v-model="settingsStore.rhythmFps" @change="settingsStore.saveSettings()">
            <el-radio-button :value="30">30</el-radio-button>
            <el-radio-button :value="60">60</el-radio-button>
          </el-radio-group>
        </div>
      </section>

      <!-- 画质档位与性能参考（与播放界面合并） -->
      <section class="settings-section">
        <h3>画质档位</h3>
        <el-radio-group v-model="settingsStore.qualityPreset" @change="onPresetChange">
          <el-radio-button value="auto">自动</el-radio-button>
          <el-radio-button value="low">低</el-radio-button>
          <el-radio-button value="medium">中</el-radio-button>
          <el-radio-button value="high">高</el-radio-button>
          <el-radio-button value="custom">自定义</el-radio-button>
        </el-radio-group>
        <p class="hint">
          自动：依据性能测试推荐档位；低/中/高：套用对应效果组合；自定义：手动调整上方任意开关后自动切换。
        </p>
      </section>

      <section class="settings-section">
        <h3>性能参考</h3>
        <p class="hint">
          基准测试会叠加一版全屏歌词页同款动态流光，采样 5 秒真实帧率与长任务，给出推荐档位（不影响当前播放）。
        </p>
        <el-button type="primary" :loading="perf.status === 'running'" @click="startBenchmark">
          {{ perf.status === 'running' ? '测试中...' : (perf.result || cachedBench ? '重新测试' : '运行性能测试') }}
        </el-button>

        <div v-if="perf.status === 'running'" class="perf-run">
          <el-progress :percentage="perf.progress" />
          <p class="hint">正在测量帧率... 实时 FPS：<strong>{{ perf.liveFps }}</strong></p>
        </div>

        <div v-else-if="perf.result" class="perf-result">
          <p>平均帧率 <strong>{{ perf.result.fps }}</strong> FPS · 长任务 <strong>{{ perf.result.longMs }}</strong> ms · 性能分 <strong>{{ perf.result.score }}</strong></p>
          <p>推荐档位：<el-tag type="success">{{ tierLabel(perf.result.tier) }}</el-tag></p>
          <el-button type="primary" size="small" @click="applyBenchmarkTier">应用推荐档位</el-button>
        </div>

        <div v-else-if="cachedBench" class="perf-result">
          <p class="hint">上次测试：{{ cachedBench.fps }} FPS · 推荐 {{ tierLabel(cachedBench.tier) }}</p>
          <el-button size="small" @click="startBenchmark">重新测试</el-button>
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

    <!-- 二级页：AI 推荐 -->
    <template v-if="page === 'ai'">
      <header class="sub-header">
        <button class="sub-header__back" v-ripple @click="page = 'menu'">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M15.41 7.41L14 6l-6 6 6 6 1.41-1.41L10.83 12z"/></svg>
        </button>
        <h1 class="sub-header__title">AI 推荐</h1>
      </header>
      <section class="settings-section">
        <div class="setting-row">
          <div class="setting-label">
            <span class="setting-title">模型缓存路径</span>
            <span class="setting-desc">E5 文本模型（~2.2GB）+ MERT 音频模型（~200MB）的存放目录</span>
          </div>
        </div>
        <div style="padding: 0 20px; margin-bottom: 16px;">
          <div style="display: flex; gap: 8px; align-items: center;">
            <span v-if="!modelDirInput" style="color: var(--text-secondary); font-size: 13px;">默认: {{ modelDefaultPath }}</span>
            <span v-else class="model-path-text">{{ modelDirInput }}</span>
            <el-button @click="pickModelDir" style="flex-shrink: 0;">
              📁 选择文件夹
            </el-button>
            <el-button
              v-if="modelDirInput"
              @click="modelDirInput = ''"
              link
              type="danger"
              style="flex-shrink: 0;"
            >
              清除
            </el-button>
          </div>
          <div style="display: flex; gap: 8px; margin-top: 8px;">
            <el-button type="primary" @click="saveModelDir" :loading="savingModelDir">
              保存
            </el-button>
          </div>
          <div v-if="modelDirSaved" style="margin-top: 8px; font-size: 12px; color: var(--color-success, #22c55e);">
            {{ needRestart ? '已保存。模型已加载，下次启动生效。' : '已保存，下次生成向量时生效。' }}
          </div>
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
import { ref, watch } from 'vue'
import { useSettingsStore } from '@/stores/settings'
import { usePerformanceStore } from '@/stores/performance'
import { useScrollMemory } from '@/composables/useScrollMemory'

const settingsStore = useSettingsStore()
const perf = usePerformanceStore()
const page = ref('menu')

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
const FPS_MARKS = Object.fromEntries(FPS_OPTIONS.map((v) => [v, String(v)]))

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

.model-path-text {
  font-size: 13px; color: var(--accent-color, #6366f1);
  max-width: 300px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}

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

.setting-fps {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 1;
  min-width: 0;
}
.setting-fps .setting-slider {
  flex: 1;
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
