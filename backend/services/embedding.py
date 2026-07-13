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
_CPU_MODEL = None  # CPU 专用模型（并行编码时使用，避免与 GPU 模型冲突）
_MODEL_DIM = 1024
_MODEL_NAME = 'intfloat/multilingual-e5-large'
# 模型在 HF 上的实际 ONNX 仓库（fastembed 会从这里下载）
_MODEL_HF_REPO = 'qdrant/multilingual-e5-large-onnx'
# 预计模型大小（ONNX ≈ 2.24GB）
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
_e5_downloaded = threading.Event()  # E5 模型就绪时 set()


def _resolve_cache_dir():
    """解析 E5 模型缓存目录（统一到 Config.resolve_model_dir + e5 子目录）"""
    from config.config import Config
    root = Config.resolve_model_dir()
    return os.path.join(root, 'e5')


def wait_for_e5_download(timeout=600):
    """等待 E5 模型下载完成（供 worker 线程调用）"""
    _e5_downloaded.wait(timeout=timeout)


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


def _retry_snapshot_download(repo_id, cache_dir=None, local_dir=None, tqdm_class=None, progress_dict=None, max_retries=3, label='模型'):
    """
    带重试的 snapshot_download，网络中断时自动恢复。
    huggingface_hub 内置断点续传，重试时从断点继续。
    """
    from huggingface_hub import snapshot_download
    kwargs = {'repo_id': repo_id, 'tqdm_class': tqdm_class}
    if cache_dir:
        kwargs['cache_dir'] = cache_dir
    if local_dir:
        kwargs['local_dir'] = local_dir

    for attempt in range(1, max_retries + 1):
        try:
            result = snapshot_download(**kwargs)
            return result
        except Exception as e:
            if attempt < max_retries:
                wait = 3 * attempt
                if progress_dict:
                    progress_dict.update({
                        'status': 'retrying',
                        'message': f'网络中断，{wait}秒后重试 ({attempt}/{max_retries})...',
                    })
                time.sleep(wait)
            else:
                raise


def get_cache_dir():
    """获取当前模型缓存目录配置"""
    return _CACHE_DIR


def _clear_e5_cache():
    """删除 E5 模型所有缓存目录，强制重新下载（含旧 Temp 路径迁移清理）"""
    import shutil
    import tempfile
    slug = _MODEL_HF_REPO.replace('/', '--')
    dirs_to_clear = []

    # 1. 统一模型路径
    dirs_to_clear.append(os.path.join(_resolve_cache_dir(), f'models--{slug}'))
    # 2. 旧路径：%TEMP%/fastembed_cache（迁移前残留）
    dirs_to_clear.append(os.path.join(
        tempfile.gettempdir(), 'fastembed_cache', f'models--{slug}'))
    # 3. HuggingFace hub 缓存（fastembed 从这里下载原始权重）
    from huggingface_hub.constants import HF_HUB_CACHE
    dirs_to_clear.append(os.path.join(HF_HUB_CACHE, f'models--{slug}'))

    cleared = False
    for d in dirs_to_clear:
        if os.path.isdir(d):
            shutil.rmtree(d, ignore_errors=True)
            cleared = True
    return cleared


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


def _poll_e5_download(stop_event, model_root, progress_dict):
    """后台轮询 E5 模型缓存目录大小，报告下载进度"""
    while not stop_event.is_set():
        current_bytes = 0
        if os.path.isdir(model_root):
            current_bytes = _dir_size(model_root)
        current_mb = round(current_bytes / (1024 * 1024), 1)
        if current_mb > 0:
            pct = min(99, max(1, int(current_bytes / (2.35 * 1024 * 1024 * 1024) * 100)))
            # 计算近似速度（每 1.5s 采样）
            mb_str = f'{current_mb:.0f} MB' if current_mb < 1024 else f'{current_mb / 1024:.2f} GB'
            progress_dict.update({
                'status': 'downloading',
                'percent': pct,
                'downloaded_mb': current_mb,
                'total_mb': 2240,
                'message': f'正在下载文本分析模型 ({mb_str})',
            })
        time.sleep(1.5)


