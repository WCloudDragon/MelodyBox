# MelodyBox - 沉浸式桌面音乐播放器

基于 **Vue 3 + Electron** 的高交互沉浸式桌面音乐播放系统，后端采用 **Python Flask + SQLite**。

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端框架 | Vue 3 (Composition API) |
| 桌面容器 | Electron 28+ |
| UI 组件 | Element Plus 2.x |
| 状态管理 | Pinia 2.x |
| 路由 | Vue Router 4.x |
| 动画引擎 | GSAP 3.x |
| 虚拟滚动 | @vueuse/core |
| 后端框架 | Flask 2.x |
| 数据库 | SQLite 3（`melodybox.db`） |
| 音乐解析 | Mutagen |

## 项目结构

```
melodybox/
├── electron/                  # Electron 主进程
│   ├── main.js                # 主进程（窗口管理、melodybox:// 协议音频流）
│   └── preload.js             # 预加载脚本（IPC 桥接、selectFolder）
├── src/                       # Vue 前端源码
│   ├── main.js               # Vue 入口
│   ├── App.vue               # 根组件
│   ├── router/               # Vue Router 路由配置
│   ├── stores/               # Pinia 状态管理
│   │   ├── player.js         # 播放器状态
│   │   ├── library.js        # 音乐库状态
│   │   ├── playlist.js       # 歌单状态
│   │   └── settings.js       # 设置状态
│   ├── components/           # 可复用组件
│   │   ├── layout/          # 布局组件（TitleBar, Sidebar）
│   │   ├── player/          # 播放器组件（PlayerBar, QueuePanel）
│   │   ├── lyrics/          # 歌词组件（LyricsDisplay）
│   │   ├── music/           # 音乐组件（MusicCard）
│   │   └── LazyCover.vue    # 封面懒加载组件
│   ├── views/               # 页面视图
│   │   ├── HomeView.vue         # 首页
│   │   ├── LibraryView.vue      # 音乐库（虚拟滚动列表）
│   │   ├── AlbumView.vue       # 专辑详情
│   │   ├── ArtistView.vue      # 歌手详情
│   │   ├── PlaylistView.vue    # 歌单详情
│   │   └── SettingsView.vue    # 设置
│   ├── utils/               # 工具函数
│   └── assets/              # 静态资源
├── backend/                  # Flask 后端
│   ├── app.py               # Flask 入口（初始化 SQLite、自动建表）
│   ├── config/config.py     # 配置（DB_PATH、封面缓存目录）
│   ├── routes/__init__.py   # API 路由（8 个端点）
│   └── services/scanner.py  # mutagen 元数据解析 + 增量扫描
├── start-dev.bat            # 一键启动（Flask + Vite + Electron）
├── build-flask.bat          # Flask 打包为独立 exe
├── package.json             # npm scripts
└── vite.config.js
```

## 已实现功能

- [x] 本地音乐文件扫描（递归扫描目录）
- [x] 音乐元数据读取（标题、歌手、专辑、封面、歌词等）
- [x] 支持 MP3 / FLAC / WAV / OGG / AAC / M4A / WMA / APE 格式
- [x] 播放控制（播放/暂停、上一首/下一首、进度控制）
- [x] 音量控制与静音
- [x] 播放模式切换（顺序/随机/单曲循环/列表循环）
- [x] 播放列表管理
- [x] 歌单创建与管理
- [x] 歌词显示与滚动动画（Apple Music 风格逐字高光效果）
- [x] 音乐库搜索、筛选、排序
- [x] 列表/网格两种查看模式
- [x] 专辑/歌手聚合浏览
- [x] 外观设置（主题色等）
- [x] Electron 无边框窗口
- [x] SQLite 数据库持久化存储
- [x] 增量扫描（仅处理新增/修改/删除的文件）
- [x] 封面懒加载（IntersectionObserver）
- [x] 虚拟滚动（900+ 歌曲列表秒开）

## 快速开始

### 前提条件

- Node.js 20.x LTS
- Python 3.10+（已安装于 `D:\flask_env`）
- MySQL **不需要**，使用 SQLite，无需安装数据库服务

### 安装依赖

```bash
cd "d:\Codeing\Language\毕业设计\项目源代码"
npm install
```

### 开发模式（推荐）

双击 `start-dev.bat`，自动依次启动：
1. Flask API 服务（`http://127.0.0.1:5000`）
2. Vite 开发服务器（`http://localhost:5173`）
3. Electron 桌面窗口

> 如果想分别启动：
> ```bash
> # 终端 1
> npm run flask
>
> # 终端 2
> npm run electron:dev
> ```

### 打包为桌面应用

```bash
npm run electron:build
```

生成 `release/MelodyBox Setup.exe`，用户安装后双击即用，**无需安装 Python / MySQL / Node**。

## Flask API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/health` | GET | 健康检查 |
| `/api/music/songs` | GET | 分页获取歌曲列表（支持搜索/排序/筛选） |
| `/api/music/songs/<id>` | GET | 获取单首歌曲 |
| `/api/music/songs/by-path` | GET | 根据路径获取歌曲 |
| `/api/music/albums` | GET | 获取所有专辑 |
| `/api/music/artists` | GET | 获取所有艺术家 |
| `/api/music/genres` | GET | 获取所有流派 |
| `/api/music/scan` | POST | 扫描目录并入库 |
| `/api/music/scan-status` | GET | 获取库统计信息 |
| `/api/music/cover` | GET | 提供封面图片 |

## 支持的音乐格式

| 格式 | 扩展名 | 元数据支持 | 备注 |
|------|--------|-----------|------|
| MP3 | .mp3 | ID3v1/v2 | 最常用格式 |
| FLAC | .flac | Vorbis Comment | 无损压缩 |
| WAV | .wav | RIFF INFO | 无压缩 |
| OGG | .ogg | Vorbis Comment | 开源格式 |
| AAC | .aac, .m4a | MP4 tags | Apple 格式 |
| WMA | .wma | ASF tags | Windows 格式 |
| APE | .ape | APEv2 | 无损格式 |

## 使用说明

1. 启动应用后，点击首页的"导入本地音乐"按钮
2. 选择包含音乐文件的文件夹，应用将自动扫描子目录
3. 扫描完成后（首次耗时稍长），可在"音乐库"页面浏览、搜索和排序
4. 双击歌曲或点击播放按钮开始播放
5. 点击播放栏上的歌词按钮显示歌词面板
6. 在音乐库中点击右键菜单可将歌曲添加到歌单
7. 再次启动时无需重新扫描，应用自动从 SQLite 数据库加载
8. 点击"刷新"按钮可增量更新音乐库（仅处理新增/修改/删除的文件）
