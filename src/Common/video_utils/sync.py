"""视频同步编排：按 TTS 音频片段切分视频、调速对齐、合并。

客户端和服务端共享此逻辑，消除重复代码。
"""

from __future__ import annotations

import shutil
from pathlib import Path

from Common.config import SEGMENTS_DIRNAME, build_video_clips_dir
from Common.language_map import get_language_dir_name
from Common.video_utils.clip_ops import cleanup_invalid_clips, validate_output
from Common.video_utils.merge import (
    adjust_video_speed_to_match_audio,
    merge_videos,
    split_video,
)
from Common.video_utils.probe import (
    detect_gpu_available,
    get_audio_duration_ffprobe,
    get_video_dimensions,
    get_video_duration,
    get_video_fps,
)


def sync_video_to_audio(
    video_path: Path,
    lang_code: str,
    *,
    chunk_size: int = 50,
    validate: bool = False,
) -> Path:
    """将视频按 TTS 音频片段切分、调速对齐、合并，返回匹配音频时长的视频路径。

    参数：
        video_path: 原始视频文件路径
        lang_code: 目标语言代码（如 'en'）
        chunk_size: 合并分块大小（默认 50）
        validate: 是否在切分后验证时长一致性

    返回：
        同步后的视频路径（与原视频同目录，文件名含语言后缀）
    """
    video_path = video_path.resolve()
    base_dir = video_path.parent
    segments_dir = base_dir / SEGMENTS_DIRNAME
    audio_dir = segments_dir / get_language_dir_name(lang_code)

    if not segments_dir.exists():
        raise FileNotFoundError(f"segments 目录不存在: {segments_dir}")
    if not audio_dir.exists():
        raise FileNotFoundError(f"语言目录不存在: {audio_dir}")

    print(f"输入视频: {video_path}")
    print(f"目标语言: {lang_code}")

    # 获取视频信息
    try:
        video_duration = get_video_duration(video_path)
        width, height = get_video_dimensions(video_path)
        fps = get_video_fps(video_path)
        print(f"视频时长: {video_duration:.3f}s, 分辨率: {width}x{height}, 帧率: {fps}")
    except RuntimeError as e:
        raise RuntimeError(f"获取视频信息失败: {e}")

    # 从 segments 根目录的 .mp3 文件解析时间区间
    mp3_files = list(segments_dir.glob("*.mp3"))
    if not mp3_files:
        raise FileNotFoundError(f"segments 目录下未找到 .mp3 文件: {segments_dir}")

    audio_segments: list[tuple[float, float]] = []
    for mp3 in mp3_files:
        try:
            start_time = float(mp3.stem)
            duration = get_audio_duration_ffprobe(mp3)
            end_time = start_time + duration
            audio_segments.append((start_time, end_time))
        except ValueError:
            print(f"[警告] 跳过非数字文件名: {mp3.name}")
        except RuntimeError as e:
            print(f"[警告] 读取 {mp3.name} 失败: {e}")

    if not audio_segments:
        raise RuntimeError("未找到有效的音频片段。")

    audio_segments.sort(key=lambda x: x[0])

    # 构建连续时间线（从 0 开始，填充间隔）
    # tts_stems 记录有语音片段的文件名，用于后续调速时只调整语音片段（跳过间隔和尾部静音）
    final_segments: list[tuple[float, float]] = []
    tts_stems: set[str] = set()
    current_time = 0.0

    for start, end in audio_segments:
        gap = start - current_time
        if gap > 0.001:
            silence_name = f"{current_time:.3f}"
            vad_name = f"{start:.3f}"
            if silence_name == vad_name:
                # 浮点精度产生的伪间隔，丢弃
                print(f"  丢弃微小区间 {current_time:.6f}-{start:.6f} "
                      f"(时长={gap:.9f}s): 格式化文件名 '{silence_name}' "
                      f"与VAD段 '{vad_name}' 冲突")
            else:
                final_segments.append((current_time, start))

        final_segments.append((start, end))
        tts_stems.add(f"{start:.3f}")
        if end > current_time:
            current_time = end

    # 尾部静音
    if current_time < video_duration - 0.001:
        print(f"添加尾部静音: {current_time:.3f}s -> {video_duration:.3f}s")
        final_segments.append((current_time, video_duration))

    # 清理旧的 video_clips 目录，避免残留片段干扰
    output_dir = build_video_clips_dir(audio_dir)
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"共 {len(final_segments)} 个片段待处理。")

    # 自动检测 GPU
    use_gpu = detect_gpu_available()
    gpu_status = "GPU 加速 (h264_nvenc)" if use_gpu else "CPU 模式 (libx264)"
    print(f"视频编码: {gpu_status}")

    # Step 1: 切分视频
    print("\n--- Step 1: 切分视频 ---")
    preserved_clips = split_video(
        video_path, output_dir, final_segments,
        width=width, height=height, fps=fps, use_gpu=use_gpu,
    )

    if validate:
        validate_output(output_dir, video_duration)

    # Step 2: 调速对齐
    print("\n--- Step 2: 调速对齐 ---")
    adjust_video_speed_to_match_audio(
        audio_dir, output_dir, use_gpu=use_gpu, preserved_clips=preserved_clips,
        tts_stems=tts_stems,
    )

    # 清理无效片段
    cleanup_invalid_clips(output_dir)

    if validate:
        print("\n--- 验证调整后输出 ---")
        validate_output(output_dir, video_duration)

    # Step 3: 合并
    print("\n--- Step 3: 合并片段 ---")
    language_suffix = lang_code.strip().replace(" ", "_") or "lang"
    output_merged_filename = f"{video_path.stem}_{language_suffix}_match_audio.mp4"
    output_merged_path = base_dir / output_merged_filename

    merge_videos(output_dir, output_merged_path, chunk_size=chunk_size)

    if not output_merged_path.exists() or output_merged_path.stat().st_size == 0:
        raise RuntimeError(f"视频合并失败，片段保留在 {output_dir} 供排查。")

    print(f"同步视频已保存: {output_merged_path}")
    return output_merged_path
