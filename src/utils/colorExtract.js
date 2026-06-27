/**
 * 封面主色提取 —— Canvas 离屏采样
 * 仅在切歌时运行一次，不影响动画性能。
 *
 * @param {string} imageUrl - 封面图片 URL
 * @returns {Promise<{light: string, vibrant: string, dark: string, muted: string}>}
 *          light   — 亮部色（渐变光源色）
 *          vibrant — 醒目色（封面中最有辨识度的主色，提高饱和度后使用）
 *          dark    — 暗部色（渐变深处色）
 *          muted   — 柔和中间色（大范围弥散渐变底色）
 */
export async function extractCoverColors(imageUrl) {
  if (!imageUrl) return defaultPalette()

  try {
    const img = await loadImage(imageUrl)
    const pixels = samplePixels(img, 60) // 60×60 足够提取主色
    if (pixels.length < 10) return defaultPalette()
    return clusterColors(pixels)
  } catch {
    return defaultPalette()
  }
}

function loadImage(src) {
  return new Promise((resolve, reject) => {
    const img = new Image()
    img.crossOrigin = 'anonymous'
    img.onload = () => resolve(img)
    img.onerror = reject
    img.src = src
  })
}

function samplePixels(img, size) {
  const canvas = document.createElement('canvas')
  canvas.width = size
  canvas.height = size
  const ctx = canvas.getContext('2d')
  ctx.drawImage(img, 0, 0, size, size)
  const data = ctx.getImageData(0, 0, size, size).data

  const pixels = []
  for (let i = 0; i < data.length; i += 4) {
    const r = data[i], g = data[i + 1], b = data[i + 2], a = data[i + 3]
    if (a < 128) continue // 跳过透明/半透明像素
    // 跳过极暗（接近纯黑）和极亮（接近纯白）的像素，它们对主色无贡献
    const lum = 0.299 * r + 0.587 * g + 0.114 * b
    if (lum < 15 || lum > 240) continue
    pixels.push({ r, g, b, lum })
  }
  return pixels
}

function clusterColors(pixels) {
  // 按亮度排序
  const sorted = [...pixels].sort((a, b) => a.lum - b.lum)

  const n = sorted.length
  // 暗部：亮度最低的 25%
  const darkSlice = sorted.slice(0, Math.max(1, Math.floor(n * 0.25)))
  // 亮部：亮度最高的 20%
  const lightSlice = sorted.slice(Math.max(0, Math.floor(n * 0.8)))
  // 中间：取中段
  const midStart = Math.floor(n * 0.3)
  const midEnd = Math.floor(n * 0.7)
  const midSlice = sorted.slice(Math.max(midStart, 0), Math.max(midEnd, 1))

  const dark = avgColor(darkSlice)
  const light = avgColor(lightSlice)
  const mid = avgColor(midSlice)

  // vibrant: 对中间色提高饱和度
  const vibrant = boostSaturation(mid)

  // muted: 中间色降低饱和 + 略微变暗，适合大范围弥散渐变
  const muted = desaturate(mid, 0.5)

  return {
    light: toHex(light),
    vibrant: toHex(vibrant),
    dark: toHex(dark),
    muted: toHex(muted)
  }
}

function avgColor(slice) {
  if (slice.length === 0) return { r: 80, g: 80, b: 80 }
  let r = 0, g = 0, b = 0
  for (const p of slice) { r += p.r; g += p.g; b += p.b }
  const n = slice.length
  return { r: Math.round(r / n), g: Math.round(g / n), b: Math.round(b / n) }
}

/** 提高饱和度（HSL 空间，保持色相和亮度，拉升 S） */
function boostSaturation({ r, g, b }) {
  const [h, s, l] = rgbToHsl(r, g, b)
  const boosted = Math.min(1, s * 1.6 + 0.15)
  const [rr, gg, bb] = hslToRgb(h, boosted, Math.min(0.65, l * 1.1))
  return { r: rr, g: gg, b: bb }
}

/** 降低饱和度，返回柔和版 */
function desaturate({ r, g, b }, factor) {
  const [h, s, l] = rgbToHsl(r, g, b)
  const [rr, gg, bb] = hslToRgb(h, s * factor, l * 0.85)
  return { r: rr, g: gg, b: bb }
}

function rgbToHsl(r, g, b) {
  const rr = r / 255, gg = g / 255, bb = b / 255
  const max = Math.max(rr, gg, bb), min = Math.min(rr, gg, bb)
  const l = (max + min) / 2
  if (max === min) return [0, 0, l]
  const d = max - min
  const s = l > 0.5 ? d / (2 - max - min) : d / (max + min)
  let h
  switch (max) {
    case rr: h = ((gg - bb) / d + (gg < bb ? 6 : 0)) / 6; break
    case gg: h = ((bb - rr) / d + 2) / 6; break
    default: h = ((rr - gg) / d + 4) / 6
  }
  return [h, s, l]
}

function hslToRgb(h, s, l) {
  const hue2rgb = (p, q, t) => {
    if (t < 0) t += 1
    if (t > 1) t -= 1
    if (t < 1 / 6) return p + (q - p) * 6 * t
    if (t < 1 / 2) return q
    if (t < 2 / 3) return p + (q - p) * (2 / 3 - t) * 6
    return p
  }
  if (s === 0) return [Math.round(l * 255), Math.round(l * 255), Math.round(l * 255)]
  const q = l < 0.5 ? l * (1 + s) : l + s - l * s
  const p = 2 * l - q
  return [
    Math.round(hue2rgb(p, q, h + 1 / 3) * 255),
    Math.round(hue2rgb(p, q, h) * 255),
    Math.round(hue2rgb(p, q, h - 1 / 3) * 255)
  ]
}

function toHex({ r, g, b }) {
  return '#' + [r, g, b].map(c => c.toString(16).padStart(2, '0')).join('')
}

function defaultPalette() {
  return {
    light: '#a5a0d4',
    vibrant: '#6366f1',
    dark: '#1a1a2e',
    muted: '#3a3570'
  }
}
