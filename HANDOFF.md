# MelodyBox 项目交接文档（供新 Agent 使用）

> 本文档由上一开发阶段整理，供无上下文的协作 Agent 快速接管。遇到与代码不一致处，以代码为准。

## 1. 项目定位

「融合 AI 语义分析的音乐智能推荐与播放系统」毕业设计。

架构形态：

- 客户端（C/S）：Electron + Vue 3，桌面音乐播放器。
- 管理端（B/S）：Flask 托管 `dist/admin.html`，浏览器访问 `http://<host>:5000/admin`。
- 后端：Flask（`Code/backend/`），本地 SQLite，含 AI 推理（文本/音频向量）。

## 2. 技术栈

- 前端：Vite 5、Vue 3（`<script setup>`）、Pinia、vue-router、Element Plus、GSAP、@vueuse/core（虚拟列表）。
- 样式：CSS 变量集中在 `src/assets/styles/global.css`，含液态玻璃变量 `--glass-*`、深浅色主题。
- 桌面端：Electron（main/preload 分离、contextIsolation）。
- 后端：Flask + sqlite3 + numpy，推荐引擎在 `backend/services/`（embedding/vectors/recommender/profile），配置在 `backend/config/recommend_config.py`。
- AI 模型：`intfloat/multilingual-e5-large`（文本 1024 维）、`MERT-v1-95M`（音频 768 维），用 fastembed/ONNX 加载，`backend/services/embedding.py`。

## 3. 启动与构建

- 开发启动（Windows）：`Code/start-dev.bat`
  - 并行：Flask(5000) + Vite + Electron；Vite 端口自动选择，写 `.vite-port`/`.vite-ready`。
  - 这解决了 Windows 端口排除区（5200 因 Hyper-V/WSL 预留会 `EACCES`）导致的启动失败。
- 单独命令：
  - `npm run electron:dev`（preelectron:dev 先找端口）
  - `npm run dev`（纯 Vite）、`npm run flask`
  - 打包：`npm run electron:build` / `npm run electron:build:quick`
- 验证：`npm run build`。

> 注意：改动 `electron/main.js` 或 preload 后必须**完全重启应用**，热更新不生效。

## 4. 目录地图（重点）

- `Code/electron/main.js`：窗口创建、IPC、音频服务器(51234/随机)、播放会话文件 `%LOCALAPPDATA%/melodybox/playback.json`。
- `Code/electron/preload.js`：暴露 `window.electronAPI`。
- `Code/src/App.vue`：全局布局、页面切换、沉浸状态（5 秒空闲隐藏鼠标/控件）。
- `Code/src/stores/player.js`：播放器核心（队列/音频/播放模式/会话持久化）。
- `Code/src/stores/library.js`：曲库/艺术家/专辑聚合。
- `Code/src/stores/settings.js`：主题/歌词/桌面歌词设置。
- `Code/src/components/player/`：PlayerBar、NowPlayingPanel（全屏歌词）、DesktopLyrics（主窗口发送器）、DesktopLyricsView（桌面歌词窗口接收端，位于 `views/`）。
- `Code/src/components/music/`：TrackTable、MusicCard、ContextMenu、ListPageHeader（单行页头）。
- `Code/src/composables/useTrackList.js`：右键菜单/多选统一逻辑。
- `Code/src/utils/format.js`：LRC 解析（parseLRC）、computeActiveSet、`LYRIC_GAP_FILL_LIMIT=10`。
- `Code/src/utils/toast.js`：项目自定义 toast（无侵入右下角），别用 element-plus 的 ElMessage。
- `Code/src/config/api.js`：API base/音频端口。
- `Code/backend/`：路由 `routes/`、服务 `services/`、测试工具 `tools/`。

## 5. 最近重点实现（已经稳定，不要回退）

### 5.1 播放会话持久化

