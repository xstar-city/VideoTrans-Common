"""视频与音频工具函数（仅依赖 ffmpeg/ffprobe，无 Python 第三方库）。

供客户端和服务端共享使用，按功能拆分为子模块：
- probe: ffprobe 查询与 GPU 检测
- ffmpeg_ops: 音频提取/替换、路径构建
- clip_ops: 片段验证、清理、黑屏视频
- merge: 切分、调速、合并
- sync: 视频同步编排（切分→调速→合并）
"""

from Common.video_utils.clip_ops import (
    cleanup_invalid_clips,
    create_blank_video,
    is_valid_video_clip,
    validate_output,
)
from Common.video_utils.ffmpeg_ops import (
    build_translated_output_path,
    extract_audio_ffmpeg,
    mux_audio_into_video,
)
from Common.video_utils.merge import (
    adjust_video_speed_to_match_audio,
    merge_videos,
    merge_videos_concat_demuxer,
    split_video,
)
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
from Common.video_utils.sync import sync_video_to_audio

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
    # clip_ops
    "cleanup_invalid_clips",
    "create_blank_video",
    "is_valid_video_clip",
    "validate_output",
    # merge
    "adjust_video_speed_to_match_audio",
    "merge_videos",
    "merge_videos_concat_demuxer",
    "split_video",
    # sync
    "sync_video_to_audio",
]