def _get_model():
    """获取或初始化 embedding 模型（懒加载单例，自动下载 + GPU 加速）"""
    global _MODEL, _MODEL_DIM, _download_progress

    if not is_available():
        raise RuntimeError('fastembed 未安装。请在终端运行: pip install fastembed')

    if _MODEL is None:
        from fastembed import TextEmbedding

        warnings.filterwarnings('ignore', message='.*now uses mean pooling.*')

        # 步骤 1：准备环境
        _download_progress = {
            'status': 'preparing',
            'percent': 0,
            'downloaded_mb': 0,
            'total_mb': 0,
            'message': '检测 GPU 环境中...',
        }

        # 步骤 2：GPU 加速
        providers = _auto_enable_gpu()

        # 缓存目录
        cache_dir = _CACHE_DIR or _resolve_cache_dir()

        # 步骤 3：检测模型是否存在
        slug = _MODEL_HF_REPO.replace('/', '--')
        model_root = os.path.join(cache_dir, f'models--{slug}')
        model_exists = os.path.isdir(model_root) and any(
            f.endswith('.onnx')
            for root, _, files in os.walk(model_root)
            for f in files
        )

        _download_progress.update({
            'status': 'checking',
            'percent': 0,
            'message': '正在检查环境，准备下载文本分析模型...',
        })

        if not model_exists:
            _download_progress.update({
                'status': 'preparing',
                'percent': 1,
                'message': '模型不存在，准备下载 ~2.2GB...',
            })
            # 预下载：用 snapshot_download(cache_dir=...) 统一写入
            # TextEmbedding 内部也用相同 cache_dir，二次查询秒返回
            from huggingface_hub import snapshot_download
            from tqdm import tqdm as _tqdm_base

            class _E5ProgressTqdm(_tqdm_base):
                def __init__(self, *args, **kwargs):
                    super().__init__(*args, **kwargs)
                    self._last_n = 0
                    self._last_t = time.monotonic()

                def update(self, n=1):
                    super().update(n)
                    if self.total and self.total > 0:
                        dl = round(self.n / (1024 * 1024), 1)
                        total = round(self.total / (1024 * 1024), 0)
                        pct = int(self.n / self.total * 100)
                        now = time.monotonic()
                        speed = ''
                        if now > self._last_t and self.n > self._last_n:
                            rate = (self.n - self._last_n) / (now - self._last_t)
                            if rate > 1024 * 1024:
                                speed = f'  {rate / (1024 * 1024):.1f} MB/s'
                            elif rate > 1024:
                                speed = f'  {rate / 1024:.0f} KB/s'
                        self._last_n = self.n
                        self._last_t = now
                        _download_progress.update({
                            'status': 'downloading',
                            'percent': pct,
                            'downloaded_mb': dl,
                            'total_mb': total,
                            'message': f'正在下载文本分析模型{speed}',
                        })

            try:
                _retry_snapshot_download(
                    _MODEL_HF_REPO,
                    cache_dir=cache_dir,
                    tqdm_class=_E5ProgressTqdm,
                    progress_dict=_download_progress,
                    label='文本分析',
                )
            except Exception as pre_e:
                _download_progress.update({
                    'status': 'error',
                    'message': f'下载失败: {str(pre_e)[:100]}',
                })
                _MODEL = None
                _e5_downloaded.set()
                return None
        else:
            pass

        _download_progress.update({
            'status': 'preparing',
            'percent': 98,
            'message': '正在加载文本分析引擎...',
        })

        try:
            _MODEL = TextEmbedding(
                model_name=_MODEL_NAME,
                cache_dir=cache_dir,
                providers=providers,
                lazy_load=False,
            )
            _MODEL_PROVIDER = providers
            try:
                _MODEL_DIM = int(_MODEL.embedding_size or 0) or _MODEL_DIM
            except Exception:
                pass
        except Exception as e:
            err = str(e)
            if 'onnx_data' in err or 'No such file' in err or 'RUNTIME_EXCEPTION' in err or 'bad allocation' in err:
                _clear_e5_cache()
                try:
                    _MODEL = TextEmbedding(
                        model_name=_MODEL_NAME,
                        cache_dir=cache_dir,
                        providers=['CPUExecutionProvider'],  # bad allocation 往往是 GPU 内存不足
                        lazy_load=False,
                    )
                    _MODEL_PROVIDER = ['CPUExecutionProvider']
                    try:
                        _MODEL_DIM = int(_MODEL.embedding_size or 0) or _MODEL_DIM
                    except Exception:
                        pass
                except Exception as retry_e:
                    _download_progress.update({
                        'status': 'error',
                        'message': str(retry_e)[:150],
                    })
                    _MODEL = None
                    _e5_downloaded.set()
                    return None
            else:
                _download_progress.update({
                    'status': 'error',
                    'message': err[:150],
                })
                raise

        _download_progress.update({
            'status': 'completed',
            'percent': 100,
            'message': '模型已就绪',
        })
        _e5_downloaded.set()

    return _MODEL


