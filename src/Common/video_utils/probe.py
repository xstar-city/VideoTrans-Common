"""ffprobe 查询与 GPU 检测。"""

from __future__ import annotations

import shutil
import subprocess


# ============================================================
# GPU 检测
# ============================================================

def detect_gpu_available() -> bool:
    """检测当前系统是否有可用的 NVIDIA GPU（用于 ffmpeg h264_nvenc 硬件编码）。

    检测逻辑：
    1. 检查 ffmpeg 是否支持 h264_nvenc 编码器；
    2. 若 ffmpeg 不可用，回退到检查 nvidia-smi 是否存在且可运行。
    """
    # 优先通过 ffmpeg 检测编码器支持
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        try:
            result = subprocess.run(
                [ffmpeg, "-hide_banner", "-encoders"],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=10,
            )
            if "h264_nvenc" in result.stdout:
                return True
        except (subprocess.TimeoutExpired, OSError):
            pass

    # 回退：检查 nvidia-smi
    nvidia_smi = shutil.which("nvidia-smi")
    if nvidia_smi:
        try:
            result = subprocess.run(
                [nvidia_smi],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=10,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, OSError):
            pass

    return False


# ============================================================
# ffprobe 查询
# ============================================================

def _run_ffprobe(args: list[str]) -> str:
    """执行 ffprobe 命令，返回 stdout 文本。"""
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        raise RuntimeError("ffprobe 未在 PATH 中找到")
    result = subprocess.run(
        [ffprobe, *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe 执行失败: {result.stderr.strip()}")
    return result.stdout.strip()


def get_video_duration(video_path: str | Path) -> float:
    """通过 ffprobe 获取视频时长（秒）。"""
    output = _run_ffprobe([
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(video_path),
    ])
    try:
        return float(output)
    except ValueError:
        raise RuntimeError(f"无法解析视频时长: {output}")


def get_audio_duration_ffprobe(audio_path: str | Path) -> float:
    """通过 ffprobe 获取音频时长（秒），替代 pydub 依赖。"""
    output = _run_ffprobe([
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(audio_path),
    ])
    try:
        return float(output)
    except ValueError:
        raise RuntimeError(f"无法解析音频时长: {output}")


def get_video_fps(video_path: str | Path) -> float:
    """通过 ffprobe 获取视频帧率。"""
    output = _run_ffprobe([
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=r_frame_rate",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(video_path),
    ])
    try:
        if "/" in output:
            num, den = output.split("/")
            if float(den) == 0:
                return 30.0
            return float(num) / float(den)
        return float(output)
    except (ValueError, ZeroDivisionError):
        return 30.0


def get_video_dimensions(video_path: str | Path) -> tuple[int, int]:
    """通过 ffprobe 获取视频宽高。"""
    output = _run_ffprobe([
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height",
        "-of", "csv=p=0",
        str(video_path),
    ])
    try:
        parts = output.split(",")
        if len(parts) >= 2:
            return int(parts[0]), int(parts[1])
    except (ValueError, IndexError):
        pass
    return 1280, 720


def get_video_resolution(video_path: str | Path) -> tuple[int, int] | None:
    """通过 ffprobe 获取视频分辨率，返回 (width, height) 或 None。"""
    output = _run_ffprobe([
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height",
        "-of", "csv=s=x:p=0",
        str(video_path),
    ])
    try:
        w, h = map(int, output.strip().split("x"))
        return w, h
    except (ValueError, AttributeError):
        return None


def has_video_stream(video_path: str | Path) -> bool:
    """检查视频文件是否包含视频流。"""
    try:
        output = _run_ffprobe([
            "-v", "error",
            "-select_streams", "v",
            "-show_entries", "stream=codec_type",
            "-of", "csv=p=0",
            str(video_path),
        ])
        return len(output) > 0
    except RuntimeError:
        return False


def has_audio_stream(video_path: str | Path) -> bool:
    """检查视频文件是否包含音频流。"""
    try:
        output = _run_ffprobe([
            "-v", "error",
            "-select_streams", "a",
            "-show_entries", "stream=codec_type",
            "-of", "csv=p=0",
            str(video_path),
        ])
        return len(output) > 0
    except RuntimeError:
        return False
