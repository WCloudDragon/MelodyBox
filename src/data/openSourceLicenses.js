/**
 * 第三方组件与开源许可清单
 *
 * 说明：
 * - 只列本项目直接依赖或随包分发的组件，传递依赖不逐一展开；
 * - license 为各项目仓库声明的主要许可证，完整许可证文本与版权声明以官方仓库为准；
 * - 详细的分发义务与版权声明见随包分发的 THIRD-PARTY-LICENSES.md。
 */

export const LICENSE_GROUPS = [
  {
    title: '前端框架与组件',
    items: [
      { name: 'Vue 3', license: 'MIT', url: 'https://github.com/vuejs/core' },
      { name: 'Vue Router', license: 'MIT', url: 'https://github.com/vuejs/router' },
      { name: 'Pinia', license: 'MIT', url: 'https://github.com/vuejs/pinia' },
      { name: 'Element Plus', license: 'MIT', url: 'https://github.com/element-plus/element-plus' },
      { name: '@element-plus/icons-vue', license: 'MIT', url: 'https://github.com/element-plus/element-plus-icons' },
      { name: 'GSAP', license: 'GreenSock Standard License', url: 'https://gsap.com/standard-license' },
      { name: 'pinyin-pro', license: 'MIT', url: 'https://github.com/zh-lx/pinyin-pro' },
      { name: 'SortableJS', license: 'MIT', url: 'https://github.com/SortableJS/Sortable' }
    ]
  },
  {
    title: '桌面端运行时',
    items: [
      { name: 'Electron', license: 'MIT', url: 'https://github.com/electron/electron' },
      { name: 'Chromium', license: 'BSD 3-Clause', url: 'https://www.chromium.org/' },
      { name: 'Node.js', license: 'MIT', url: 'https://github.com/nodejs/node' }
    ]
  },
  {
    title: '后端服务与音频元数据',
    items: [
      { name: 'Flask', license: 'BSD 3-Clause', url: 'https://github.com/pallets/flask' },
      { name: 'Flask-CORS', license: 'MIT', url: 'https://github.com/corydolphin/flask-cors' },
      { name: 'librosa', license: 'ISC', url: 'https://github.com/librosa/librosa' },
      { name: 'python-soundfile', license: 'BSD 3-Clause', url: 'https://github.com/bastibe/python-soundfile' },
      { name: 'mutagen', license: 'GPL-2.0-or-later', url: 'https://github.com/quodlibet/mutagen' },
      { name: 'Pillow', license: 'HPND', url: 'https://github.com/python-pillow/Pillow' },
      { name: 'NumPy', license: 'BSD 3-Clause', url: 'https://github.com/numpy/numpy' },
      { name: 'SciPy', license: 'BSD 3-Clause', url: 'https://github.com/scipy/scipy' },
      { name: 'scikit-learn', license: 'BSD 3-Clause', url: 'https://github.com/scikit-learn/scikit-learn' },
      { name: 'langdetect', license: 'Apache-2.0', url: 'https://github.com/Mimino666/langdetect' },
      { name: 'tqdm', license: 'MIT', url: 'https://github.com/tqdm/tqdm' }
    ]
  },
  {
    title: 'AI 推理与模型',
    items: [
      { name: 'ONNX Runtime', license: 'MIT', url: 'https://github.com/microsoft/onnxruntime' },
      { name: 'ONNX Runtime DirectML', license: 'MIT', url: 'https://github.com/microsoft/onnxruntime' },
      { name: 'fastembed', license: 'Apache-2.0', url: 'https://github.com/qdrant/fastembed' },
      { name: 'Transformers', license: 'Apache-2.0', url: 'https://github.com/huggingface/transformers' },
      { name: 'PyTorch', license: 'BSD 3-Clause', url: 'https://github.com/pytorch/pytorch' },
      { name: 'multilingual-e5-large', license: 'MIT', url: 'https://huggingface.co/intfloat/multilingual-e5-large' },
      { name: 'MERT-v1-95M', license: 'CC BY-NC 4.0', url: 'https://huggingface.co/m-a-p/MERT-v1-95M' }
    ]
  },
  {
    title: '多媒体处理',
    items: [
      { name: 'FFmpeg', license: 'GPL-3.0-or-later', url: 'https://ffmpeg.org/' },
      { name: 'mpg123', license: 'LGPL-2.1', url: 'https://www.mpg123.de/' },
      { name: 'libsoxr', license: 'LGPL-2.1', url: 'https://sourceforge.net/projects/soxr/' }
    ]
  },
  {
    title: '字体',
    items: [
      { name: 'MiSans', license: 'MiSans 字体许可', url: 'https://hyperos.mi.com/font/' }
    ]
  }
]

export const LICENSE_TOTAL = LICENSE_GROUPS.reduce((sum, g) => sum + g.items.length, 0)