def _get_cpu_model():
    """获取 CPU 专用 embedding 模型（与 GPU 模型并行使用，不冲突）"""
    global _CPU_MODEL
    if _CPU_MODEL is None:
        from fastembed import TextEmbedding
        warnings.filterwarnings('ignore', message='.*now uses mean pooling.*')
        cache_dir = _CACHE_DIR or _resolve_cache_dir()

        def _try_load():
            return TextEmbedding(
                model_name=_MODEL_NAME,
                cache_dir=cache_dir,
                providers=['CPUExecutionProvider'],
                lazy_load=False,  # 立即加载，及早发现文件损坏
            )

        try:
            _CPU_MODEL = _try_load()
        except Exception as e:
            err = str(e)
            if 'onnx_data' in err or 'No such file' in err or 'RUNTIME_EXCEPTION' in err or 'bad allocation' in err:
                _clear_e5_cache()
                try:
                    _CPU_MODEL = _try_load()
                except Exception as retry_e:
                    _CPU_MODEL = None
            else:
                raise

    return _CPU_MODEL


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
        _download_progress['message'] = '正在安装 GPU 加速组件（仅首次，约 30s）...'
        _install_directml_async()
    else:
        pass

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
                _download_progress['message'] = 'GPU 组件已安装，等待生成任务完成后自动重启...'

                # 等待正在进行的 embedding 生成完成（最多等 5 分钟）
                waited = 0
                while _GENERATION_ACTIVE and waited < 300:
                    time.sleep(3)
                    waited += 3

                if _GENERATION_ACTIVE:
                    _download_progress['message'] = 'GPU 组件已安装，下次启动自动切换。'
                else:
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
                _download_progress['message'] = f'GPU 组件安装失败: {error_msg[:100]}'
        except Exception as e:
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


def encode_songs_batch(songs, batch_size=32, progress_callback=None, use_cpu=False):
    """
    批量生成歌曲的 embedding 向量。

    Args:
        songs: list of dict
        batch_size: 编码批大小
        progress_callback: (current, total) 进度回调
        use_cpu: 强制使用 CPU 推理（与 GPU 模型并行时使用）

    Returns:
        list of numpy arrays
    """
    texts = [build_song_text(s) for s in songs]
    if use_cpu:
        model = _get_cpu_model()
        if model is None:
            # CPU 模型加载失败，回退到主模型
            model = _get_model()
    else:
        model = _get_model()
    if model is None:
        raise RuntimeError('无法加载 embedding 模型')

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


# ==================== 音频 Embedding (MERT-v1-95M) ====================
#
# 使用 m-a-p/MERT-v1-95M 模型提取音频特征（768维）。
# 首次运行自动从 HuggingFace 下载模型 → 导出 ONNX → 缓存。
# 后续运行直接加载 ONNX，使用现有 GPU 加速（CUDA/DirectML）。

_AUDIO_OK = None           # 音频依赖是否可用
_AUDIO_MODEL = None         # ONNX Runtime InferenceSession
_AUDIO_MODEL_DIM = 768
_AUDIO_MODEL_NAME = 'm-a-p/MERT-v1-95M'
_AUDIO_SAMPLE_RATE = 24000  # MERT 输入采样率
_AUDIO_CLIP_SECONDS = 5     # 只取 5 秒（30秒处，更代表歌曲主体）
_AUDIO_OFFSET_SECONDS = 30  # 从第 30 秒开始取（跳过 intro）
_AUDIO_ONNX_FILENAME = 'mert-v1-95m-audio.onnx'


