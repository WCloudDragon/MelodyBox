const { app, BrowserWindow, ipcMain, dialog } = require('electron')
const { execSync } = require('child_process')
const path = require('path')
const fs = require('fs')
const os = require('os')
const { spawn } = require('child_process')
const http = require('http')

// ==================== Flask 后端管理 ====================

let flaskProcess = null

function getFlaskPath() {
  // app.isPackaged 是 Electron 官方 API，打包后为 true，开发模式为 false
  if (!app.isPackaged) return null
  const exeName = process.platform === 'win32' ? 'melodybox-api.exe' : 'melodybox-api'
  return path.join(process.resourcesPath, 'flask-dist', exeName)
}

function startFlask() {
  const flaskPath = getFlaskPath()
  if (!flaskPath) {
    console.log('[flask] 开发模式，跳过自动启动')
    return Promise.resolve()
  }
  if (!fs.existsSync(flaskPath)) {
    console.error('[flask] 未找到 Flask 可执行文件:', flaskPath)
    return Promise.resolve()
  }

  console.log('[flask] 启动:', flaskPath)
  const internalDir = path.join(path.dirname(flaskPath), '_internal')
  flaskProcess = spawn(flaskPath, [], {
    cwd: path.dirname(flaskPath),
    stdio: ['ignore', 'pipe', 'pipe'],
    env: { ...process.env, PYTHONHOME: internalDir }
  })

  flaskProcess.stdout.on('data', data => {
    const msg = data.toString().trim()
    if (msg) console.log('[flask]', msg)
  })
  flaskProcess.stderr.on('data', data => {
    const msg = data.toString().trim()
    if (msg) console.log('[flask]', msg)
  })
  flaskProcess.on('error', err => console.error('[flask] 启动失败:', err.message))
  flaskProcess.on('exit', code => {
    console.log('[flask] 退出, code:', code)
    flaskProcess = null
  })

  // 等待 Flask 就绪
  return new Promise((resolve) => {
    const check = () => {
      const req = http.get('http://127.0.0.1:5000/api/health', (res) => {
        if (res.statusCode === 200) {
          console.log('[flask] 就绪')
          resolve()
        } else {
          setTimeout(check, 500)
        }
      })
      req.on('error', () => setTimeout(check, 500))
      req.setTimeout(2000, () => { req.destroy(); setTimeout(check, 500) })
    }
    check()
  })
}

function stopFlask() {
  if (flaskProcess) {
    console.log('[flask] 正在关闭...')
    if (process.platform === 'win32') {
      spawn('taskkill', ['/pid', String(flaskProcess.pid), '/f', '/t'])
    } else {
      flaskProcess.kill('SIGTERM')
    }
    flaskProcess = null
  }
}

// 封面缓存目录
const coverDir = path.join(os.tmpdir(), 'melodybox-covers')
if (!fs.existsSync(coverDir)) fs.mkdirSync(coverDir, { recursive: true })

// ==================== 本地 HTTP 音频服务器 ====================

// Chromium 的 FFmpeg FLAC demuxer 对某些 FLAC 文件无法计算 PTS，导致播放失败。
// 解决方案：服务端用系统 FFmpeg 将 FLAC 实时转码为 WAV (PCM) 再返回给 Audio 元素。

let audioServer = null
let audioServerPort = 0

const AUDIO_MIME = {
  '.mp3': 'audio/mpeg', '.flac': 'audio/flac', '.wav': 'audio/wav',
  '.ogg': 'audio/ogg', '.m4a': 'audio/mp4', '.aac': 'audio/aac',
  '.wma': 'audio/x-ms-wma', '.ape': 'audio/ape'
}

// 检测 FFmpeg 可用性（优先使用内嵌的 ffmpeg.exe）
let ffmpegAvailable = false
let ffmpegPath = ''

function getFfmpegPath() {
  // 开发模式：项目根目录的 bin/ffmpeg.exe
  // 打包模式：resources/bin/ffmpeg.exe
  const devPath = path.join(__dirname, '..', 'bin', 'ffmpeg.exe')
  const packagedPath = path.join(process.resourcesPath, 'bin', 'ffmpeg.exe')
  const candidate = app.isPackaged ? packagedPath : devPath
  if (fs.existsSync(candidate)) {
    console.log(`[audio-server] 使用内嵌 FFmpeg: ${candidate}`)
    return candidate
  }
  // 回退到系统 PATH
  return 'ffmpeg'
}

