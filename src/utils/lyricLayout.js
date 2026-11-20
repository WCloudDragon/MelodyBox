/**
 * 歌词滚动定位几何计算
 *
 * 纯函数模块：不查询、不写入 DOM，所有元素由调用方传入，
 * 仅读取 offsetTop / offsetHeight / clientHeight 这类布局属性。
 * 公式与 NowPlayingPanel 中的现有实现逐字一致，仅做收敛，不做额外钳制或优化。
 */

/**
 * 单行居中：让该行的垂直中心与容器中心对齐。
 * 对应 scrollToLine。
 *
 * @param {HTMLElement} lineEl - 目标歌词行元素
 * @param {number} containerHeight - 歌词容器可视高度（clientHeight）
 * @returns {number} 目标滚动量（内容坐标）
 */
export function lineCenteredScroll(lineEl, containerHeight) {
    return lineEl.offsetTop - containerHeight / 2 + lineEl.offsetHeight / 2
}

/**
 * 多行活跃组居中：以组整体中心对齐容器中心；
 * 组高度超过容器 60% 的异常大组退化为以第一行居中，保证可读。
 * 对应 scrollToActiveGroup 的多行分支（单行由调用方使用 lineCenteredScroll）。
 *
 * @param {HTMLElement} firstEl - 组内首行元素
 * @param {HTMLElement} lastEl - 组内末行元素
 * @param {number} containerHeight - 歌词容器可视高度（clientHeight）
 * @returns {number} 目标滚动量（内容坐标）
 */
export function activeGroupScroll(firstEl, lastEl, containerHeight) {
    const top = firstEl.offsetTop
    const bottom = lastEl.offsetTop + lastEl.offsetHeight
    if (bottom - top > containerHeight * 0.6) {
        return top - containerHeight / 2 + firstEl.offsetHeight / 2
    }
    return (top + bottom) / 2 - containerHeight / 2
}

/**
 * 三点提示居中：滚动到「三点收起后下一句恰好居中」的位置，
 * 句中空区再用上一行剩余收缩量预补偿。
 * 对应 scrollToDots。
 *
 * @param {HTMLElement} anchorEl - 下一句元素（锚点行）
 * @param {HTMLElement|null} dotsEl - 三点提示行元素，缺失时高度按 0 计
 * @param {HTMLElement|null} prevEl - 句中空区的上一行元素，首行前为 null
 * @param {number} containerHeight - 歌词容器可视高度（clientHeight）
 * @returns {number} 目标滚动量（内容坐标）
 */
export function dotsCenteredScroll(anchorEl, dotsEl, prevEl, containerHeight) {
    const dotsH = dotsEl ? dotsEl.offsetHeight : 0
    let y = Math.max(0, anchorEl.offsetTop - dotsH - containerHeight / 2 + anchorEl.offsetHeight / 2)
    if (prevEl) {
        const drift = Math.max(0, prevEl.offsetHeight - anchorEl.offsetHeight)
        if (drift > 0) y = Math.max(0, y - drift)
    }
    return y
}

/**
 * 三点自然结束后的级联位移：容器瞬跳到目标位，
 * 下方行吸收三点行移除的布局位移与滚动差，上方行仅吸收滚动差。
 * 对应 runDotsCascade 中的位移计算。
 *
 * @param {HTMLElement} nextEl - 即将激活的下一行元素
 * @param {number} containerHeight - 歌词容器可视高度（clientHeight）
 * @param {number} targetScrollPos - 上一次的目标滚动量
 * @param {number} dotsH - 三点行移除前测量的高度
 * @returns {{targetScroll: number, belowShift: number, aboveShift: number}} 目标滚动量与上下方行的反向偏移
 */
export function dotsCascadeShifts(nextEl, containerHeight, targetScrollPos, dotsH) {
    const targetScroll = Math.max(0, nextEl.offsetTop - containerHeight / 2 + nextEl.offsetHeight / 2)
    const scrollDelta = targetScroll - targetScrollPos
    const belowShift = dotsH - scrollDelta
    const aboveShift = -scrollDelta
    return { targetScroll, belowShift, aboveShift }
}

/**
 * 用户手动滚动的边界钳制：上下各留 20px 余量。
 * 对应 onLyricsWheel 与 applyUserScrollRecenter 中的钳制。
 *
 * @param {number} transformY - 待钳制的 transform Y 值（向下为负）
 * @param {number} contentHeight - 歌词内容总高度（scrollHeight）
 * @param {number} containerHeight - 歌词容器可视高度（clientHeight）
 * @returns {number} 钳制后的 transform Y 值
 */
export function clampManualScroll(transformY, contentHeight, containerHeight) {
    const minY = -(contentHeight - containerHeight) - 20
    const maxY = 20
    return Math.max(minY, Math.min(maxY, transformY))
}

/**
 * 按用户滚动锚点推算应居中的滚动量：锚点行顶部 + 行内比例 × 行高 - 半容器高。
 * 对应 computeUserScrollTarget。
 *
 * @param {HTMLElement} lineEl - 锚点命中的歌词行元素
 * @param {number} ratio - 视口中心在该行内的比例（0~1）
 * @param {number} containerHeight - 歌词容器可视高度（clientHeight）
 * @returns {number} 目标滚动量（内容坐标）
 */
export function anchorScrollForLine(lineEl, ratio, containerHeight) {
    return lineEl.offsetTop + ratio * lineEl.offsetHeight - containerHeight / 2
}