def is_audio_available():
    """检查音频 embedding 依赖是否可用（librosa + soundfile + onnxruntime）"""
    global _AUDIO_OK
    if _AUDIO_OK is None:
        try:
            import onnxruntime  # noqa: F401
            import librosa      # noqa: F401
            import soundfile    # noqa: F401
            _AUDIO_OK = True
        except ImportError:
            _AUDIO_OK = False
    return _AUDIO_OK


def get_audio_model_dim():
    """返回音频 embedding 向量维度"""
    return _AUDIO_MODEL_DIM


def _get_audio_onnx_path():
    """MERT ONNX 模型路径（统一到 %APPDATA%/melodybox/models/mert/）"""
    from config.config import Config
    root = Config.resolve_model_dir()
    mert_dir = os.path.join(root, 'mert')
    os.makedirs(mert_dir, exist_ok=True)
    return os.path.join(mert_dir, 'mert-v1-95m-audio.onnx')


def _get_audio_duration(file_path):
    """获取音频文件时长（秒），优先 soundfile，回退 librosa"""
    try:
        import soundfile as sf
        info = sf.info(file_path)
        return info.duration
    except Exception:
        import librosa
        return librosa.get_duration(path=file_path)


def _load_audio_clip(file_path):
    """
    加载音频文件的指定片段，转为 24kHz 单声道 float32。
    优先从第 30 秒处取 5 秒（代表歌曲主体），不足 35 秒的歌曲回退到开头。
    返回 numpy array，失败返回 None。
    """
    try:
        import librosa
        # 先获取音频总时长
        duration = _get_audio_duration(file_path)
        # 决定 offset：优先 30 秒处，短歌曲回退到开头
        if duration >= _AUDIO_OFFSET_SECONDS + _AUDIO_CLIP_SECONDS:
            offset = _AUDIO_OFFSET_SECONDS
        else:
            offset = 0

        waveform, sr = librosa.load(
            file_path,
            sr=None,               # 保持原始采样率
            mono=True,             # 单声道
            duration=_AUDIO_CLIP_SECONDS,
            offset=offset,
            res_type='kaiser_fast'  # 快速重采样（比 kaiser_best 快 2-3 倍）
        )
        if sr != _AUDIO_SAMPLE_RATE:
            waveform = librosa.resample(
                waveform, orig_sr=sr, target_sr=_AUDIO_SAMPLE_RATE
            )
        # 确保足够长度（不足则零填充，过长则截断）
        target_samples = _AUDIO_SAMPLE_RATE * _AUDIO_CLIP_SECONDS
        if len(waveform) < target_samples:
            waveform = np.pad(waveform, (0, target_samples - len(waveform)))
        else:
            waveform = waveform[:target_samples]
        return waveform.astype(np.float32)
    except Exception as e:
        return None


_pytorch_cache_cleaned = False  # 仅清理一次
_mert_download_progress = {
    'status': 'idle',
    'percent': 0,
    'downloaded_mb': 0,
    'total_mb': 370,
    'message': '',
}
_mert_downloaded = threading.Event()  # MERT 下载+导出完成时 set()


def is_mert_downloaded():
    """检查 MERT ONNX 模型是否已就绪（已下载 + 已导出）"""
    onnx_path = _get_audio_onnx_path()
    return os.path.isfile(onnx_path)


def get_mert_download_progress():
    """获取 MERT 模型下载进度（供 API 轮询）"""
    return dict(_mert_download_progress)


def wait_for_mert_download(timeout=600):
    """等待 MERT 下载+导出完成（供 worker 线程调用）"""
    _mert_downloaded.wait(timeout=timeout)