try {
  ffmpegPath = getFfmpegPath()
  execSync(`"${ffmpegPath}" -version`, { stdio: 'ignore', timeout: 5000 })
  ffmpegAvailable = true
  console.log('[audio-server] FFmpeg 可用')
} catch {
  ffmpegPath = 'ffmpeg'
  console.warn('[audio-server] FFmpeg 不可用，FLAC 将使用 Chromium 原生解码（可能失败）')
}

// 解析 FLAC STREAMINFO，用于诊断日志
function parseFlacStreaminfo(filePath) {
  try {
    const fd = fs.openSync(filePath, 'r')
    const buf = Buffer.alloc(42)
    fs.readSync(fd, buf, 0, 42, 0)
    fs.closeSync(fd)
    if (!buf.subarray(0, 4).equals(Buffer.from('fLaC'))) return null

    const si = buf.subarray(8, 42)
    const minBlock = si.readUInt16BE(0)
    const maxBlock = si.readUInt16BE(2)
    const byte10 = si[10], byte11 = si[11], byte12 = si[12], byte13 = si[13]
    const sampleRate = (byte10 << 12) | (byte11 << 4) | (byte12 >> 4)
    const channels = ((byte12 & 0x0E) >> 1) + 1
    const bps = ((byte12 & 0x01) << 4) | ((byte13 & 0xF0) >> 4) + 1
    const totalSamplesLow = byte13 & 0x0F
    const totalSamples = (totalSamplesLow * 0x100000000) + si.readUInt32BE(14)
    return { sampleRate, channels, bitsPerSample: bps, totalSamples: Number(totalSamples),
      minBlockSize: minBlock, maxBlockSize: maxBlock,
      duration: totalSamples > 0 ? Number(totalSamples) / sampleRate : 0 }
  } catch { return null }
}

