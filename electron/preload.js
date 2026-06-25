const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('electronAPI', {
  // 窗口控制
  minimize: () => ipcRenderer.send('window:minimize'),
  maximize: () => ipcRenderer.send('window:maximize'),
  close: () => ipcRenderer.send('window:close'),
  isMaximized: () => ipcRenderer.invoke('window:isMaximized'),
  onMaximizeChange: (callback) => {
    ipcRenderer.on('window:maximizeChange', (_event, value) => callback(value))
  },
  fullscreen: () => ipcRenderer.send('window:fullscreen'),
  isFullscreen: () => ipcRenderer.invoke('window:isFullscreen'),
  onFullscreenChange: (callback) => {
    ipcRenderer.on('window:fullscreenChange', (_event, value) => callback(value))
  },

  // 文件夹选择
  selectFolder: () => ipcRenderer.invoke('dialog:selectFolder'),

  // 音乐扫描（仅返回文件路径）
  scanMusic: (dirPaths) => ipcRenderer.invoke('music:scan', dirPaths),

  // 文件路径转 melodybox:// 协议 URL
  pathToUrl: (filePath) => ipcRenderer.invoke('music:pathToUrl', filePath),

  // 获取音频服务器端口
  getAudioServerPort: () => ipcRenderer.invoke('audio:getPort'),

  // Windows 主题色
  getAccentColor: () => ipcRenderer.invoke('system:getAccentColor'),

  // 桌面歌词窗口控制（主窗口使用）
  lyricsOpen: () => ipcRenderer.send('lyrics:open'),
  lyricsClose: () => ipcRenderer.send('lyrics:close'),
  lyricsUpdate: (data) => ipcRenderer.send('lyrics:update', data),
  onLyricsWindowClosed: (callback) => {
    ipcRenderer.on('lyrics:windowClosed', () => callback())
  },

  // 桌面歌词数据接收（歌词窗口使用）
  onLyricsData: (callback) => {
    ipcRenderer.on('lyrics:data', (_event, data) => callback(data))
  }
})