- 写入位置：Electron 主进程 `%LOCALAPPDATA%/melodybox/playback.json`，通过 IPC `session:savePlayback/loadPlayback`。
- 前端 `player.js`：`saveSessionSoon` 节流 1 秒保存队列/索引/进度；恢复不自动播放，预加载音频，元数据加载后 seek 到上次进度。
- 该方案规避了 localStorage 按 origin（开发端口随机）隔离的问题。

### 5.2 桌面歌词（复杂，接手请重点看）

- 主窗口 `DesktopLyrics.vue` 只负责推送，不再渲染内联歌词：
  - `structure`（切歌/首帧：lines、索引、overlap、upcoming、settings）
  - `state`（行/重叠/设置变化，也携带 lines 兜底）
  - `tick`（每 250ms：真实时间 + remaining）
- 歌词窗口 `DesktopLyricsView.vue` 按 type 处理；三点行必须在 `<template v-for>` **内部**（否则 index 取不到，之前踩过）。
- IPC 发送前必须 `JSON.parse(JSON.stringify(payload))`，否则响应式代理/循环引用导致 Electron 克隆失败静默丢失（已修复；曾出现"structure 发 51 行但歌词窗口只收到 tick"）。
- 窗口：高度按行数锁定，宽度用户自由拖（`lyricsResize` 以窗口中心为锚），拖拽时 `resize` 事件触发 `_activeRemeasure` 实时重测溢出/对齐范围（滚动进度不变）。
- **横向羽化（已解决，勿回退 mask 方案）**：本窗口渲染器里，mask 挂在 transform 滚动容器内部（文本 `<p>` 或 `.dl-line__inner` 合成层）一律不渲染；WAAPI/合成器驱动的动画在 masked 视口内会被冻结在首帧。最终方案：mask 挂在 `.lyrics-viewport`（滚动容器之外），羽化宽度由 JS 按各文本行的当前裁剪量动态写入（对齐端零羽化，保证行首/行尾完整可见）；跑马灯因此改用 rAF 主循环写 `style.transform`（~30fps 跳帧），普通行行首→行尾对称往返（两端各停 12%），逐字行滚动跟随演唱点（锚定可视区 35% 处，clamp 到行首/行尾对齐范围）。逐字行必须套 `.dl-line__text` 包裹层供整体位移。
- 活跃行 font-size 恒为基础字号（`--dl-active-*` 变量已定义但无 CSS 消费），变大纯靠 inner 的 `transform: scale`，不影响布局测量，`scrollWidth`/`offsetLeft` 可直接用。
- 后续迭代补充（勿回退）：歌曲信息合成行**整首歌常驻**结构，视图索引 = 真实索引 + 1（`upcomingNext`/`isPrev`/三点插入位均 +1）；跑马灯溢出按**视觉宽度**（layout × scale）判定，静止期贴左 6px 零左羽化；三点只在**真实空区**显示（与全屏同口径：`computeActiveSet` 活跃守卫），切歌瞬间 sender 用 `switchingTrack` 抑制假三点；三点出现窗口增高 + 顶对齐，离场 600ms 移除时无动画反向补偿滚动量，结构替换时 `resetHintForStructure` 复位离场状态；跑马灯/卡拉OK均有 600ms 自校准与 resize 实时重测，定时器统一清理；对齐/羽化全部基于实测 `offsetLeft` 反推（`computeNaturalVisual`），不要恢复居中几何假设。

### 5.3 全屏歌词（NowPlayingPanel）

- 空区与活跃行统一 `repositionToCurrent()`（打开面板与窗口 resize 共用）。
- 多行公平模型；三点逐点放大/淡出（`dotScaleFor`/`dotFading`）；无结束时间戳行 gap 近似为"下一句起 - 本行起"。

### 5.4 单行页头（ListPageHeader）

- 五个列表页已接入：音乐库、专辑列表、艺术家列表、播放历史、播放次数。
- 特性：标题+计数、播放模式按钮（左键循环切换/右键玻璃二级菜单）、搜索（图标展开输入框）、排序、筛选、多选、右侧插槽。
- 专辑/艺术家详情页：删除独立工具行，播放全部/多选并入顶部大标题行。
- 推荐详情页：未改造（本就是单行封面+标题+播放全部），可后续统一。
- 渐进式模糊（顶部玻璃+渐变 mask）是下一步目标，`ListPageHeader` 已带玻璃+sticky，只差渐变 mask。