function startAudioServer() {
  return new Promise((resolve, reject) => {
    audioServer = http.createServer((req, res) => {
      try {
        const reqUrl = new URL(req.url, `http://127.0.0.1:${audioServerPort}`)
        if (reqUrl.pathname !== '/audio') { res.writeHead(404); res.end(); return }
        const filePath = reqUrl.searchParams.get('path')
        if (!filePath || !fs.existsSync(filePath)) { res.writeHead(404); res.end(); return }

        if (req.method === 'OPTIONS') {
          res.writeHead(204, {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET, HEAD, OPTIONS',
            'Access-Control-Allow-Headers': 'Range, Content-Type',
            'Access-Control-Max-Age': '86400'
          })
          res.end()
          return
        }

        const stat = fs.statSync(filePath)
        const fileSize = stat.size
        const ext = path.extname(filePath).toLowerCase()
        const range = req.headers.range
        const startTime = parseFloat(reqUrl.searchParams.get('start')) || 0

        console.log(`[audio] ${req.method} ${req.url} Range=${range || 'none'} ext=${ext} size=${fileSize} start=${startTime || 0}`)

        // CORS
        res.setHeader('Access-Control-Allow-Origin', '*')
        res.setHeader('Accept-Ranges', 'bytes')

        // === FLAC 文件：FFmpeg 解码为 WAV（保持原始采样率/位深，无损） ===
        // 注意：忽略 Range 请求，始终返回完整 WAV 流。
        // FFmpeg 输出的 WAV 头部中 data-size 是完整 PCM 大小，截断会导致解码错误（雪花噪音）。
        // Chromium 的 Audio 元素能在 WAV 内部直接 seek，不需要 HTTP Range。
        if (ext === '.flac' && ffmpegAvailable) {
          const info = parseFlacStreaminfo(filePath)
          if (info) {
            console.log(`[ffmpeg] FLAC: ${info.channels}ch ${info.sampleRate}Hz ${info.bitsPerSample}bit, blocksize ${info.minBlockSize}-${info.maxBlockSize}, ${info.duration.toFixed(1)}s`)
          } else {
            console.warn(`[ffmpeg] FLAC STREAMINFO 解析失败: ${path.basename(filePath)}`)
          }

          const bps = info?.bitsPerSample || 16
          const totalSamples = info?.totalSamples || 0
          const channels = info?.channels || 2
          const sampleRate = info?.sampleRate || 44100
          const bytesPerSample = Math.ceil(bps / 8)
          const pcmCodec = bps >= 32 ? 'pcm_s32le' : bps >= 24 ? 'pcm_s24le' : 'pcm_s16le'

          // 从起点开始的剩余采样数
          const startSample = Math.floor(startTime * sampleRate)
          const remainingSamples = Math.max(0, totalSamples - startSample)
          const wavDataSize = remainingSamples * channels * bytesPerSample
          const wavFileSize = 44 + wavDataSize

          const ffmpegArgs = ['-hide_banner', '-loglevel', 'error']
          if (startTime > 0) {
            // -ss 在 -i 之前：快速关键帧定位
            ffmpegArgs.push('-ss', startTime.toFixed(3))
          }
          ffmpegArgs.push('-i', filePath, '-f', 'wav', '-acodec', pcmCodec, 'pipe:1')

          let ffmpegCleaned = false
          const ffmpeg = spawn(ffmpegPath, ffmpegArgs,
            { stdio: ['ignore', 'pipe', 'pipe'] })

          const cleanupFfmpeg = () => {
            if (ffmpegCleaned) return
            ffmpegCleaned = true
            try { ffmpeg.kill('SIGKILL') } catch {}
            if (!res.writableEnded) {
              try { res.end() } catch {}
            }
          }

          // 客户端断连/关闭时立即清理，防止 write after end
          req.on('close', cleanupFfmpeg)
          res.on('close', cleanupFfmpeg)
          ffmpeg.on('error', () => {
            if (!res.headersSent) { try { res.writeHead(500) } catch {} }
            cleanupFfmpeg()
          })

          ffmpeg.stderr.on('data', d => {
            const msg = d.toString().trim()
            if (msg && !msg.includes('invalid sync code') && !msg.includes('decode_frame() failed')) {
              console.error('[ffmpeg]', msg)
            }
          })

          res.writeHead(200, {
            'Content-Type': 'audio/wav',
            'Content-Length': wavFileSize,
            'Accept-Ranges': 'bytes'
          })
          ffmpeg.stdout.pipe(res)
          return
        }

        // === 非 FLAC / FFmpeg 不可用：直接服务原始文件 ===
        const mime = AUDIO_MIME[ext] || 'application/octet-stream'

        if (range) {
          const parts = range.replace(/bytes=/, '').split('-')
          const start = Math.max(0, parseInt(parts[0]) || 0)
          const end = parts[1] ? Math.min(fileSize - 1, parseInt(parts[1])) : fileSize - 1
          if (start > end || start >= fileSize) {
            res.writeHead(416, { 'Content-Range': `bytes */${fileSize}` })
            res.end(); return
          }
          const isFull = start === 0 && end === fileSize - 1
          if (isFull) {
            res.writeHead(200, { 'Content-Type': mime, 'Content-Length': fileSize })
            const rs = fs.createReadStream(filePath)
            req.on('close', () => rs.destroy())
            res.on('close', () => rs.destroy())
            rs.pipe(res)
          } else {
            res.writeHead(206, {
              'Content-Type': mime,
              'Content-Range': `bytes ${start}-${end}/${fileSize}`,
              'Content-Length': end - start + 1
            })
            const rs = fs.createReadStream(filePath, { start, end })
            req.on('close', () => rs.destroy())
            res.on('close', () => rs.destroy())
            rs.pipe(res)
          }
        } else {
          res.writeHead(200, { 'Content-Type': mime, 'Content-Length': fileSize })
          const rs = fs.createReadStream(filePath)
          req.on('close', () => rs.destroy())
          res.on('close', () => rs.destroy())
          rs.pipe(res)
        }
      } catch {
        if (!res.headersSent) { res.writeHead(500); res.end() }
      }
    })

    audioServer.on('error', (err) => {
      console.error('[audio-server] 启动失败:', err.message)
      reject(err)
    })

    // 端口: 优先 51234，被占用则随机
    audioServer.listen(51234, '127.0.0.1', () => {
      audioServerPort = 51234
      console.log(`[audio-server] 启动在 http://127.0.0.1:${audioServerPort}`)
      resolve()
    }).on('error', () => {
      // 51234 被占用，随机端口
      audioServer.listen(0, '127.0.0.1', () => {
        audioServerPort = audioServer.address().port
        console.log(`[audio-server] 启动在 http://127.0.0.1:${audioServerPort}`)
        resolve()
      })
    })
  })
}

