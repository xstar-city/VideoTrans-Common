"""ffmpeg 音视频操作（提取音频、替换音轨、压缩视频）。

命名常量和路径构建函数在 Common.config 中定义。
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from Common.video_utils.probe import detect_gpu_available, get_video_dimensions


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


def compress_video_for_upload(
    video_path: Path,
    output_path: Path,
    *,
    target_short_side: int = 480,
    target_fps: int = 25,
    use_gpu: bool | None = None,
):
    """压缩视频用于上传到服务端（视觉 diarization 场景）。

    压缩策略（仅用于上传，最终合成仍使用本地高清原版）：
    - 短边缩放到 target_short_side（不放大：原始短边更小时保持原分辨率）
      短边 >= 480px 与 S3FD minDetSize 对齐，保证人脸检测召回率。
    - 帧率降至 target_fps（流水线 ffmpeg 会强制 25fps，提前降帧率减小体积）
    - H.264 编码，CRF 30（视觉 diarization 只需识别人脸/嘴部运动，不需要高质量画面）
    - 音频降至 64k AAC（仅需供服务端抽取音频做 ASR，音质要求低）
    - 有 GPU 时使用 h264_nvenc 硬件加速

    参数:
        video_path: 原始视频路径
        output_path: 压缩后输出路径（建议用 Common.config.build_compressed_upload_path 构建）
        target_short_side: 目标短边像素数，默认 480
        target_fps: 目标帧率，默认 25（与流水线 default_params FPS 对齐）
        use_gpu: 是否使用 GPU 编码。None 表示自动检测。
    """
    if use_gpu is None:
        use_gpu = detect_gpu_available()

    orig_w, orig_h = get_video_dimensions(video_path)
    short_side = min(orig_w, orig_h)

    # 构建缩放滤镜：仅在原始短边 > 目标时缩放，不放大
    filters: list[str] = []
    if short_side > target_short_side:
        if orig_w >= orig_h:
            # 横屏：高度设为目标，宽度自动（-2 保证偶数）
            filters.append(f"scale=-2:{target_short_side}")
        else:
            # 竖屏：宽度设为目标，高度自动
            filters.append(f"scale={target_short_side}:-2")
    filters.append(f"fps={target_fps}")
    vf = ",".join(filters)

    if use_gpu:
        cmd = [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-vf", vf,
            "-c:v", "h264_nvenc",
            "-preset", "p4",
            "-cq", "30",
            "-c:a", "aac",
            "-b:a", "64k",
            str(output_path),
        ]
    else:
        cmd = [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-vf", vf,
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "30",
            "-c:a", "aac",
            "-b:a", "64k",
            str(output_path),
        ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
