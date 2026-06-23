"""视频与音频工具函数（仅依赖 ffmpeg/ffprobe，无 Python 第三方库）。

供客户端和服务端共享使用，按功能拆分为子模块：
- probe: ffprobe 查询与 GPU 检测
- ffmpeg_ops: 音频提取/替换、路径构建
- merge: 视频片段合并（仅供独立工具使用，主流水线不再切分/调速视频）
"""

from Common.video_utils.ffmpeg_ops import (
    build_translated_output_path,
    extract_audio_ffmpeg,
    mux_audio_into_video,
)
from Common.video_utils.merge import merge_videos
from Common.video_utils.probe import (
    detect_gpu_available,
    get_audio_duration_ffprobe,
    get_video_dimensions,
    get_video_duration,
    get_video_fps,
    get_video_resolution,
    has_audio_stream,
    has_video_stream,
)

__all__ = [
    # probe
    "detect_gpu_available",
    "get_audio_duration_ffprobe",
    "get_video_dimensions",
    "get_video_duration",
    "get_video_fps",
    "get_video_resolution",
    "has_audio_stream",
    "has_video_stream",
    # ffmpeg_ops
    "build_translated_output_path",
    "extract_audio_ffmpeg",
    "mux_audio_into_video",
    # merge
    "merge_videos",
]
