// 全局浮层关闭机制：全屏播放页 / 播放队列等浮层在跳转后需要统一收回。
let _closeOverlays = null

export function registerOverlaysCloser(fn) {
  _closeOverlays = fn
}

export function closeOverlays() {
  if (_closeOverlays) _closeOverlays()
}