### 5.5 卡片文本与交互

- 卡片名/艺术家：`block + width:fit-content + max-width:100% + margin:auto + text-align:left + ellipsis`（短文本居中、长文本从左省略、不挤行）。**不要**用两层 inline-block（会导致标题和艺术家同行）。
- 封面：`width:min(140px,100%); height:auto; aspect-ratio:1`（此前固定 140px 在小卡片会溢出、hover 不居中）。
- 艺术家/专辑文本交互：用 `<router-link>` 多个，分隔符为**纯 span** `/`（`.col-title__sep`），不要做成可点链接。
- 艺术家详情页右键：多艺术家才有"跳转艺术家"且二级菜单剔除当前歌手；单艺术家不显示该项。
- 专辑详情页右键：不显示"跳转专辑"（`buildMenuItems('album', ...)`）。

### 5.6 搜索/排序/筛选

- 音乐库排序选项已含"创建时间/修改时间"，但**后端是否已存并支持排序需确认**（字段：`created_at`、`file_mtime`；未实现则前端 fallback 或补扫描字段）。
- 流派筛选已收进"筛选"面板（funnel 图标），来源（全部/本地/云端）同面板。

## 6. 已知问题/待办清单

1. ~~【高】桌面歌词羽化视觉不生效~~（已解决，见 5.2：mask 挂 `.lyrics-viewport` + JS 动态羽化 + rAF 跑马灯）。
2. 【高】渐进式模糊：给顶部单行加 `backdrop-filter` + `mask-image` 渐变（参考 iOS 控制中心；注意 mask 与合成层可能不生效，可用 opacity 渐变层兜底）。
3. 【中】文件创建/修改时间排序字段与后端扫描确认。
4. 【中】推荐详情页是否统一组件/玻璃头部（可选）。
5. 【待确认】会员体系、管理员端细化、性能/画质分级（用户早前提过 1.1、2.13 等，是否已实现以代码为准）。
6. 【可选】图标库统一（建议 Lucide/Phosphor，避免混用 emoji/手写 SVG）。
7. 【可选】RAG/LLM：目前只有检索（E5/MERT 向量），无生成模型；开题无需真 RAG。

## 7. 开发注意事项（踩坑记录）

- 在 Codex 沙箱：构建用已批准命令，如 `npm run build 2>&1 | Select-String -Pattern "built in|error|ERROR|Could not resolve" | Select-Object -Last 10`；`Get-Content` 后不要接 `Select-Object`（会 740）；优先 `rg`。
- `git`：仓库根在 `Code/`；`git add -A`/`status` 可直接执行；`commit` 需提升权限；`git push` 用 workdir=Code 裸执行。
- 「提交推送」是用户惯例：功能完成后征询，其说"提交推送"就执行。
- 用户常要求"先仅思考/先排查，不修改"，务必遵守。
- 全屏/桌面歌词用 `translate3d` 滚动的行高/offsetTop 受三点行显隐影响，改动显隐要配套补偿；三点行用透明度+延迟移除（`hintVisible/hintLeaving`）。
- Electron 拖拽区（`-webkit-app-region: drag`）不会派发 DOM 鼠标事件；需 hover 的地方不要整窗 drag（桌面歌词 hover 已由主进程 cursor 坐标判断）。

## 8. 给新 Agent 的启动建议

1. 先读本文件 + `global.css` + `App.vue` + `player.js`，了解状态与样式语言。
2. 用 `start-dev.bat` 跑起来，打开主窗口/歌词窗口 DevTools 验证。
3. 改前先 `rg` 定位；小步提交。
4. 遇到视觉问题优先让用户提供截图/Console 日志，可加临时诊断日志并在修复后移除。
5. 所有 UI 改动保持：圆角 14px、`--glass-*` 变量、深浅色自适应、动效 0.2~0.6s 缓动。
