"""
统一缓存层

线程安全的 TTL 缓存，供所有后端模块共用。
用法:
    from utils.cache import cache
    cache.set('key', data, ttl=300)
    data = cache.get('key')
    cache.delete('key')
"""
import time
import threading


class TTLCache:
    """线程安全的 TTL 缓存"""

    def __init__(self):
        self._store = {}
        self._lock = threading.Lock()

    def get(self, key):
        """获取缓存值，过期或不存在返回 None"""
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            expire_at, value = entry
            if expire_at <= time.time():
                del self._store[key]
                return None
            return value

    def sweep(self):
        """
        清理全部已过期条目。

        原实现只在下一次访问同一 key 时惰性删除过期项；推荐缓存等 key 带
        日期/版本维度，旧 key 永远不会再被访问，导致字典无界增长。
        该方法是全量清理，由后台守护线程定期调用。
        """
        now = time.time()
        with self._lock:
            expired = [
                key for key, (expire_at, _value) in self._store.items()
                if expire_at <= now
            ]
            for key in expired:
                del self._store[key]
            return len(expired)

    def set(self, key, value, ttl):
        """设置缓存值，ttl 单位为秒"""
        with self._lock:
            self._store[key] = (time.time() + ttl, value)

    def delete(self, key):
        """删除指定缓存"""
        with self._lock:
            self._store.pop(key, None)

    def clear(self, prefix=None):
        """清空缓存。prefix 不为 None 时只清除匹配前缀的 key"""
        with self._lock:
            if prefix is None:
                self._store.clear()
            else:
                keys = [k for k in self._store if k.startswith(prefix)]
                for k in keys:
                    del self._store[k]


# 全局单例
cache = TTLCache()


def _sweeper_loop():
    """后台守护线程：每 60 秒清理一次过期缓存，防止 key 长期累积。"""
    while True:
        time.sleep(60)
        try:
            cache.sweep()
        except Exception:
            pass


threading.Thread(target=_sweeper_loop, daemon=True).start()
