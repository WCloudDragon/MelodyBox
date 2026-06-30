"""
Embedding 向量生成服务

使用 fastembed + intfloat/multilingual-e5-large 模型生成语义向量。
- 1024 维，100+ 语言（中日英德俄韩全覆盖）
- ONNX Runtime 推理，GPU 自动加速，无需 PyTorch

依赖: pip install fastembed
"""

import os
import time
import threading
import warnings
import numpy as np

# 全局单例，延迟加载
_MODEL = None
_MODEL_DIM = 1024
_MODEL_NAME = 'intfloat/multilingual-e5-large'
# 模型在 HF 上的实际 ONNX 仓库（fastembed 会从这里下载）
_MODEL_HF_REPO = 'qdrant/multilingual-e5-large-onnx'
# 预计模型大小（ONNX ≈ 2.24GB）
_MODEL_EXPECTED_BYTES = 2400000000
_FASTEMBED_OK = None
_MODEL_PROVIDER = None  # 当前使用的推理后端，如 'CUDAExecutionProvider'
_CACHE_DIR = None       # 用户自定义模型缓存目录
_GPU_INSTALL_PENDING = False  # GPU 组件后台安装中
_GENERATION_ACTIVE = False    # embedding 生成进行中（用于协调自动重启）

# 下载进度（模块级共享，供 API 轮询）
_download_progress = {
    'status': 'idle',
    'percent': 0,
    'downloaded_mb': 0,
    'total_mb': 0,
    'message': '',
}


def is_available():
    """检查 fastembed 是否可用"""
    global _FASTEMBED_OK
    if _FASTEMBED_OK is None:
        try:
            import fastembed  # noqa: F401
            _FASTEMBED_OK = True
        except ImportError:
            _FASTEMBED_OK = False
    return _FASTEMBED_OK


def get_active_provider():
    """返回当前使用的推理后端"""
    global _MODEL, _MODEL_PROVIDER
    if _MODEL is not None and _MODEL_PROVIDER:
        return _MODEL_PROVIDER[0]
    # 模型未加载时也检测一次
    providers = _detect_providers()
    return providers[0] if providers else 'cpu'


def get_model_dim():
    """返回 embedding 向量维度"""
    return _MODEL_DIM


def is_loaded():
    """检查模型是否已加载到内存"""
    return _MODEL is not None


def get_download_progress():
    """获取模型下载进度（供 API 轮询）"""
    return dict(_download_progress)


def set_cache_dir(path):
    """设置模型缓存目录"""
    global _CACHE_DIR
    _CACHE_DIR = (path or '').strip() or None


def get_cache_dir():
    """获取当前模型缓存目录配置"""
    return _CACHE_DIR


def _model_blobs_dir():
    """fastembed 下载的模型 blobs 目录"""
    import huggingface_hub.constants as hf_const
    root = _CACHE_DIR if _CACHE_DIR else hf_const.HF_HUB_CACHE
    # huggingface_hub 缓存路径格式: models--{org}--{repo} → 实际对应
    # 例如 qdrant/multilingual-e5-large-onnx → models--qdrant--multilingual-e5-large-onnx
    slug = _MODEL_HF_REPO.replace('/', '--')
    return os.path.join(root, f'models--{slug}', 'blobs')


def _dir_size(path):
    """递归计算目录大小（字节）"""
    total = 0
    if not os.path.isdir(path):
        return 0
    try:
        for entry in os.scandir(path):
            if entry.is_file(follow_symlinks=False):
                total += entry.stat().st_size
            elif entry.is_dir(follow_symlinks=False):
                total += _dir_size(entry.path)
    except OSError:
        pass
    return total


def _poll_download_progress(stop_event, blobs_dir):
    """后台线程：轮询缓存目录大小报告下载进度"""
    global _download_progress
    total_mb = round(_MODEL_EXPECTED_BYTES / (1024 * 1024), 0)
    _download_progress['total_mb'] = total_mb

    while not stop_event.is_set():
        current_bytes = _dir_size(blobs_dir)
        current_mb = round(current_bytes / (1024 * 1024), 1)
        pct = min(99, int(current_bytes / _MODEL_EXPECTED_BYTES * 100))
        _download_progress.update({
            'status': 'downloading',
            'percent': pct,
            'downloaded_mb': current_mb,
            'total_mb': total_mb,
            'message': f'{current_mb:.0f} / {total_mb:.0f} MB',
        })
        time.sleep(1.5)

    current_bytes = _dir_size(blobs_dir)
    current_mb = round(current_bytes / (1024 * 1024), 1)
    if current_bytes >= _MODEL_EXPECTED_BYTES * 0.9:
        _download_progress.update({
            'status': 'completed',
            'percent': 100,
            'downloaded_mb': current_mb,
            'message': '下载完成',
        })


