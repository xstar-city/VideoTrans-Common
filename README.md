# videotrans-common

VideoTrans 客户端与服务端共享的常量与工具包。零 Python 第三方依赖，仅依赖系统 ffmpeg/ffprobe。

## 安装

```bash
pip install -e .
```

## 模块说明

| 模块 | 说明 | 依赖 |
|------|------|------|
| `Common.config` | 目录/文件命名常量、路径构建函数 | 无 |
| `Common.language_map` | 语言代码映射 | 无 |
| `Common.asr_languages` | ASR 支持的语言代码 | 无 |
| `Common.tts_languages` | TTS 支持的语言代码 | 无 |
| `Common.video_utils` | ffmpeg 封装（探查/剪辑/合并/同步） | 系统 ffmpeg/ffprobe |

> **注意**：`audio_sync`（音频时长同步与混音）已迁移至 `服务端/AudioProcessing/audio_sync.py`，不再属于 Common 包。
