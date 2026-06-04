"""视频片段验证、清理与黑屏视频生成。"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from Common.video_utils.probe import get_video_duration, has_video_stream


def validate_output(output_dir: Path, expected_total_duration: float):
    """验证切分后的视频片段总时长是否与原始视频一致。"""
    print("\n--- 验证输出 ---")
    video_files = list(output_dir.glob("*.mp4"))
    if not video_files:
        print("未找到视频文件，无法验证。")
        return

    try:
        video_files.sort(key=lambda x: float(x.stem))
    except ValueError:
        print("[警告] 无法按数字文件名排序，验证可能不准确。")

    total_duration = 0.0
    print(f"找到 {len(video_files)} 个片段，计算总时长...")
    for vf in video_files:
        try:
            dur = get_video_duration(vf)
            total_duration += dur
        except Exception as e:
            print(f"[错误] 获取 {vf.name} 时长失败: {e}")

    print(f"片段总时长: {total_duration:.3f}s")
    print(f"原始视频时长: {expected_total_duration:.3f}s")

    diff = abs(total_duration - expected_total_duration)
    if diff < 0.5:
        print("验证通过：时长匹配。")
    else:
        print(f"验证失败：差异 {diff:.3f}s")


def is_valid_video_clip(video_path: Path) -> bool:
    """验证视频片段是否有效（非空、有视频流、时长 > 0）。"""
    try:
        if not video_path.exists() or video_path.stat().st_size == 0:
            return False
    except OSError:
        return False
    if not has_video_stream(video_path):
        return False
    try:
        return get_video_duration(video_path) > 0.001
    except RuntimeError:
        return False


def cleanup_invalid_clips(output_dir: Path):
    """将无效片段（无视频流或零时长）移到子目录，避免合并时出错。"""
    video_files = list(output_dir.glob("*.mp4"))
    if not video_files:
        return
    bad_dir = output_dir / "_bad_clips"
    moved = 0
    for vf in video_files:
        if not is_valid_video_clip(vf):
            bad_dir.mkdir(exist_ok=True)
            try:
                shutil.move(str(vf), str(bad_dir / vf.name))
                moved += 1
            except Exception as e:
                print(f"[警告] 无法移动无效片段 {vf.name}: {e}")
    if moved:
        print(f"跳过 {moved} 个无效片段，已移至: {bad_dir}")


def create_blank_video(
    output_path: Path,
    duration: float,
    width: int = 1280,
    height: int = 720,
    fps: float = 30.0,
):
    """创建指定时长的黑屏视频。"""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return
    cmd = [
        ffmpeg, "-y",
        "-f", "lavfi",
        "-i", f"color=c=black:s={width}x{height}:r={fps}",
        "-t", f"{duration:.3f}",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-an",
        str(output_path),
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