def _get_model():
    """获取或初始化 embedding 模型（懒加载单例，自动下载 + GPU 加速）"""
    global _MODEL, _MODEL_DIM, _download_progress

    if not is_available():
        raise RuntimeError('fastembed 未安装。请在终端运行: pip install fastembed')

    if _MODEL is None:
        from fastembed import TextEmbedding

        # fastembed 0.8 改了 pooling 策略，只是一个提示，不影响功能
        warnings.filterwarnings('ignore', message='.*now uses mean pooling.*')

        # 步骤 1：准备环境（初始化进度状态，前端可见）
        _download_progress = {
            'status': 'preparing',
            'percent': 0,
            'downloaded_mb': 0,
            'total_mb': 0,
            'message': '检测 GPU 环境中...',
        }

        # 步骤 2：自动检测并启用 GPU 加速
        providers = _auto_enable_gpu()

        # 缓存目录优先级：set_cache_dir() > Config > 默认（None）
        cache_dir = _CACHE_DIR
        if not cache_dir:
            from config.config import Config
            cache_dir = Config.AI_MODEL_CACHE_DIR
        # 防御：确保不是空字符串
        if cache_dir is not None and (not isinstance(cache_dir, str) or not cache_dir.strip()):
            cache_dir = None

        # 步骤 3：启动下载进度轮询（TextEmbedding 构造函数内部下载时追踪）
        _download_progress = {
            'status': 'downloading',
            'percent': 0,
            'downloaded_mb': 0,
            'total_mb': 0,
            'message': '正在下载模型文件...',
        }
        blobs_dir = _model_blobs_dir()
        stop_event = threading.Event()
        poll_thread = threading.Thread(
            target=_poll_download_progress,
            args=(stop_event, blobs_dir),
            daemon=True
        )
        poll_thread.start()

        try:
            print(f'[embedding] 加载模型 {_MODEL_NAME}（首次运行会自动下载 ~2.2GB）...')
            if cache_dir:
                print(f'[embedding] 模型缓存目录: {cache_dir}')
            print(f'[embedding] 推理后端: {providers[0]}')
            _MODEL = TextEmbedding(
                model_name=_MODEL_NAME,
                cache_dir=cache_dir,
                providers=providers,
                lazy_load=True,
            )
            _MODEL_PROVIDER = providers
            # fastembed 0.8+ 去掉了 _model 属性，维度直接从模型注册表获取
            try:
                _MODEL_DIM = int(_MODEL.embedding_size or 0) or _MODEL_DIM
            except Exception:
                pass
            print(f'[embedding] 模型加载完成，向量维度: {_MODEL_DIM}')
        except Exception as e:
            # DML/CUDA 未真正可用时回退到 CPU
            if providers[0] in ('DmlExecutionProvider', 'CUDAExecutionProvider'):
                print(f'[embedding] GPU 初始化失败，回退 CPU: {e}')
                _MODEL = TextEmbedding(
                    model_name=_MODEL_NAME,
                    cache_dir=cache_dir,
                    providers=['CPUExecutionProvider'],
                    lazy_load=True,
                )
                _MODEL_PROVIDER = ['CPUExecutionProvider']
                try:
                    _MODEL_DIM = int(_MODEL.embedding_size or 0) or _MODEL_DIM
                except Exception:
                    pass
                print(f'[embedding] 模型加载完成 (CPU)，向量维度: {_MODEL_DIM}')
            else:
                stop_event.set()
                poll_thread.join(timeout=3)
                _download_progress.update({
                    'status': 'error',
                    'message': str(e)[:150],
                })
                raise
        finally:
            stop_event.set()
            poll_thread.join(timeout=3)

        _download_progress.update({
            'status': 'completed',
            'percent': 100,
            'message': '下载完成',
        })

    return _MODEL


def _detect_providers():
    """检测可用的 ONNX Runtime 执行提供者，优先级：CUDA > DirectML > CPU"""
    try:
        import onnxruntime as ort
        available = set(ort.get_available_providers())

        if 'CUDAExecutionProvider' in available:
            return ['CUDAExecutionProvider', 'CPUExecutionProvider']

        if 'DmlExecutionProvider' in available:
            return ['DmlExecutionProvider', 'CPUExecutionProvider']

        # 部分环境中 DML 已安装但 get_available_providers() 不返回（虚拟环境兼容性问题）
        # 此时显式请求 DML，ONNX Runtime 会在创建 session 时尝试加载，失败则回退 CPU
        if _is_directml_installed():
            print('[embedding] 已检测到 onnxruntime-directml，主动启用 DmlExecutionProvider')
            return ['DmlExecutionProvider', 'CPUExecutionProvider']
    except Exception:
        pass
    return ['CPUExecutionProvider']


