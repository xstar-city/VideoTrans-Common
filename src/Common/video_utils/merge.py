"""视频片段切分、调速对齐与合并。"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from Common.video_utils.clip_ops import create_blank_video, is_valid_video_clip
from Common.video_utils.probe import (
    detect_gpu_available,
    get_audio_duration_ffprobe,
    get_video_duration,
    get_video_fps,
    get_video_resolution,
    has_audio_stream,
    has_video_stream,
)


def split_video(
    input_video: Path,
    output_dir: Path,
    segments: list[tuple[float, float]],
    width: int = 1280,
    height: int = 720,
    fps: float = 30.0,
    use_gpu: bool = False,
) -> set[str]:
    """将视频按时间区间切分为片段。

    参数：
        segments: [(start, end), ...] 时间区间列表

    返回：
        已存在跳过的片段文件名集合（preserved_clips）
    """
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

    total = len(segments)
    preserved_clips: set[str] = set()

    for i, (start, end) in enumerate(segments, 1):
        duration = end - start
        if duration <= 0.001:
            continue

        output_filename = f"{start:.3f}.mp4"
        output_path = output_dir / output_filename

        # 跳过已存在的片段（保留之前的调整结果）
        try:
            if output_path.exists() and output_path.stat().st_size > 0:
                print(f"  [{i}/{total}] 跳过已有片段 {output_filename}")
                preserved_clips.add(output_filename)
                continue
        except OSError:
            pass

        cmd = [
            ffmpeg, "-y",
            "-ss", f"{start:.3f}",
            "-i", str(input_video),
            "-t", f"{duration:.3f}",
            "-c:v", video_codec, "-preset", preset,
            *quality_args,
            "-r", str(fps),
            "-pix_fmt", "yuv420p",
            "-an",
            str(output_path),
        ]

        print(f"  [{i}/{total}] 切分 {output_filename} (起: {start:.3f}s, 长: {duration:.3f}s)...")

        try:
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            # 验证输出
            try:
                dur = get_video_duration(output_path)
                if dur <= 0:
                    raise ValueError("时长为 0")
            except (RuntimeError, ValueError):
                print(f"  [警告] 生成的片段 {output_filename} 无效，替换为黑屏视频。")
                create_blank_video(output_path, duration, width, height, fps)

        except subprocess.CalledProcessError as e:
            print(f"  [错误] 切分 {output_filename} 失败: {e.stderr.decode() if e.stderr else '未知'}")
            try:
                create_blank_video(output_path, duration, width, height, fps)
            except Exception as ex:
                print(f"  [错误] 黑屏回退也失败: {ex}")

    return preserved_clips


def adjust_video_speed_to_match_audio(
    audio_dir: Path,
    video_clips_dir: Path,
    use_gpu: bool = False,
    preserved_clips: set[str] | None = None,
    tts_stems: set[str] | None = None,
):
    """调整视频片段时长，使其与对应 TTS 音频片段匹配。

    参数：
        audio_dir: 语言目录（如 segments/Hindi/），包含 TTS 合成的 .mp3 文件
        video_clips_dir: 视频片段目录（video_clips/）
        use_gpu: 是否使用 GPU 加速编码
        preserved_clips: 跳过的保留片段集合
        tts_stems: 有语音片段的文件名集合（不含扩展名），用于过滤非片段 mp3
    """
    print("\n--- 调整视频时长以匹配音频 ---")

    audio_files = list(audio_dir.glob("*.mp3"))
    if not audio_files:
        print(f"未找到 .mp3 文件: {audio_dir}，跳过时长调整。")
        return

    # 只处理 TTS 片段对应的 mp3，排除 combined.mp3、final.mp3 等非片段文件
    if tts_stems is not None:
        audio_files = [f for f in audio_files if f.stem in tts_stems]

    if not audio_files:
        print(f"未找到 TTS 片段 .mp3 文件: {audio_dir}，跳过时长调整。")
        return

    try:
        audio_files.sort(key=lambda x: float(x.stem))
    except ValueError:
        print("[警告] 无法按数字文件名排序 .mp3 文件。")

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

    marker_dir = video_clips_dir / "_adjusted"
    preserved = set(preserved_clips or [])

    for audio_path in audio_files:
        mp4_filename = f"{audio_path.stem}.mp4"
        mp4_path = video_clips_dir / mp4_filename

        if not mp4_path.exists():
            continue
        if mp4_filename in preserved:
            print(f"  跳过保留片段（不调整）: {mp4_filename}")
            continue

        marker_path = marker_dir / f"{audio_path.stem}.done"
        if marker_path.exists():
            continue

        if not is_valid_video_clip(mp4_path):
            print(f"  跳过无效视频片段: {mp4_filename}")
            continue

        try:
            target_duration = get_audio_duration_ffprobe(audio_path)
            current_video_duration = get_video_duration(mp4_path)

            if target_duration <= 0.001 or current_video_duration <= 0.001:
                continue

            # 差异太小时跳过，避免不必要的重编码
            if abs(target_duration - current_video_duration) < 0.01:
                continue

            scale_factor = target_duration / current_video_duration
            print(f"  调整 {mp4_filename}: {current_video_duration:.3f}s -> {target_duration:.3f}s (倍速: {scale_factor:.3f})")

            temp_output = video_clips_dir / f"temp_{mp4_filename}"
            fps = get_video_fps(mp4_path)

            # setpts 调速 + fps 固定帧率 + tpad 末尾填充（克隆最后一帧）
            pad_duration = max(3.0, target_duration * 0.1)
            vf_filter = (
                f"setpts=PTS*{scale_factor:.6f},"
                f"fps={fps:.2f},"
                f"tpad=stop_mode=clone:stop_duration={pad_duration:.2f}"
            )

            cmd = [
                ffmpeg, "-y",
                "-i", str(mp4_path),
                "-filter:v", vf_filter,
                "-t", f"{target_duration:.3f}",
                "-an",
                "-c:v", video_codec, "-preset", preset,
                *quality_args,
                "-pix_fmt", "yuv420p",
                str(temp_output),
            ]

            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            shutil.move(str(temp_output), str(mp4_path))

            marker_dir.mkdir(exist_ok=True)
            try:
                marker_path.write_text("ok", encoding="utf-8")
            except Exception as e:
                print(f"  [警告] 无法写入调整标记 {mp4_filename}: {e}")

        except Exception as e:
            print(f"  [错误] 调整 {mp4_filename} 失败: {e}")
            if 'temp_output' in locals() and Path(temp_output).exists():
                try:
                    os.remove(temp_output)
                except OSError:
                    pass


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


def merge_videos_concat_demuxer(video_clips_dir: Path, output_path: Path) -> bool:
    """使用 ffmpeg concat demuxer 合并所有视频片段（简化版，无音频、无分块）。

    适用于客户端等简单场景；服务端推荐使用 merge_videos()。
    返回 True 表示成功，False 表示失败。
    """
    print(f"\n--- 合并视频片段 ({video_clips_dir}) ---")

    video_files = _collect_and_sort_video_clips(video_clips_dir, output_path)
    if not video_files:
        return False

    print(f"共 {len(video_files)} 个片段待合并。")

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg 未在 PATH 中找到")

    use_gpu = detect_gpu_available()
    if use_gpu:
        video_codec = "h264_nvenc"
        preset = "p4"
        quality_args = ["-cq", "18", "-b:v", "0"]
    else:
        video_codec = "libx264"
        preset = "fast"
        quality_args = ["-crf", "18"]

    # 写入 concat 列表文件
    list_file = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        ) as tf:
            list_file = Path(tf.name)
            for f in video_files:
                # 单引号转义
                path_str = str(f).replace("'", "'\\''")
                tf.write(f"file '{path_str}'\n")

        cmd = [
            ffmpeg, "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(list_file),
            "-c:v", video_codec, "-preset", preset,
            *quality_args,
            "-an",
            str(output_path),
        ]

        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    finally:
        if list_file and list_file.exists():
            try:
                list_file.unlink()
            except OSError:
                pass

    if not output_path.exists() or output_path.stat().st_size == 0:
        print("[错误] 合并后的视频文件不存在或为空。")
        return False

    # 验证时长
    total_input_duration = sum(get_video_duration(f) for f in video_files)
    output_duration = get_video_duration(output_path)
    print(f"片段总时长: {total_input_duration:.3f}s, 合并后: {output_duration:.3f}s")
    return True