def _cleanup_pytorch_cache():
    """清理 MERT PyTorch 原始模型缓存和废弃的 fp16 模型（节省 ~478MB）"""
    global _pytorch_cache_cleaned
    if _pytorch_cache_cleaned:
        return
    _pytorch_cache_cleaned = True
    try:
        import shutil
        from huggingface_hub.constants import HF_HUB_CACHE
        cache_name = _AUDIO_MODEL_NAME.replace('/', '--')
        pytorch_cache_dir = os.path.join(HF_HUB_CACHE, f'models--{cache_name}')
        if os.path.isdir(pytorch_cache_dir):
            shutil.rmtree(pytorch_cache_dir, ignore_errors=True)
        # 清理废弃的 fp16 模型文件
        fp16_path = _get_audio_onnx_path().replace('.onnx', '-fp16.onnx')
        if os.path.isfile(fp16_path):
            os.remove(fp16_path)
    except Exception:
        pass


def _export_mert_to_onnx():
    """
    下载 MERT-v1-95M 模型，导出音频编码器为 ONNX 格式。
    只在首次运行时调用一次，导出后缓存到本地。
    """
    global _mert_download_progress
    try:
        import torch
        from transformers import Wav2Vec2Model
        import onnx  # noqa: F401  torch.onnx.export 需要此模块
    except ImportError:
        raise RuntimeError(
            'ONNX 导出需要 transformers、torch 和 onnx。'
            '请运行: pip install transformers torch onnx'
        )

    _mert_download_progress = {
        'status': 'checking',
        'percent': 0,
        'downloaded_mb': 0,
        'total_mb': 0,
        'message': '正在检查环境，准备下载音频分析模型...',
    }

    from tqdm import tqdm as _tqdm_base

    class _MertProgressTqdm(_tqdm_base):
        """自定义 tqdm 类：把 snapshot_download 的实时进度同步到 _mert_download_progress"""
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._last_n = 0
            self._last_t = time.monotonic()

        def update(self, n=1):
            super().update(n)
            if self.total and self.total > 0:
                dl = round(self.n / (1024 * 1024), 1)
                total = round(self.total / (1024 * 1024), 0)
                pct = int(self.n / self.total * 100)
                # 计算下载速度
                now = time.monotonic()
                speed = ''
                if now > self._last_t and self.n > self._last_n:
                    rate = (self.n - self._last_n) / (now - self._last_t)
                    if rate > 1024 * 1024:
                        speed = f'  {rate / (1024 * 1024):.1f} MB/s'
                    elif rate > 1024:
                        speed = f'  {rate / 1024:.0f} KB/s'
                self._last_n = self.n
                self._last_t = now
                _mert_download_progress.update({
                    'status': 'downloading',
                    'percent': pct,
                    'downloaded_mb': dl,
                    'total_mb': total,
                    'message': f'正在下载音频分析模型{speed}',
                })

    local_dir_snapshot = _retry_snapshot_download(
        _AUDIO_MODEL_NAME,
        local_dir=None,
        tqdm_class=_MertProgressTqdm,
        progress_dict=_mert_download_progress,
        label='音频分析',
    )

    _mert_download_progress.update({
        'status': 'exporting',
        'percent': 95,
        'message': '正在准备音频分析引擎...',
    })

    # 使用 HF 镜像（app.py 已设置 HF_ENDPOINT）
    model = Wav2Vec2Model.from_pretrained(local_dir_snapshot)
    model.eval()

    class MERTAudioWrapper(torch.nn.Module):
        """包装 MERT，输入原始波形，输出时间池化后的 768 维向量"""
        def __init__(self, base_model):
            super().__init__()
            self.base = base_model

        def forward(self, input_values):
            # input_values: (batch, samples) float32 @ 24kHz
            outputs = self.base(input_values, output_hidden_states=False)
            # last_hidden_state: (batch, time_steps, 768)
            pooled = outputs.last_hidden_state.mean(dim=1)
            return pooled

    wrapper = MERTAudioWrapper(model)
    dummy = torch.randn(1, _AUDIO_SAMPLE_RATE * _AUDIO_CLIP_SECONDS)

    onnx_path = _get_audio_onnx_path()
    torch.onnx.export(
        wrapper,
        (dummy,),
        onnx_path,
        input_names=['input_values'],
        output_names=['audio_embedding'],
        dynamic_axes={
            'input_values': {0: 'batch', 1: 'time'},
            'audio_embedding': {0: 'batch'},
        },
        opset_version=14,
        dynamo=False,  # 使用旧版 ONNX 导出，不需要 onnxscript
    )

    # 释放 PyTorch 模型内存
    del model, wrapper

    # 清理 PyTorch 原始模型缓存（ONNX 导出后不再需要，节省 ~378MB）
    _cleanup_pytorch_cache()

    _mert_download_progress.update({
        'status': 'completed',
        'percent': 100,
        'message': '模型准备就绪',
    })
    _mert_downloaded.set()