function stopAudioServer() {
  if (audioServer) {
    audioServer.close()
    audioServer = null
  }
}

console.log('[main] 主进程启动')

let mainWindow = null
let lyricsWindow = null
let _isFullScreen = false

// ==================== 桌面歌词窗口 ====================

function getLyricsWindowUrl() {
  const isDev = !app.isPackaged
  if (isDev) {
    return 'http://localhost:5173/#/desktop-lyrics'
  }
  return `file://${path.join(__dirname, '..', 'dist', 'index.html')}#/desktop-lyrics`
}

function createLyricsWindow() {
  if (lyricsWindow && !lyricsWindow.isDestroyed()) {
    lyricsWindow.show()
    lyricsWindow.focus()
    return
  }

  // 标记窗口是否成功显示过（防止崩溃触发反馈循环）
  let lyricsLoaded = false

  const { screen } = require('electron')
  const primaryDisplay = screen.getPrimaryDisplay()
  const { width: screenWidth, height: screenHeight } = primaryDisplay.workAreaSize

  lyricsWindow = new BrowserWindow({
    width: 800,
    height: 180,
    x: Math.round((screenWidth - 800) / 2),
    y: screenHeight - 220,
    frame: false,
    transparent: true,
    alwaysOnTop: true,
    skipTaskbar: true,
    resizable: false,
    hasShadow: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false
    },
    backgroundColor: '#00000000',
    show: false
  })

  lyricsWindow.setAlwaysOnTop(true, 'screen-saver')

  // macOS: 所有工作区可见；Windows: 跳过
  if (process.platform === 'darwin') {
    lyricsWindow.setVisibleOnAllWorkspaces(true)
  }

  const url = getLyricsWindowUrl()
  lyricsWindow.loadURL(url)

  // 渲染进程崩溃处理
  lyricsWindow.webContents.on('render-process-gone', (_event, details) => {
    console.error('[lyrics] 渲染进程崩溃:', details.reason, details.exitCode)
    if (lyricsWindow && !lyricsWindow.isDestroyed()) {
      lyricsWindow.close()
    }
    lyricsWindow = null
  })

  lyricsWindow.webContents.on('did-fail-load', (_event, errorCode, errorDescription) => {
    console.error('[lyrics] 页面加载失败:', errorCode, errorDescription)
  })

  lyricsWindow.once('ready-to-show', () => {
    if (lyricsWindow && !lyricsWindow.isDestroyed()) {
      lyricsWindow.show()
      lyricsLoaded = true
    }
  })

  lyricsWindow.on('closed', () => {
    const wasLoaded = lyricsLoaded
    lyricsWindow = null
    // 只有窗口成功显示后才通知主窗口（防止崩溃反馈循环）
    if (wasLoaded && mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send('lyrics:windowClosed')
    }
  })
}

function closeLyricsWindow() {
  if (lyricsWindow && !lyricsWindow.isDestroyed()) {
    lyricsWindow.close()
    lyricsWindow = null
  }
}

function updateLyricsData(data) {
  if (lyricsWindow && !lyricsWindow.isDestroyed()) {
    lyricsWindow.webContents.send('lyrics:data', data)
  }
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    minWidth: 900,
    minHeight: 600,
    frame: false,
    titleBarStyle: 'hidden',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false
    },
    backgroundColor: '#0a0a0a',
    show: false
  })

  const isDev = !app.isPackaged

  if (isDev) {
    mainWindow.loadURL('http://localhost:5173')
    mainWindow.webContents.openDevTools()
  } else {
    mainWindow.loadFile(path.join(__dirname, '..', 'dist', 'index.html'))
  }

  mainWindow.once('ready-to-show', () => {
    mainWindow.show()
  })

  // 窗口控制 IPC
  ipcMain.on('window:minimize', () => mainWindow.minimize())
  ipcMain.on('window:maximize', () => {
    mainWindow.isMaximized() ? mainWindow.unmaximize() : mainWindow.maximize()
  })
  ipcMain.on('window:close', () => mainWindow.close())
  ipcMain.handle('window:isMaximized', () => mainWindow.isMaximized())
  mainWindow.on('maximize', () => mainWindow.webContents.send('window:maximizeChange', true))
  mainWindow.on('unmaximize', () => mainWindow.webContents.send('window:maximizeChange', false))
  ipcMain.on('window:fullscreen', () => {
    _isFullScreen = !_isFullScreen
    mainWindow.setFullScreen(_isFullScreen)
  })
  ipcMain.handle('window:isFullscreen', () => _isFullScreen)
  mainWindow.on('enter-full-screen', () => {
    _isFullScreen = true
    mainWindow.webContents.send('window:fullscreenChange', true)
  })
  mainWindow.on('leave-full-screen', () => {
    _isFullScreen = false
    mainWindow.webContents.send('window:fullscreenChange', false)
  })
}