def _has_nvidia_gpu():
    """检测是否有 NVIDIA 显卡"""
    try:
        import subprocess
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=name', '--format=csv,noheader'],
            capture_output=True, text=True, timeout=5
        )
        return result.returncode == 0 and result.stdout.strip()
    except Exception:
        return False


def _has_any_gpu():
    """检测系统是否有任何GPU（WMI 方式）"""
    try:
        import subprocess
        result = subprocess.run(
            ['wmic', 'path', 'Win32_VideoController', 'get', 'name'],
            capture_output=True, text=True, timeout=5
        )
        lines = [l.strip() for l in result.stdout.splitlines() if l.strip() and l.strip() != 'Name']
        return len(lines) > 0
    except Exception:
        return False


def _auto_enable_gpu():
    """
    自动检测并启用 GPU 加速。
    - 如果已有 GPU provider → 直接使用
    - 如果 DML 未安装 → 后台安装（不阻塞），当前会话用 CPU，下次启动自动切 GPU
    - 如果 DML 已安装但未检测到 → 需重启进程（DLL 锁问题）
    返回最佳可用 providers 列表。
    """
    providers = _detect_providers()

    # 已有 GPU provider，直接返回
    if providers[0] != 'CPUExecutionProvider':
        return providers

    # 只有 CPU，检查系统是否有 GPU
    if not _has_nvidia_gpu() and not _has_any_gpu():
        return providers

    # 检查 onnxruntime-directml 是否已通过 pip 安装（不 import onnxruntime，避免 DLL 锁）
    dml_installed = _is_directml_installed()

    if not dml_installed:
        # 首次安装：后台执行（不阻塞），当前会话用 CPU
        print('[embedding] 检测到 GPU，正在后台安装 GPU 加速组件（仅首次，约 30s）...')
        print('[embedding] 本次将使用 CPU 推理，下次启动自动切换至 GPU。')
        _download_progress['message'] = '正在安装 GPU 加速组件（仅首次，约 30s）...'
        _install_directml_async()
    else:
        # 已安装但 provider 未出现 → 当前进程加载了 CPU 版 DLL，需重启
        print('[embedding] onnxruntime-directml 已安装，GPU 加速将在下次启动时生效。')

    return ['CPUExecutionProvider']


