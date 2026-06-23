"""视频片段合并工具。

仅保留把已切好的多个 mp4 合并为一条视频的能力，供服务端
``Tools/video_combine.py`` 等独立工具使用。

历史上这里还包含 ``split_video`` / ``adjust_video_speed_to_match_audio``
等按音频时长伸缩视频的逻辑，已随"禁止视频伸缩"的简化整体下线。
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from Common.video_utils.probe import (
    detect_gpu_available,
    get_video_duration,
    get_video_resolution,
    has_audio_stream,
    has_video_stream,
)


# ============================================================
# 合并
# ============================================================

def _collect_and_sort_video_clips(
    video_clips_dir: Path,
    output_path: Path,
) -> list[Path] | None:
    """收集并排序视频片段（公共预处理逻辑）。

    返回排序后的 Path 列表，无可用片段时返回 None。
    """
    video_files = list(video_clips_dir.glob("*.mp4"))
    # 排除输出文件自身，避免循环
    video_files = [f for f in video_files if f.resolve() != output_path.resolve()]

    # 过滤无视频流的文件
    valid_files = []
    skipped = []
    for f in video_files:
        if has_video_stream(f):
            valid_files.append(f)
        else:
            skipped.append(f)
    if skipped:
        print(f"  [警告] 跳过 {len(skipped)} 个无视频流的文件")

    if not valid_files:
        print("没有可合并的视频片段。")
        return None

    # 按文件名（数字）排序
    try:
        valid_files.sort(key=lambda x: float(x.stem))
    except ValueError:
        valid_files.sort(key=lambda x: x.name)

    return valid_files


def _merge_subset_robust(
    files: list[Path],
    out_path: Path,
    use_gpu: bool,
    video_codec: str,
    preset: str,
    quality_args: list[str],
):
    """使用 filter_complex 合并一组视频（重编码，统一分辨率）。"""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg 未在 PATH 中找到")

    inputs: list[str] = []

    # 分析每个文件的音频流和分辨率
    file_infos: list[dict] = []
    any_audio = False
    max_width = 0
    max_height = 0

    for f in files:
        has_a = has_audio_stream(f)
        duration = get_video_duration(f)
        res = get_video_resolution(f)
        if res:
            w, h = res
            max_width = max(max_width, w)
            max_height = max(max_height, h)

        if has_a:
            any_audio = True
        file_infos.append({"path": f, "has_audio": has_a, "duration": duration})

    # 默认分辨率
    if max_width == 0 or max_height == 0:
        max_width, max_height = 1920, 1080

    # 确保尺寸为偶数
    if max_width % 2 != 0:
        max_width += 1
    if max_height % 2 != 0:
        max_height += 1

    # 构建 filter_complex
    video_filters: list[str] = []
    silence_filters: list[str] = []
    concat_segments: list[str] = []

    for i, info in enumerate(file_infos):
        if use_gpu:
            inputs.extend(["-hwaccel", "cuda"])
        inputs.extend(["-i", str(info["path"])])

        v_label = f"v{i}"
        scale_cmd = (
            f"[{i}:v]scale={max_width}:{max_height}:force_original_aspect_ratio=decrease,"
            f"pad={max_width}:{max_height}:(ow-iw)/2:(oh-ih)/2,"
            f"setsar=1,"
            f"format=yuv420p[{v_label}]"
        )
        video_filters.append(scale_cmd)

        seg_v = f"[{v_label}]"

        if any_audio:
            if info["has_audio"]:
                seg_a = f"[{i}:a]"
            else:
                # 生成静音
                silence_label = f"s{i}"
                dur = info["duration"] if info["duration"] > 0 else 0.1
                silence_cmd = (
                    f"anullsrc=channel_layout=stereo:sample_rate=44100,"
                    f"atrim=duration={dur},"
                    f"asetpts=PTS-STARTPTS[{silence_label}]"
                )
                silence_filters.append(silence_cmd)
                seg_a = f"[{silence_label}]"

            concat_segments.append(f"{seg_v}{seg_a}")
        else:
            concat_segments.append(f"{seg_v}")

    # 组合滤镜
    full_filter = ""
    if video_filters:
        full_filter += ";".join(video_filters) + ";"
    if silence_filters:
        full_filter += ";".join(silence_filters) + ";"

    full_filter += "".join(concat_segments)

    if any_audio:
        full_filter += f"concat=n={len(files)}:v=1:a=1[v][a]"
        map_args = ["-map", "[v]", "-map", "[a]"]
    else:
        full_filter += f"concat=n={len(files)}:v=1:a=0[v]"
        map_args = ["-map", "[v]"]

    cmd = [
        ffmpeg, "-y",
        *inputs,
        "-filter_complex", full_filter,
        *map_args,
        "-c:v", video_codec, "-preset", preset, *quality_args,
    ]

    if any_audio:
        cmd.extend(["-c:a", "aac"])

    cmd.append(str(out_path))

    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def _merge_subset_concat_demuxer(
    files: list[Path],
    out_path: Path,
    video_codec: str,
    preset: str,
    quality_args: list[str],
):
    """使用 concat demuxer 合并一组视频（重编码，避免命令行过长）。"""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg 未在 PATH 中找到")

    any_audio = any(has_audio_stream(f) for f in files)

    list_file = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        ) as tf:
            list_file = Path(tf.name)
            for f in files:
                path_str = str(f).replace("'", "'\\''")
                tf.write(f"file '{path_str}'\n")

        cmd = [
            ffmpeg, "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(list_file),
            "-c:v", video_codec, "-preset", preset, *quality_args,
        ]

        if any_audio:
            cmd.extend(["-c:a", "aac"])
        else:
            cmd.extend(["-an"])

        cmd.append(str(out_path))

        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    finally:
        if list_file and list_file.exists():
            try:
                list_file.unlink()
            except OSError:
                pass


def merge_videos(
    video_clips_dir: Path,
    output_path: Path,
    chunk_size: int = 50,
):
    """合并目录下所有 MP4 视频片段为一个完整视频。

    策略：
    - 少量文件（≤ chunk_size）：使用 filter_complex 重编码（robust 模式，统一分辨率/帧率）；
    - 大量文件：分块用 robust 模式合并中间结果，再用 concat demuxer 合并中间结果。
    """
    use_gpu = detect_gpu_available()
    gpu_status = "GPU 加速 (h264_nvenc)" if use_gpu else "CPU 模式 (libx264)"
    print(f"\n--- 合并视频片段 ({video_clips_dir}, {gpu_status}) ---")

    video_files = _collect_and_sort_video_clips(video_clips_dir, output_path)
    if not video_files:
        return

    print(f"共 {len(video_files)} 个片段待合并。")

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg 未在 PATH 中找到")

    if use_gpu:
        video_codec = "h264_nvenc"
        preset = "p4"
        quality_args = ["-cq", "18", "-b:v", "0"]
    else:
        video_codec = "libx264"
        preset = "fast"
        quality_args = ["-crf", "18"]

    if len(video_files) <= chunk_size:
        print(f"合并 {len(video_files)} 个文件（Robust 模式）...")
        try:
            _merge_subset_robust(
                video_files, output_path, use_gpu, video_codec, preset, quality_args,
            )
        except subprocess.CalledProcessError as e:
            print(f"[错误] 合并失败: {e.stderr.decode() if e.stderr else '未知'}")
            return
    else:
        print(f"文件较多 ({len(video_files)})，按每 {chunk_size} 个分块合并...")
        temp_dir = video_clips_dir / "temp_merge_parts"
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
        temp_dir.mkdir()

        intermediate_files: list[Path] = []
        try:
            total_chunks = (len(video_files) + chunk_size - 1) // chunk_size

            for i in range(0, len(video_files), chunk_size):
                chunk = video_files[i : i + chunk_size]
                chunk_idx = i // chunk_size
                part_output = temp_dir / f"part_{chunk_idx:03d}.mp4"

                print(f"  处理分块 {chunk_idx + 1}/{total_chunks} ({len(chunk)} 个文件)...")
                _merge_subset_robust(
                    chunk, part_output, use_gpu, video_codec, preset, quality_args,
                )
                intermediate_files.append(part_output)

            print(f"合并 {len(intermediate_files)} 个中间结果...")
            _merge_subset_concat_demuxer(
                intermediate_files, output_path, video_codec, preset, quality_args,
            )

        except subprocess.CalledProcessError as e:
            print(f"[错误] 分块合并失败: {e.stderr.decode() if e.stderr else '未知'}")
            return
        finally:
            if temp_dir.exists():
                shutil.rmtree(temp_dir)

    # 验证时长
    total_input_duration = sum(get_video_duration(f) for f in video_files)
    output_duration = get_video_duration(output_path)
    print(f"片段总时长: {total_input_duration:.3f}s, 合并后: {output_duration:.3f}s")
