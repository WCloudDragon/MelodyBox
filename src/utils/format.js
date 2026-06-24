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
        sentenceEntries.push({ time, text })
      }
    } else {
      // 逐字歌词（格式三/四）：提取每个词的时间戳+文本 segment
      const segments = []
      for (let i = 0; i < matches.length; i++) {
        const m = matches[i]
        const minutes = parseInt(m[1])
        const seconds = parseInt(m[2])
        const ms = parseInt(m[3].padEnd(3, '0'))
        const segTime = minutes * 60 + seconds + ms / 1000
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
        if (segments.length >= 2) {
          sentenceEntries.push({
            time: segments[0].time,
            text: fullText,
            segments,
            wordLevel: true
          })
        } else {
          sentenceEntries.push({
            time: segments[0].time,
            text: fullText
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
  return mergeBilingual(sentenceEntries)
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
        wordLevel: cur.wordLevel || next.wordLevel || false
      })
      i++
    } else {
      merged.push({
        time: cur.time,
        original: cur.text,
        translation: null,
        segments: cur.segments || null,
        wordLevel: cur.wordLevel || false
      })
    }
  }
  return merged
}
