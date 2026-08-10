/**
 * 格式化工具函数
 */

// 格式化时长为 mm:ss
export function formatDuration(seconds) {
  if (!seconds || seconds <= 0) return '00:00'
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

// 格式化总时长
export function formatTotalDuration(seconds) {
  if (!seconds || seconds <= 0) return '0分钟'
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  if (h > 0) return `${h}小时${m}分钟`
  return `${m}分钟`
}

// 格式化比特率
export function formatBitrate(bps) {
  if (!bps) return ''
  const kbps = Math.round(bps / 1000)
  return `${kbps} kbps`
}

// 格式化采样率
export function formatSampleRate(hz) {
  if (!hz) return ''
  const khz = (hz / 1000).toFixed(1)
  return `${khz} kHz`
}

// 格式化文件大小
export function formatFileSize(bytes) {
  if (!bytes) return ''
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

// 音质标签 CSS 类名
export function qualityClass(quality) {
  const map = {
    'HQ': 'quality-tag--hq',
    'CD': 'quality-tag--cd',
    'CD+': 'quality-tag--cd-plus',
    'Hi-Res': 'quality-tag--hires',
  }
  return map[quality] || ''
}

// 解析歌词（兼容四种常见 LRC 格式）
export function parseLRC(lrcText) {
  if (!lrcText) return []

  // 归一化：处理字面量 \r\n 和 \n（反斜杠+n → 真正的换行）
  const normalized = lrcText.trim().replace(/\\r\\n/g, '\n').replace(/\\n/g, '\n').replace(/\\r/g, '\n').replace(/\\'/g, "'").replace(/\\"/g, '"')
  const sourceLines = normalized.split(/\r?\n/)
  const sentenceEntries = []
  const timeRegex = /\[(\d{2}):(\d{2})[.:](\d{2,3})\]/g

  for (const rawLine of sourceLines) {
    const line = rawLine.trim()
    if (!line) continue

    // 使用 matchAll 一次性收集该行所有时间戳匹配
    timeRegex.lastIndex = 0  // 重置全局正则状态，避免跨行污染
    const matches = [...line.matchAll(timeRegex)]
    if (matches.length === 0) continue

    if (matches.length === 1) {
      // 逐句歌词（格式一/二）：单个 [timestamp] + 之后全文
      const m = matches[0]
      const minutes = parseInt(m[1])
      const seconds = parseInt(m[2])
      const ms = parseInt(m[3].padEnd(3, '0'))
      const time = minutes * 60 + seconds + ms / 1000
      const text = line.slice(m.index + m[0].length).trim()
      if (text) {
        // 无结束时间戳：视为一直持续到下一句开始
        sentenceEntries.push({ time, text, end: null })
      }
    } else {
      // 逐字歌词（格式三/四）：提取每个词的时间戳+文本 segment
      const times = matches.map(m => {
        const minutes = parseInt(m[1])
        const seconds = parseInt(m[2])
        const ms = parseInt(m[3].padEnd(3, '0'))
        return minutes * 60 + seconds + ms / 1000
      })
      const segments = []
      for (let i = 0; i < matches.length; i++) {
        const m = matches[i]
        const segTime = times[i]
        // 文本范围：当前时间戳之后 → 下一个时间戳之前（或行尾）
        const textStart = m.index + m[0].length
        const textEnd = i + 1 < matches.length ? matches[i + 1].index : line.length
        const rawText = line.slice(textStart, textEnd)
        if (rawText.trim()) {
          segments.push({ time: segTime, text: rawText })
        }
      }
      if (segments.length > 0) {
        const fullText = segments.map(s => s.text).join('')
        // 行末时间戳即本行的结束时间（逐字行/整句行的尾部 [mm:ss.xxx]）
        const endTime = times[times.length - 1]
        if (segments.length >= 2) {
          sentenceEntries.push({
            time: segments[0].time,
            text: fullText,
            segments,
            wordLevel: true,
            end: endTime
          })
        } else {
          sentenceEntries.push({
            time: segments[0].time,
            text: fullText,
            end: endTime
          })
        }
      }
    }
  }

  if (sentenceEntries.length === 0) {
    // 纯文本：按行拆分，每行估算 4 秒间隔
    const plainLines = sourceLines.filter(l => l.trim())
    if (plainLines.length === 0) return []
    return plainLines.map((text, i) => ({
      time: i * 4,
      original: text.trim(),
      translation: null
    }))
  }

  // 按时间排序后合并双语对
  sentenceEntries.sort((a, b) => a.time - b.time)
  const merged = mergeBilingual(sentenceEntries)
  // 预计算每行原词结束后到下一行的间隔（供长间隙“即将开唱”提示使用，稳定不随时间变化）
  for (let i = 0; i < merged.length; i++) {
    const L = merged[i]
    if (L.end == null) {
      L.gap = 0
      continue
    }
    const baseEnd = L.end
    let nextAfter = Infinity
    for (let j = 0; j < merged.length; j++) {
      if (j === i) continue
      if (merged[j].time > baseEnd && merged[j].time < nextAfter) nextAfter = merged[j].time
    }
    L.gap = nextAfter !== Infinity ? nextAfter - baseEnd : 0
  }
  return merged
}

// 获取当前歌词行索引
export function getCurrentLyricIndex(lyrics, currentTime) {
  if (!lyrics || lyrics.length === 0) return -1
  // 如果当前时间还没到第一行，不激活任何行
  if (currentTime < lyrics[0].time) return -1
  for (let i = lyrics.length - 1; i >= 0; i--) {
    if (lyrics[i].time <= currentTime) return i
  }
  return 0
}

// 计算当前时刻全部正在播放的歌词行（公平模型：不区分主/副行，每行一律平等）。
// 每行的有效结束时间：
// - 若其基础窗口 [start, 较早结束) 与其他行的基础窗口重叠 → 较早结束（多句并存时唱完即走）；
// - 否则 → 下一行开始（单句播放时持续显示，填补句间空隙，避免熄灭/跳动）。
// 无结束时间戳的行，基础窗口视为持续到下一行开始。
export function computeActiveSet(lyrics, currentTime) {
  if (!lyrics || lyrics.length === 0) return { activeIndexes: [] }
  const activeIndexes = []
  for (let i = 0; i < lyrics.length; i++) {
    const L = lyrics[i]
    if (L.time > currentTime) break
    if (currentTime >= effectiveEnd(lyrics, i)) continue
    activeIndexes.push(i)
  }
  return { activeIndexes }
}

// 句间间隙填缝上限（秒）：原词结束后到下一行开始的间隔达到该值时不再用翻译尾巴填缝，
// 产生真实空区，供“即将开唱”提示显示（低于该值保持填缝，与现状一致）。
export const LYRIC_GAP_FILL_LIMIT = 10

function effectiveEnd(lyrics, i) {
  const L = lyrics[i]
  // 无结束时间戳（标准逐句歌词）：持续到下一行开始
  if (L.end == null) {
    return i + 1 < lyrics.length ? lyrics[i + 1].time : Infinity
  }
  const baseEnd = L.end
  let nextAfter = Infinity
  for (let j = 0; j < lyrics.length; j++) {
    if (j === i) continue
    const M = lyrics[j]
    const otherStart = M.time
    const otherBaseEnd = M.end != null ? M.end : (j + 1 < lyrics.length ? lyrics[j + 1].time : Infinity)
    // 手递手：另一行在原词结束时刻（含同时刻无缝衔接）仍在播放 → 本行到此为止（原词结束即走）
    if (otherStart <= baseEnd && baseEnd < otherBaseEnd) {
      return baseEnd
    }
    // 收集原词结束时刻或之后才开始的第一行，作为无手递手时翻译尾巴的终点
    if (otherStart >= baseEnd && otherStart < nextAfter) {
      nextAfter = otherStart
    }
  }
  // 长间隙（≥ 上限）不再填缝：原词结束即止，产生空区
  if (nextAfter !== Infinity && nextAfter - baseEnd >= LYRIC_GAP_FILL_LIMIT) {
    return baseEnd
  }
  // 短间隙：翻译尾巴延伸到下一行开始，填补句间空隙（与现状一致）
  return nextAfter
}

// 合并相同时戳的条目为双语歌词对
function mergeBilingual(entries) {
  const merged = []
  for (let i = 0; i < entries.length; i++) {
    const cur = entries[i]
    if (i + 1 < entries.length && Math.abs(cur.time - entries[i + 1].time) < 0.01) {
      const next = entries[i + 1]
      merged.push({
        time: cur.time,
        original: cur.text,
        translation: next.text,
        segments: cur.segments || null,
        wordLevel: cur.wordLevel || next.wordLevel || false,
        end: mergeEnd(cur.end, next.end)
      })
      i++
    } else {
      merged.push({
        time: cur.time,
        original: cur.text,
        translation: null,
        segments: cur.segments || null,
        wordLevel: cur.wordLevel || false,
        end: cur.end ?? null
      })
    }
  }
  return merged
}

function mergeEnd(a, b) {
  const has = [a, b].filter(v => v != null)
  // 原词与翻译都有结束时间戳时，以较早者为整句的结束基准
  return has.length ? Math.min(...has) : null
}
