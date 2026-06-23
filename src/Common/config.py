# ============================================================
# 客户端与服务端共享的文件/目录命名约定
# ============================================================
#
# 此文件存放客户端与服务端共同依赖的文件名、目录名等命名常量，
# 以及基于这些常量的路径构建与存在性检查函数，
# 确保双方对磁盘布局的理解一致。
#
# 使用方式：
#   from Common.config import ASR_DIRNAME, build_segments_dir, ...

from __future__ import annotations

from pathlib import Path
from typing import Optional


# ============================================================
# 命名常量
# ============================================================

# ── segments 根目录 ──────────────────────────────────────
# segments/ 是整个流水线的输出根目录，与输入音频位于同一父目录。
# 内部按职责分为 ASR 子目录和各目标语言子目录。

SEGMENTS_DIRNAME = 'segments'

# 翻译全文转录文件名模板（如 full_text_en.txt）
TRANSCRIPT_FULL_TEXT_FILENAME_TEMPLATE = 'full_text_{lang_suffix}.txt'

# 翻译指南文件名
TRANSLATION_GUIDELINES_FILENAME = 'translation_guidelines.txt'

# ── ASR 子目录 ──────────────────────────────────────────
# segments/ASR/ 存放语音识别结果：
#   - 逐段识别文本：{start_s 三位小数}.txt（如 0.000.txt，与同级 mp3 片段一一对应）
#   - 全文识别文本：full_text.md
#   - 句子校准日志：sentence-reconcile-log.md
#   - 句子合并日志：sentence-merge-log.md
#   - 二次 diarization 校准日志：secondary-diarization-calibration-log.md

ASR_DIRNAME = 'ASR'
# ASR 全文输出文件名
ASR_FULL_TEXT_FILENAME = 'full_text.md'
# ASR 句子校准日志
ASR_SENTENCE_RECONCILE_FILENAME = 'sentence-reconcile-log.md'
# ASR 句子合并日志
SENTENCE_MERGE_LOG_FILENAME = 'sentence-merge-log.md'
# 二次 diarization 校准日志（secondary_diarization 模块输出）
SECONDARY_DIARIZATION_CALIBRATE_LOG_FILENAME = 'secondary-diarization-calibration-log.md'


# ── 目标语言子目录 ──────────────────────────────────────
# segments/{lang}/（如 en/、zh/）存放翻译与合成结果：
#   - 逐段翻译文本：{start_s 三位小数}.txt（如 0.000.txt）
#   - 翻译过程记录：{start_s 三位小数}.md
#   - TTS 合成音频：{start_s 三位小数}.mp3
#   - 合并后纯人声：combined.mp3
#   - 最终输出音轨：final.mp3（含背景音时为混音）
#   - 视频片段目录：video_clips/（仅视频翻译场景）

# 合并后完整音频文件名
COMBINED_AUDIO_FILENAME = 'combined.mp3'

# 最终输出音频文件名（例如，合并背景音等其他轨道）
FINAL_AUDIO_FILENAME = 'final.mp3'

# 翻译指南文件名
TRANSLATION_GUIDELINES_FILENAME = 'translation_guidelines.txt'

# TTS 目标采样率（Hz），客户端 ffmpeg 提取音频和服务端混音均使用此值
TTS_TARGET_SAMPLE_RATE = 48000

# 支持的视频容器格式后缀
VIDEO_CONTAINER_SUFFIXES = {'.mp4', '.mov', '.mkv', '.avi', '.webm', '.m4v'}

# ============================================================
# 路径构建函数
# ============================================================

def build_segments_dir(audio_path: str | Path) -> Path:
    """根据音频文件路径，返回其所属的 segments 目录。

    约定：segments 目录与音频文件位于同一父目录。
    例如：audio_path = /data/video1/en.mp3 → /data/video1/segments/
    """
    return Path(audio_path).expanduser().resolve().parent / SEGMENTS_DIRNAME


def build_asr_dir(segments_dir: str | Path) -> Path:
    """根据 segments 目录，返回 ASR 结果目录。

    例如：segments_dir = /data/video1/segments/ → /data/video1/segments/ASR/
    """
    return Path(segments_dir).expanduser().resolve() / ASR_DIRNAME


def resolve_asr_dir(input_dir: str | Path) -> Optional[Path]:
    """查找 ASR 结果目录。

    布局约定：input_dir/segments/ASR/
    若目录存在则返回路径，否则返回 None。
    """
    candidate = Path(input_dir).expanduser().resolve() / SEGMENTS_DIRNAME / ASR_DIRNAME
    return candidate if candidate.is_dir() else None


def build_combined_audio_path(segments_dir: str | Path, language_key: str) -> Path:
    """根据 segments 目录和语言标识，返回 combined.mp3 的路径。

    例如：segments_dir = /data/video1/segments/, language_key = 'en'
          → /data/video1/segments/en/combined.mp3
    """
    return Path(segments_dir).expanduser().resolve() / language_key / COMBINED_AUDIO_FILENAME


def build_final_audio_path(segments_dir: str | Path, language_key: str) -> Path:
    """根据 segments 目录和语言标识，返回 final.mp3 的路径。

    例如：segments_dir = /data/video1/segments/, language_key = 'en'
          → /data/video1/segments/en/final.mp3
    """
    return Path(segments_dir).expanduser().resolve() / language_key / FINAL_AUDIO_FILENAME


def build_transcript_full_text_path(segments_dir: str | Path, lang_suffix: str) -> Path:
    """根据 segments 目录和语言后缀，返回 full_text_{lang_suffix}.txt 的路径。

    例如：segments_dir = /data/video1/segments/, lang_suffix = 'en'
          → /data/video1/segments/full_text_en.txt
    """
    filename = TRANSCRIPT_FULL_TEXT_FILENAME_TEMPLATE.format(lang_suffix=lang_suffix)
    return Path(segments_dir).expanduser().resolve() / filename


# ============================================================
# 存在性检查函数
# ============================================================

def has_complete_segment_outputs(output_dir: str | Path, export_format: str = 'mp3') -> bool:
    """判断分段输出是否已完整（音频文件与 ASR 文本一一对应）。

    检查逻辑：
    1. output_dir 和其下的 ASR 子目录必须存在；
    2. output_dir 中的音频文件 stem 集合与 ASR 目录中的 .txt 文件 stem 集合
       （排除 full_text.txt）完全一致。

    参数：
        output_dir: 分段输出目录（通常是 segments/<lang>/）
        export_format: 音频文件扩展名，默认 'mp3'
    """
    root = Path(output_dir).expanduser().resolve()
    asr_dir = root / ASR_DIRNAME
    if not root.is_dir() or not asr_dir.is_dir():
        return False

    audio_stems = {
        path.stem
        for path in root.glob(f'*.{export_format}')
        if path.is_file()
    }
    txt_stems = {
        path.stem
        for path in asr_dir.glob('*.txt')
        if path.is_file() and path.name.lower() != ASR_FULL_TEXT_FILENAME
    }

    return bool(audio_stems) and audio_stems == txt_stems


def find_language_dirs(segments_dir: str | Path) -> list[Path]:
    """在 segments 目录中找出所有已生成合并音频的语言目录。

    约定：语言目录名不是 ASR，且包含 combined.mp3 文件。
    返回按名称排序的路径列表。
    """
    segments_path = Path(segments_dir).expanduser().resolve()
    return [
        path for path in sorted(segments_path.iterdir(), key=lambda item: item.name.lower())
        if path.is_dir() and path.name != ASR_DIRNAME and (path / COMBINED_AUDIO_FILENAME).is_file()
    ]
