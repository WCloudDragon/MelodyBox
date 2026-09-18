/**
 * 封面黑边检测（显示窗口化，不做数据裁剪）：
 * 检测「几乎全黑」的边缘行列，返回内容区窗口 box（inset 比例）与内容比例。
 * 消费方用 CSS object-view-box 按窗口显示原图 —— 原图数据零丢失，
 * bbox 错误只影响显示参数（调检测即修），随时可去掉窗口回到完整原图。
 * （动画 OST 常见「方形画布印竖版海报、两侧纯黑」→ 窗口取竖版内容区撑满显示）
 *
 * 缓存检测结论（窗口极小）；仅「图都加载不了」的失败不缓存，下次调用自动重检。
 * 像素检测要求 canvas 未污染：跨域需后端 CORS 头（项目后端 CORS(app) 已全局开启）。
 */
const trimCache = new Map()
const TRIM_CACHE_MAX = 40

/** box（比例 inset）→ CSS object-view-box 值 */
export function viewBoxStyle(box) {
  if (!box) return ''
  const p = v => (v * 100).toFixed(4).replace(/\.?0+$/, '')
  return `inset(${p(box.t)}% ${p(box.r)}% ${p(box.b)}% ${p(box.l)}%)`
}

export async function getTrimmedCover(url) {
  if (!url) return null
  if (trimCache.has(url)) {
    const hit = trimCache.get(url)
    trimCache.delete(url); trimCache.set(url, hit) // LRU 触达置新
    return hit
  }
  let result = { box: null, ratio: null, failed: true }
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
      // 缩小到最长边 96px 检测，避免全尺寸像素遍历
      const S = 96
      const sw = h >= w ? S : Math.max(1, Math.round(S * w / h))
      const sh = w > h ? S : Math.max(1, Math.round(S * h / w))
      const c = document.createElement('canvas')
      c.width = sw; c.height = sh
      const ctx = c.getContext('2d', { willReadFrequently: true })
      ctx.drawImage(img, 0, 0, sw, sh)
      const d = ctx.getImageData(0, 0, sw, sh).data
      // 逐列/行统计非黑像素占比：只有「几乎全黑」的边缘行列才算黑边。
      // 封面自身的暗色艺术设计（暗角、黑底文字/图案）边缘列非黑占比必超阈值，不会被误裁。
      const BLACK_RATIO = 0.02 // 边缘行列非黑像素占比 ≤2% 视为黑边（容忍压缩噪声亮点）
      const colNonBlack = new Array(sw).fill(0)
      const rowNonBlack = new Array(sh).fill(0)
      for (let y = 0; y < sh; y++) {
        for (let x = 0; x < sw; x++) {
          const i = (y * sw + x) * 4
          if (d[i] > 24 || d[i + 1] > 24 || d[i + 2] > 24) {
            colNonBlack[x]++
            rowNonBlack[y]++
          }
        }
      }
      const isBlackCol = x => colNonBlack[x] <= sh * BLACK_RATIO
      const isBlackRow = y => rowNonBlack[y] <= sw * BLACK_RATIO
      // 从四边向内收缩，跳过近全黑的边缘行列，得到保守的内容窗口
      let minX = 0, maxX = sw - 1, minY = 0, maxY = sh - 1
      while (minX < maxX && isBlackCol(minX)) minX++
      while (maxX > minX && isBlackCol(maxX)) maxX--
      while (minY < maxY && isBlackRow(minY)) minY--
      while (maxY > minY && isBlackRow(maxY)) maxY--
      const hasContent = maxX > minX || maxY > minY
      if (hasContent) {
        const cw = (maxX - minX + 1) / sw
        const ch = (maxY - minY + 1) / sh
        if (cw < 0.98 || ch < 0.98) {
          // 面积保护：窗口不足原图 55% 说明疑似把大面积内容当黑边（如全黑背景封面），拒绝开窗
          if (cw * ch >= 0.55) {
            result = {
              box: {
                l: minX / sw,
                t: minY / sh,
                r: 1 - (maxX + 1) / sw,
                b: 1 - (maxY + 1) / sh
              },
              ratio: cw / ch,
              failed: false
            }
          } else {
            // 拒绝开窗：按原图比例完整显示
            result = { box: null, ratio: w / h, failed: false }
          }
        } else {
          // 无黑边：不开窗，按原图比例显示
          result = { box: null, ratio: w / h, failed: false }
        }
      }
    }
  } catch { /* 检测失败回落原图 */ }
  // 检测完成（无论是否开窗）的结论都缓存——比例是确定的；
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
