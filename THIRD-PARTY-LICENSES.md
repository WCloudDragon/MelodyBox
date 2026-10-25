# 第三方组件与许可声明（THIRD-PARTY NOTICES）

MelodyBox（以下简称"本软件"）为哈尔滨信息工程学院 2023 届软件工程专业毕业设计作品，
仅用于教学演示与学术研究，不用于商业目的。

本软件在开发与分发过程中使用了下列第三方组件。各组件的著作权归其原作者所有，
并遵循其各自的许可条款；本文件保留相关版权声明与许可信息。

---

## 1. 前端与桌面运行时

| 组件 | 许可 | 项目主页 |
|---|---|---|
| Vue 3 / Vue Router / Pinia | MIT | https://github.com/vuejs |
| Element Plus | MIT | https://github.com/element-plus/element-plus |
| GSAP | GreenSock Standard License | https://gsap.com/standard-license |
| pinyin-pro | MIT | https://github.com/zh-lx/pinyin-pro |
| SortableJS | MIT | https://github.com/SortableJS/Sortable |
| Electron / Node.js | MIT | https://github.com/electron/electron |
| Chromium | BSD 3-Clause | https://www.chromium.org/ |

## 2. 后端与音视频处理

| 组件 | 许可 | 项目主页 |
|---|---|---|
| Flask / Flask-CORS | BSD 3-Clause / MIT | https://github.com/pallets/flask |
| librosa | ISC | https://github.com/librosa/librosa |
| python-soundfile | BSD 3-Clause | https://github.com/bastibe/python-soundfile |
| mutagen | GPL-2.0-or-later | https://github.com/quodlibet/mutagen |
| Pillow | HPND | https://github.com/python-pillow/Pillow |
| NumPy / SciPy / scikit-learn | BSD 3-Clause | https://numpy.org / https://scipy.org |
| langdetect | Apache-2.0 | https://github.com/Mimino666/langdetect |
| tqdm | MIT | https://github.com/tqdm/tqdm |
| mpg123 | LGPL-2.1 | https://www.mpg123.de/ |
| libsoxr | LGPL-2.1 | https://sourceforge.net/projects/soxr/ |

## 3. AI 推理与模型

| 组件 | 许可 | 项目主页 |
|---|---|---|
| ONNX Runtime / DirectML EP | MIT | https://github.com/microsoft/onnxruntime |
| fastembed | Apache-2.0 | https://github.com/qdrant/fastembed |
| Transformers | Apache-2.0 | https://github.com/huggingface/transformers |
| PyTorch | BSD 3-Clause | https://github.com/pytorch/pytorch |
| multilingual-e5-large | MIT | https://huggingface.co/intfloat/multilingual-e5-large |
| MERT-v1-95M | CC BY-NC 4.0 | https://huggingface.co/m-a-p/MERT-v1-95M |

## 4. 字体

**MiSans** — 小米科技有限责任公司发布，遵循 MiSans 字体许可（免费使用，需保留原始声明）。
许可说明：https://hyperos.mi.com/font/

---

## 5. 需要特别说明的分发义务

### 5.1 FFmpeg（GPL-3.0-or-later）

本软件随包分发 `resources/bin/ffmpeg.exe`（FFmpeg 8.1.1 essentials build，
构建参数含 `--enable-gpl --enable-version3`，因此适用 **GNU General Public License v3**）。

- 调用方式：本软件通过子进程（stdout pipe）调用该可执行文件进行音频转码，
  未与其进行静态或动态链接，属于 GPL 所称的"聚合"分发，主程序代码不受 GPL 传染。
- 对应源码：https://ffmpeg.org/download.html （与本包同源的构建见 https://www.gyan.dev/ffmpeg/builds/）
- 许可证全文：已随包附于 `licenses/GPL-3.0.txt`，亦可在 https://www.gnu.org/licenses/gpl-3.0.txt 获取。

### 5.2 MiSans 字体

字体文件 `assets/fonts/MiSansVF.ttf` 随前端资源打包分发，需保留上述字体许可声明，
不得单独拆分销售或再授权。

### 5.3 MERT-v1-95M（CC BY-NC 4.0）

该模型采用"署名—非商业性使用"许可。本软件为毕业设计作品，属非商业用途，
符合许可要求；模型权重**不随本安装包分发**，由用户在首次使用 AI 音频特征时自行下载。
任何将本软件用于商业用途的行为，均须另行获得模型权利人的授权。

### 5.4 和风天气 API

天气数据由和风天气（QWeather）提供，免费开发版仅限非商业使用，并要求在展示处署名。
本软件首页天气卡片已标注"和风天气"字样。使用条款：https://www.qweather.com/

### 5.5 mutagen（GPL-2.0-or-later）

后端元数据解析依赖 mutagen。本软件源码托管于 GitHub / Gitee 公开仓库，可满足 GPL 关于提供源码的要求；
若后续需要以闭源、非 GPL 许可的方式分发，应替换为许可兼容的元数据解析库（如 MIT 许可的 tinytag）。

---

## 6. 其他

- 本软件界面中的示例音乐、专辑封面等素材版权归各自权利人所有，仅用于功能演示，
  不随本安装包分发。
- 如对本声明有异议或需获取对应源码，请联系作者：王云龙（哈尔滨信息工程学院）。
