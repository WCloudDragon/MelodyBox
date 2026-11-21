/**
 * 计算某一歌词行的透明度与模糊。
 *
 * 纯函数：不读写 DOM，不依赖组件状态，输入输出都是普通值，便于单独验证。
 *
 * @param {number} index 行索引
 * @param {object} ctx
 * @param {boolean} ctx.isScrubbing 进度条拖拽预览中（全部行清晰）
 * @param {boolean} ctx.isUserScrolling 用户滚轮浏览中（取消模糊与淡出）
 * @param {number[]} ctx.activeIndexes 当前活跃行索引集合
 * @param {number} ctx.hintLineIndex 空区锚点行（无活跃行时的距离基准）
 * @param {boolean} ctx.blurEnabled 是否启用歌词模糊
 * @returns {{ opacity: number, filter: string }}
 */
export function computeLineStyle(index, {
  isScrubbing,
  isUserScrolling,
  activeIndexes,
  hintLineIndex,
  blurEnabled
}) {
  // 进度条拖拽预览：所有行统一清晰显示（不模糊、不按距离淡出），便于快速定位
  if (isScrubbing) return { opacity: 1, filter: 'none' }
  // 跳转时模糊/透明度立即跟随新的活跃位置，不等待滚动落地；
  // jumpPending 只负责延迟 .active 的放大高亮，避免视觉脱节
  let refs = activeIndexes

  // 无活跃行（空区）：以空区锚点（上一行索引，首行前为 -1）为距离基准，
  // 恢复与其他时刻一致的模糊与透明度渐变
  if (refs.length === 0) {
    refs = [hintLineIndex]
  }

  // 正在播放的行（公平模型：所有活跃行一律高亮，不区分主/副）
  if (refs.includes(index)) {
    return { opacity: 1, filter: 'none' }
  }

  // 非活跃行：按与最近活跃行的距离渐变
  let minDist = Infinity
  for (const r of refs) {
    const d = Math.abs(index - r)
    if (d < minDist) minDist = d
  }
  if (minDist === Infinity) minDist = 1
  const absDist = minDist
  const t = Math.min(absDist / 6, 1)
  const opacity = isUserScrolling ? 1 : Math.max(0.12, 1 - t * 0.88)

  // Apple Music 风格模糊：越远离活跃行越模糊，用户滚动时取消模糊
  const blurAmount = (isUserScrolling || !blurEnabled) ? 0 : Math.min(absDist * 1, 4)
  const filter = blurAmount > 0.5 ? `blur(${blurAmount}px)` : 'none'

  return { opacity, filter }
}
