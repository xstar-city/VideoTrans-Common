"""ffmpeg 音频操作与路径构建。"""

from __future__ import annotations

import subprocess
from pathlib import Path

from Common.config import VIDEO_CONTAINER_SUFFIXES


def extract_audio_ffmpeg(
    video_path: Path,
    mp3_path: Path,
):
    """从视频中提取音频为 MP3，保留原始采样率、声道布局和比特率。

    不指定 -ar、-ac、-b:a，避免重采样和比特率膨胀引入失真。
    源音频通常为 ~128kbps AAC，强制 320k CBR 只会增大文件而不增加信息量，
    且与方案 A（PowerShell 最少干预）行为完全对齐。
    TTS 合成后的重采样由 resample_if_needed 在混音阶段统一处理。
    """
    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-vn",
        "-acodec", "libmp3lame",
        str(mp3_path),
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def mux_audio_into_video(
    original_video: Path,
    audio_path: Path,
    out_video: Path,
):
    """替换视频音轨：用 audio_path 的音频替换 original_video 的音轨，输出到 out_video。"""
    cmd = [
        "ffmpeg", "-y",
        "-i", str(original_video),
        "-i", str(audio_path),
        "-c:v", "copy",
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-filter:a", "volume=2.5",
        "-shortest",
        str(out_video),
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def build_translated_output_path(
    input_path: Path,
    mux_source_video: Path,
    lang_code: str,
) -> Path:
    """构建翻译后视频的输出路径，并优先选择可承载视频流的后缀。

    逻辑说明：
    - 默认沿用输入文件后缀（input_path.suffix）；
    - 若输入后缀不是视频容器（例如 .mp3），则回退为 mux_source_video 的后缀；
    - 若回退后仍为空，则最终使用 .mp4。
    """
    preferred_suffix = input_path.suffix.lower()
    if preferred_suffix not in VIDEO_CONTAINER_SUFFIXES:
        preferred_suffix = mux_source_video.suffix or ".mp4"
    return input_path.with_name(
        f"{input_path.stem}_translated_{lang_code}{preferred_suffix}"
    )
