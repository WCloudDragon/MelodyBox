/**
 * Extract dominant colors from an album cover image using Canvas offscreen sampling.
 * Returns 3 colors: highlight (light/saturated), mid (average tone), shadow (dark).
 * Sampling weight favors edges and center — the parts least likely to be text/logo.
 *
 * @param {string} imageUrl - URL or data URI of the cover image
 * @param {Object} [opts] - options
 * @param {number} [opts.sampleSize=60] - downsample dimension (smaller = faster)
 * @returns {Promise<{highlight:string, mid:string, shadow:string}|null>}
 */
export async function extractCoverColors(imageUrl, opts = {}) {
  const { sampleSize = 60 } = opts

  try {
    const img = await loadImage(imageUrl)
    const canvas = document.createElement('canvas')
    canvas.width = sampleSize
    canvas.height = sampleSize
    const ctx = canvas.getContext('2d')
    ctx.drawImage(img, 0, 0, sampleSize, sampleSize)

    const { data } = ctx.getImageData(0, 0, sampleSize, sampleSize)

    // Collect all pixel colors with spatial weight (center + edges weighted higher)
    const pixels = []
    const half = sampleSize / 2
    for (let y = 0; y < sampleSize; y++) {
      for (let x = 0; x < sampleSize; x++) {
        const idx = (y * sampleSize + x) * 4
        const r = data[idx], g = data[idx + 1], b = data[idx + 2], a = data[idx + 3]
        if (a < 128) continue // skip transparent

        // Spatial weight: center row/col and edges get higher weight (avoid text/logos in center)
        const dx = (x - half) / half
        const dy = (y - half) / half
        const dist = Math.sqrt(dx * dx + dy * dy)
        // Ring-based: prefer 20%-70% radius area (annular region)
        let w = 1
        if (dist < 0.2) w = 0.3
        else if (dist < 0.7) w = 1.0
        else w = 0.6

        pixels.push({ r, g, b, w, dist })
      }
    }

    if (pixels.length === 0) return null

    // Sort by luminance (perceived brightness) for k-means seeding
    const lum = (p) => 0.299 * p.r + 0.587 * p.g + 0.114 * p.b
    const sat = (p) => {
      const max = Math.max(p.r, p.g, p.b)
      const min = Math.min(p.r, p.g, p.b)
      return max === 0 ? 0 : (max - min) / max
    }

    // Weighted k-means (k=5 then merge to 3)
    const clusters = kMeansWeighted(pixels, 5, 8)

    // Sort clusters by luminance ascending (dark → light)
    clusters.sort((a, b) => lum(a.center) - lum(b.center))

    // Merge to 3 clusters: shadow (darkest 1-2), mid (middle 1-2), highlight (lightest 1-2, most saturated)
    const highlight = pickHighlight(clusters)
    const shadow = clusters[0]
    const mid = clusters[Math.floor(clusters.length / 2)]

    return {
      highlight: rgbToHex(highlight.center.r, highlight.center.g, highlight.center.b),
      mid: rgbToHex(mid.center.r, mid.center.g, mid.center.b),
      shadow: rgbToHex(shadow.center.r, shadow.center.g, shadow.center.b),
    }
  } catch {
    return null
  }
}

function loadImage(url) {
  return new Promise((resolve, reject) => {
    const img = new Image()
    img.crossOrigin = 'anonymous'
    img.onload = () => resolve(img)
    img.onerror = reject
    img.src = url
  })
}

function kMeansWeighted(pixels, k, maxIter = 10) {
  // Init centroids by luminance-spread seeding
  const sorted = [...pixels].sort((a, b) =>
    (0.299 * a.r + 0.587 * a.g + 0.114 * a.b) - (0.299 * b.r + 0.587 * b.g + 0.114 * b.b)
  )
  const centroids = []
  for (let i = 0; i < k; i++) {
    const idx = Math.floor((i / (k - 1)) * (sorted.length - 1))
    const p = sorted[idx]
    centroids.push({ r: p.r, g: p.g, b: p.b })
  }

  for (let iter = 0; iter < maxIter; iter++) {
    // Assign pixels to nearest centroid
    const clusters = centroids.map(c => ({ center: c, sumR: 0, sumG: 0, sumB: 0, totalW: 0 }))

    for (const p of pixels) {
      let minDist = Infinity, minIdx = 0
      for (let i = 0; i < k; i++) {
        const dr = p.r - centroids[i].r, dg = p.g - centroids[i].g, db = p.b - centroids[i].b
        const d = dr * dr + dg * dg + db * db
        if (d < minDist) { minDist = d; minIdx = i }
      }
      clusters[minIdx].sumR += p.r * p.w
      clusters[minIdx].sumG += p.g * p.w
      clusters[minIdx].sumB += p.b * p.w
      clusters[minIdx].totalW += p.w
    }

    let moved = false
    for (let i = 0; i < k; i++) {
      const c = clusters[i]
      if (c.totalW === 0) continue
      const nr = c.sumR / c.totalW, ng = c.sumG / c.totalW, nb = c.sumB / c.totalW
      const dr = nr - centroids[i].r, dg = ng - centroids[i].g, db = nb - centroids[i].b
      if (Math.abs(dr) > 0.5 || Math.abs(dg) > 0.5 || Math.abs(db) > 0.5) moved = true
      centroids[i] = { r: nr, g: ng, b: nb }
    }

    if (!moved) break
  }

  return centroids.map(c => ({ center: c }))
}

function pickHighlight(clusters) {
  // Pick the most saturated cluster from the top half (lightest)
  const half = Math.ceil(clusters.length / 2)
  let best = clusters[clusters.length - 1]
  let bestSat = 0
  for (let i = half; i < clusters.length; i++) {
    const s = saturation(clusters[i].center)
    if (s > bestSat) { bestSat = s; best = clusters[i] }
  }
  return best
}

function saturation({ r, g, b }) {
  const max = Math.max(r, g, b)
  const min = Math.min(r, g, b)
  return max === 0 ? 0 : (max - min) / max
}

function rgbToHex(r, g, b) {
  const toHex = (v) => {
    const clamped = Math.max(0, Math.min(255, Math.round(v)))
    return clamped.toString(16).padStart(2, '0')
  }
  return `#${toHex(r)}${toHex(g)}${toHex(b)}`
}
