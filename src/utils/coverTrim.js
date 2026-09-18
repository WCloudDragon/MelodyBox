/**
 * 封面黑边裁剪：检测近黑边缘并裁剪（动画 OST 常见「方形画布印竖版海报、两侧留黑」）。
 * 模块级 LRU 缓存（dataURL 体积大，限 40 张）；裁剪版供「全屏歌词页 ↔ 播放栏」
 * 飞行动画链路统一显示，落位前后内容零跳变。
 * 像素检测要求 canvas 未污染：封面跨域（file:// 打包 → http 后端）时需后端 CORS 头，
 * 项目后端 CORS(app) 已全局开启；检测失败静默回落原图（src=null）。
 */
const trimCache = new Map()
const TRIM_CACHE_MAX = 40

export async function getTrimmedCover(url) {
  if (!url) return null
  if (trimCache.has(url)) {
    const hit = trimCache.get(url)
    trimCache.delete(url); trimCache.set(url, hit) // LRU 触达置新
    return hit
  }
  let result = { src: null, ratio: null, failed: true }
  try {
    // 必须带 crossOrigin 加载：canvas 像素检测要求图未污染（跨域需后端 CORS 头配合）
    const img = await new Promise(resolve => {
      const im = new Image()
      im.crossOrigin = 'anonymous'
      im.onload = () => resolve(im)
      im.onerror = () => resolve(null)
      im.src = url
    })
    if (img && img.naturalWidth > 0) {
      const w = img.naturalWidth, h = img.naturalHeight
      // 缩小到最长边 96px 检测内容包围盒，避免全尺寸像素遍历
      const S = 96
      const sw = h >= w ? S : Math.max(1, Math.round(S * w / h))
      const sh = w > h ? S : Math.max(1, Math.round(S * h / w))
      const c = document.createElement('canvas')
      c.width = sw; c.height = sh
      const ctx = c.getContext('2d', { willReadFrequently: true })
      ctx.drawImage(img, 0, 0, sw, sh)
      const d = ctx.getImageData(0, 0, sw, sh).data
      let minX = sw, minY = sh, maxX = -1, maxY = -1
      for (let y = 0; y < sh; y++) {
        for (let x = 0; x < sw; x++) {
          const i = (y * sw + x) * 4
          // 近黑像素视为背景（阈值容纳 JPEG 压缩噪声）
          if (d[i] > 24 || d[i + 1] > 24 || d[i + 2] > 24) {
            if (x < minX) minX = x
            if (x > maxX) maxX = x
            if (y < minY) minY = y
            if (y > maxY) maxY = y
          }
        }
      }
      // 内容占满（裁剪收益过小）→ 不裁剪，避免正常封面被误缩
      if (maxX >= 0) {
        const cw = (maxX + 1 - minX) / sw
        const ch = (maxY + 1 - minY) / sh
        if (cw < 0.98 || ch < 0.98) {
          const sx = Math.floor(minX / sw * w)
          const sy = Math.floor(minY / sh * h)
          const ex = Math.ceil((maxX + 1) / sw * w)
          const ey = Math.ceil((maxY + 1) / sh * h)
          const tw = Math.min(w, ex - sx), th = Math.min(h, ey - sy)
          if (tw > 0 && th > 0) {
            const c2 = document.createElement('canvas')
            c2.width = tw; c2.height = th
            c2.getContext('2d').drawImage(img, sx, sy, tw, th, 0, 0, tw, th)
            result = { src: c2.toDataURL('image/jpeg', 0.92), ratio: tw / th, failed: false }
          }
        } else {
          // 无黑边：返回原图比例（消费方按原比例显示，与有黑边时的框体逻辑统一）
          result = { src: null, ratio: w / h, failed: false }
        }
      }
    }
  } catch { /* 检测失败回落原图 */ }
  // 检测完成（无论是否裁剪）的结果都缓存——比例是确定的；
  // 仅「图都加载不了」的失败不缓存，下次调用自动重检（避免后端未就绪时固化失败）
  if (!result.failed) {
    trimCache.set(url, result)
    while (trimCache.size > TRIM_CACHE_MAX) {
      trimCache.delete(trimCache.keys().next().value)
    }
  } else {
    console.warn('[coverTrim] 封面加载失败，本次回落（下次自动重试）:', url?.slice(0, 60))
  }
  return result
}