def _get_audio_model():
    """获取或初始化音频 embedding 模型（ONNX Runtime）"""
    global _AUDIO_MODEL

    if not is_audio_available():
        raise RuntimeError(
            '音频 embedding 依赖未安装。'
            '请运行: pip install librosa soundfile'
        )

    if _AUDIO_MODEL is None:
        onnx_path = _get_audio_onnx_path()

        # 首次使用：导出 ONNX
        if not os.path.exists(onnx_path):
            _export_mert_to_onnx()
        else:
            # ONNX 已存在，尝试清理残留的 PyTorch 缓存（仅执行一次）
            _cleanup_pytorch_cache()
            # 标记 MERT 就绪（无需下载）
            _mert_download_progress.update({
                'status': 'completed',
                'percent': 100,
                'message': '模型已就绪',
            })
            _mert_downloaded.set()

        import onnxruntime as ort
        providers = _detect_providers()

        sess_options = ort.SessionOptions()
        sess_options.graph_optimization_level = (
            ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        )
        _AUDIO_MODEL = ort.InferenceSession(
            onnx_path,
            sess_options=sess_options,
            providers=providers,
        )

    return _AUDIO_MODEL


def encode_audio_batch(clips, batch_size=8, progress_callback=None):
    """
    批量生成音频 embedding。

    Args:
        clips: list of (song_id, file_path) tuples
        batch_size: 每批处理的歌曲数
        progress_callback: callable(done, total) 进度回调

    Returns:
        list of (song_id, embedding_numpy_array_or_None)
    """
    model = _get_audio_model()
    if model is None:
        return [(sid, None) for sid, _ in clips]

    batch_size = max(1, min(batch_size, len(clips)))
    results = []
    total = len(clips)

    _audio_gpu_failed = False

    for offset in range(0, total, batch_size):
        batch = clips[offset:offset + batch_size]

        # 加载音频波形
        waveforms = []
        batch_ids = []
        for song_id, file_path in batch:
            waveform = _load_audio_clip(file_path)
            if waveform is not None:
                waveforms.append(waveform)
                batch_ids.append(song_id)
            else:
                results.append((song_id, None))

        if waveforms:
            stacked = np.stack(waveforms, axis=0)
            try:
                outputs = model.run(None, {'input_values': stacked})
            except Exception as e:
                err = str(e)
                if not _audio_gpu_failed and ('Gelu' in err or 'Dml' in err or 'UnicodeDecodeError' in repr(e) or '0x8007000E' in err):
                    _audio_gpu_failed = True
                    global _AUDIO_MODEL
                    _AUDIO_MODEL = None
                    import onnxruntime as ort
                    sess_options = ort.SessionOptions()
                    sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
                    onnx_path = _get_audio_onnx_path()
                    _AUDIO_MODEL = ort.InferenceSession(
                        onnx_path, sess_options=sess_options,
                        providers=['CPUExecutionProvider'],
                    )
                    model = _AUDIO_MODEL
                    outputs = model.run(None, {'input_values': stacked})
                else:
                    raise

            embeddings = outputs[0]
            for i, sid in enumerate(batch_ids):
                emb = embeddings[i].astype(np.float32)
                results.append((sid, emb))

        if progress_callback:
            progress_callback(min(offset + batch_size, total), total)

    return results


def encode_single_audio(file_path):
    """编码单首歌曲的音频，返回 numpy array 或 None"""
    waveform = _load_audio_clip(file_path)
    if waveform is None:
        return None
    model = _get_audio_model()
    outputs = model.run(None, {'input_values': waveform[np.newaxis, :]})
    return outputs[0][0].astype(np.float32)
