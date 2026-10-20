/**
 * 拼音模糊搜索索引
 *
 * 为含中文的文本生成「全拼 + 首字母」两种索引，使用户输入 jiamian 或 jm
 * 都能命中「假面」。索引按原文缓存于 Map，命中后不再重复转换。
 *
 * 匹配优先级（分值越高越靠前）：
 *   3  原文直接包含（中文原样、英文原样）
 *   2  全拼包含（jiamian）
 *   1  首字母包含（jm）
 *   0  不匹配
 */
import { pinyin } from 'pinyin-pro'

const CACHE = new Map()
const CJK = /[\u4e00-\u9fff]/

/** 把 octet 数组拼成小写串；ü 归一为 v，贴合用户输入习惯（nv → 女） */
function normalize(arr) {
  return arr.join('').toLowerCase().replace(/ü/g, 'v')
}

function build(text) {
  if (!CJK.test(text)) return null // 纯英文/数字无需拼音索引
  return {
    full: normalize(pinyin(text, { toneType: 'none', type: 'array' })),
    initials: normalize(pinyin(text, { pattern: 'first', toneType: 'none', type: 'array' })),
  }
}

/** 取（并缓存）某段文本的拼音索引；不含中文时返回 null */
export function indexOf(text) {
  const key = text || ''
  if (CACHE.has(key)) return CACHE.get(key)
  let value = null
  try {
    value = build(key)
  } catch {
    value = null
  }
  CACHE.set(key, value)
  return value
}

/** 单字段匹配分值 */
export function scoreOf(text, query) {
  if (!text || !query) return 0
  if (text.toLowerCase().includes(query)) return 3
  const idx = indexOf(text)
  if (!idx) return 0
  if (idx.full.includes(query)) return 2
  if (idx.initials.includes(query)) return 1
  return 0
}

/** 多字段取最高分（任一字段直接命中即提前结束） */
export function bestScore(fields, query) {
  let best = 0
  for (const field of fields) {
    const s = scoreOf(field, query)
    if (s > best) best = s
    if (best === 3) break
  }
  return best
}

/**
 * 过滤 + 按分值排序 + 截断。
 * 同分保持原有次序（用下标显式回退，不依赖 Array.sort 的稳定性）。
 * @param {Array} list 待筛选数据
 * @param {(item) => Array<string>} fieldsOf 从元素取出可搜索字段
 * @param {string} query 已小写化的关键词
 * @param {number} limit 截断条数，不传则不限
 */
export function rankPick(list, fieldsOf, query, limit = Infinity) {
  const scored = []
  for (let i = 0; i < list.length; i++) {
    const score = bestScore(fieldsOf(list[i]), query)
    if (score > 0) scored.push({ item: list[i], score, i })
  }
  scored.sort((a, b) => b.score - a.score || a.i - b.i)
  const picked = limit === Infinity ? scored : scored.slice(0, limit)
  return picked.map(e => e.item)
}

/** 预建索引：曲库就绪后调用，避免首次输入时才转换导致的卡顿 */
export function prewarm(strings) {
  for (const s of strings) indexOf(s)
}