// ==================== 音乐文件扫描 ====================

const AUDIO_EXTENSIONS = ['.mp3', '.flac', '.wav', '.ogg', '.aac', '.m4a', '.wma', '.ape']

function scanDirectory(dirPath, results = []) {
  try {
    const entries = fs.readdirSync(dirPath, { withFileTypes: true })
    for (const entry of entries) {
      const fullPath = path.join(dirPath, entry.name)
      if (entry.isDirectory()) {
        scanDirectory(fullPath, results)
      } else if (entry.isFile()) {
        const ext = path.extname(entry.name).toLowerCase()
        if (AUDIO_EXTENSIONS.includes(ext)) {
          results.push(fullPath)
        }
      }
    }
  } catch (err) {
    console.error('扫描目录出错:', dirPath, err.message)
  }
  return results
}

// 扫描本地音乐文件
ipcMain.handle('music:scan', async (_event, dirPaths) => {
  const allFiles = []
  for (const dir of dirPaths) {
    if (fs.existsSync(dir)) {
      scanDirectory(dir, allFiles)
    }
  }
  return allFiles
})

// 选择文件夹
ipcMain.handle('dialog:selectFolder', async () => {
  const result = await dialog.showOpenDialog(mainWindow, {
    properties: ['openDirectory', 'multiSelections']
  })
  return result.canceled ? [] : result.filePaths
})

// ==================== 文件路径转音频 URL ====================

// 将本地文件路径转换为 HTTP 音频流 URL
function filePathToUrl(filePath) {
  return `http://127.0.0.1:${audioServerPort}/audio?path=${encodeURIComponent(filePath)}`
}

ipcMain.handle('music:pathToUrl', async (_event, filePath) => {
  return filePathToUrl(filePath)
})

// 暴露音频服务器端口给渲染进程
ipcMain.handle('audio:getPort', () => audioServerPort)

// 桌面歌词窗口 IPC
ipcMain.on('lyrics:open', () => createLyricsWindow())
ipcMain.on('lyrics:close', () => closeLyricsWindow())
ipcMain.on('lyrics:update', (_event, data) => updateLyricsData(data))
ipcMain.on('lyrics:resize', (_event, { width, height }) => {
  if (lyricsWindow && !lyricsWindow.isDestroyed()) {
    lyricsWindow.setSize(width, height)
  }
})

// ==================== Windows 主题色 ====================

ipcMain.handle('system:getAccentColor', async () => {
  try {
    // 从注册表读取 Windows DWM 主题色 (DWORD, AABBGGRR 格式)
    const raw = execSync(
      'powershell -NoProfile -Command "Get-ItemPropertyValue -Path \'HKCU:\\Software\\Microsoft\\Windows\\DWM\' -Name AccentColor"',
      { timeout: 3000 }
    ).toString().trim()
    const dword = parseInt(raw, 10)
    if (isNaN(dword)) return null
    // AABBGGRR → #RRGGBB
    const r = dword & 0xff
    const g = (dword >> 8) & 0xff
    const b = (dword >> 16) & 0xff
    return '#' + [r, g, b].map(c => c.toString(16).padStart(2, '0')).join('')
  } catch {
    return null
  }
})

// ==================== 应用生命周期 ====================

app.whenReady().then(async () => {
  // 启动 Flask 后端（生产环境自动启动，开发环境跳过）
  await startFlask()

  // 启动本地 HTTP 音频服务器
  await startAudioServer()

  createWindow()
})

app.on('window-all-closed', () => {
  closeLyricsWindow()
  stopFlask()
  stopAudioServer()
  if (process.platform !== 'darwin') app.quit()
})

app.on('before-quit', () => {
  closeLyricsWindow()
  stopFlask()
  stopAudioServer()
})

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow()
})
