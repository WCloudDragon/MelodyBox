const net = require('net')
const fs = require('fs')
const path = require('path')

const ROOT = path.resolve(__dirname, '..')
const PREFERRED_PORT = 5200

function tryListen(port) {
  return new Promise((resolve) => {
    const server = net.createServer()
    let settled = false
    const finish = (value) => {
      if (settled) return
      settled = true
      server.close(() => resolve(value))
    }
    server.once('error', () => finish(0))
    server.once('listening', () => {
      const actual = server.address().port
      finish(actual)
    })
    server.listen(port, '127.0.0.1')
  })
}

async function main() {
  // 清理上一次的就绪标记
  fs.rmSync(path.join(ROOT, '.vite-ready'), { force: true })

  // 优先尝试默认端口，失败则交给系统分配一个真正空闲的端口
  let port = await tryListen(PREFERRED_PORT)
  if (!port) port = await tryListen(0)
  if (!port) port = PREFERRED_PORT

  fs.writeFileSync(path.join(ROOT, '.vite-port'), String(port))
  console.log(`Vite dev port: ${port}`)
}

main().catch((err) => {
  console.error('[find-port] failed:', err)
  process.exit(1)
})