def _is_directml_installed():
    """检查 onnxruntime-directml 是否已安装（不导入 onnxruntime）"""
    try:
        import importlib.metadata
        dist = importlib.metadata.distribution('onnxruntime-directml')
        return dist is not None
    except Exception:
        pass
    # fallback: 检查 pip list
    try:
        import subprocess, sys, json
        result = subprocess.run(
            [sys.executable, '-m', 'pip', 'list', '--format=json'],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            packages = json.loads(result.stdout)
            return any(p.get('name') == 'onnxruntime-directml' for p in packages)
    except Exception:
        pass
    return False


def set_generation_active(val):
    """设置 embedding 生成进行中标志（用于协调 GPU 安装后的自动重启）"""
    global _GENERATION_ACTIVE
    _GENERATION_ACTIVE = val


def get_generation_active():
    """获取 embedding 生成进行中标志"""
    return _GENERATION_ACTIVE


def is_gpu_install_pending():
    """检查 GPU 组件是否正在后台安装"""
    return _GPU_INSTALL_PENDING


def _install_directml_async():
    """后台线程安装 onnxruntime-directml，安装完成后自动重启进程以切换 GPU 模式"""
    global _GPU_INSTALL_PENDING
    _GPU_INSTALL_PENDING = True

    def _install():
        import subprocess, sys
        try:
            # 国内优先使用清华源，大幅加速下载
            _mirrors = [
                'https://pypi.tuna.tsinghua.edu.cn/simple',
                'https://mirrors.aliyun.com/pypi/simple/',
            ]
            installed = False
            for mirror in _mirrors:
                _download_progress['message'] = f'正在下载 GPU 加速组件（{mirror.split("/")[2]}）...'
                result = subprocess.run(
                    [sys.executable, '-m', 'pip', 'install', 'onnxruntime-directml',
                     '-i', mirror, '--trusted-host', mirror.split('/')[2],
                     '-q', '--no-input', '--force-reinstall'],
                    capture_output=True, text=True, timeout=180,
                    env={**os.environ, 'PIP_REQUIRE_VIRTUALENV': 'false'}
                )
                if result.returncode == 0:
                    installed = True
                    break
                print(f'[embedding] 镜像 {mirror} 失败，尝试下一个...')

            if not installed:
                # 回退到官方源
                _download_progress['message'] = '正在下载 GPU 加速组件（官方源）...'
                result = subprocess.run(
                    [sys.executable, '-m', 'pip', 'install', 'onnxruntime-directml',
                     '-q', '--no-input', '--force-reinstall'],
                    capture_output=True, text=True, timeout=180,
                    env={**os.environ, 'PIP_REQUIRE_VIRTUALENV': 'false'}
                )
            if result.returncode == 0:
                print('[embedding] GPU 加速组件安装完成，等待安全时机自动重启...')
                _download_progress['message'] = 'GPU 组件已安装，等待生成任务完成后自动重启...'

                # 等待正在进行的 embedding 生成完成（最多等 5 分钟）
                waited = 0
                while _GENERATION_ACTIVE and waited < 300:
                    time.sleep(3)
                    waited += 3
                    if waited % 15 == 0:
                        print(f'[embedding] 等待 embedding 生成完成中... （已等 {waited}s）')

                if _GENERATION_ACTIVE:
                    print('[embedding] 等待超时，延迟到下次启动自动切换 GPU。')
                    _download_progress['message'] = 'GPU 组件已安装，下次启动自动切换。'
                else:
                    print('[embedding] 正在重启进程以启用 GPU 加速...')
                    _download_progress.update({
                        'status': 'restarting',
                        'message': '正在重启应用以启用 GPU 加速...',
                    })
                    import time as _time
                    _time.sleep(2)  # 给前端一点时间收到状态
                    # 使用 os.execl 原地重启当前进程（保留命令行参数和 PID）
                    os.execl(sys.executable, sys.executable, *sys.argv)
            else:
                error_msg = (result.stderr or '').strip()[-200:]
                print(f'[embedding] GPU 组件安装失败: {error_msg}')
                _download_progress['message'] = f'GPU 组件安装失败: {error_msg[:100]}'
        except Exception as e:
            print(f'[embedding] GPU 组件安装异常: {e}')
            _download_progress['message'] = f'GPU 组件安装异常: {str(e)[:100]}'
        finally:
            _GPU_INSTALL_PENDING = False

    t = threading.Thread(target=_install, daemon=True)
    t.start()


def build_song_text(song):
    """
    构建歌曲的文本表示，用于生成 embedding。

    multilingual-e5-large 需要 query/passage 前缀：
    - 查询时: "query: {text}"
    - 文档（歌曲）时: "passage: {text}"

    格式: passage: [lang:xx] title | artist | genre | year | lyrics前512字符
    """
    lang = (song.get('lang') or '').strip()
    title = (song.get('title') or '').strip()
    artist = (song.get('artist') or '').strip()
    genre = (song.get('genre') or '').strip()
    year = str(song.get('year') or '').strip()
    lyrics = (song.get('lyrics') or '').strip()[:512]

    parts = []
    if lang:
        parts.append(f"[lang:{lang}]")
    parts.append(title)
    if artist:
        parts.append(artist)
    if genre:
        parts.append(genre)
    if year and year != '0':
        parts.append(year)
    if lyrics:
        parts.append(lyrics)

    return 'passage: ' + ' | '.join(parts)


def encode_text(text):
    """将文本编码为向量（带 query 前缀）"""
    model = _get_model()
    embeddings = list(model.embed([f'query: {text}']))
    return embeddings[0].astype(np.float32)


def encode_songs_batch(songs, batch_size=32, progress_callback=None):
    """
    批量生成歌曲的 embedding 向量。

    Args:
        songs: list of dict
        batch_size: 编码批大小
        progress_callback: (current, total) 进度回调

    Returns:
        list of numpy arrays
    """
    texts = [build_song_text(s) for s in songs]
    model = _get_model()

    all_embeddings = []
    for i in range(0, len(texts), batch_size):
        batch_texts = texts[i:i + batch_size]
        batch_embs = list(model.embed(batch_texts))
        all_embeddings.extend(emb.astype(np.float32) for emb in batch_embs)
        if progress_callback:
            progress_callback(min(i + batch_size, len(texts)), len(texts))

    return all_embeddings


def embedding_to_blob(embedding):
    """将 numpy embedding 向量转换为二进制 BLOB"""
    return embedding.astype(np.float32).tobytes()


def blob_to_embedding(blob):
    """将二进制 BLOB 还原为 numpy embedding 向量"""
    return np.frombuffer(blob, dtype=np.float32)
