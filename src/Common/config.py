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

# 翻译指南文件名
TRANSLATION_GUIDELINES_FILENAME = 'translation_guidelines.txt'

# ── ASR 子目录 ──────────────────────────────────────────
# segments/ASR/ 存放语音识别结果：
#   - 逐段识别文本：{start_s 三位小数}.txt（如 0.000.txt，与同级 mp3 片段一一对应）
#   - 全文识别字幕：full_text.srt（SRT 格式，含时间戳，可编辑后返修覆盖逐段 txt）
#   - 句子校准日志：sentence-reconcile-log.md
#   - 句子合并日志：sentence-merge-log.md
#   - 二次 diarization 校准日志：secondary-diarization-calibration-log.md

ASR_DIRNAME = 'ASR'
# ASR 全文输出文件名（SRT 格式，含时间戳）
ASR_FULL_TEXT_FILENAME = 'full_text.srt'
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

FLEXSED_EVENTS_DIRNAME = 'non_speech_vocal_events'

# ASR 残差噪音目录名（vocals 中 ASR 未识别区间的背景噪音片段）
# diarization 残差噪音片段也放入此目录，两类噪音互补、统一管理
ASR_RESIDUAL_NOISE_DIRNAME = 'asr_residual_noise'

# 合并后完整音频文件名
COMBINED_AUDIO_FILENAME = 'combined.mp3'

# 最终输出音频文件名（例如，合并背景音等其他轨道）
FINAL_AUDIO_FILENAME = 'final.mp3'

# 翻译指南文件名
TRANSLATION_GUIDELINES_FILENAME = 'translation_guidelines.txt'

# 完整翻译字幕文件名（SRT 格式，基于 ASR 时间戳和翻译文本生成，供人工检查返修）
FULL_TRANSLATION_SRT_FILENAME = 'full_translation.srt'

# 编辑重跑日志文件名（JSONL 格式，记录每次返修的变更详情）
# 存放于 segments/ 根目录，每次 edit_rerun 会话追加一行
EDIT_RERUN_LOG_FILENAME = 'edit_rerun_log.jsonl'

# ── TTS 时长感知翻译参数（客户端与服务端共享的默认值） ──────
# 客户端 argparse 默认值和服务端运行时默认值均引用以下常量，
# 确保两端参数一致。以下常量是本组参数的**唯一来源**：代码 / 测试 /
# 文档 / 规则一律引用常量名，禁止抄写数值（抄写必随调参漂移）。

# TTS 语速偏好（文本闸判定窗中心，1.0 = 与原声等速，<1 偏慢、>1 偏快）。
# 窗宽（容忍带 SLOW/FAST）是服务端内部参数（服务端/config.py 的
# TTS_MAX_AUDIO_SLOWDOWN_PCT / TTS_MAX_AUDIO_SPEEDUP_PCT），
# 客户端只暴露本偏好参数（--tts-speech-rate-preference）。
TTS_SPEECH_RATE_PREFERENCE_DEFAULT = 1.0
# TTS 时长感知翻译：每个句子的最大时长调整重试次数（LLM 重新调整翻译的次数）
TTS_AWARE_MAX_DURATION_RETRIES = 10
# TTS 时长感知翻译：收集阶段凑满目标——哑火/质量筛选存活的候选条数（供阶段 3 ASR 选优）。
# 客户端 CLI --tts-aware-min-candidate-count 可调（1-10）。
TTS_AWARE_MIN_CANDIDATE_COUNT = 3

# ── 最终音频响度（客户端与服务端共享的默认值） ──────────────
# final.mp3 整体响度目标（LUFS，EBU R128 / ATSC A/85 广播电视响度标准，
# 数值越接近 0 越响）。控制视频合成后的最终音量：
# 服务端在最终混音后把整条音频归一化到此响度。
# -24 为广播电视标准响度；要更响可调到 -18，要更轻可调到 -30。
FINAL_AUDIO_LUFS = -24.0

# ── 客户端可见日志前缀（客户端与服务端共享的协议符号） ──────
# 服务端流水线以此前缀开头的 stdout 行会被远程执行服务过滤后发给客户端
# （步骤标题 / ERROR / WARN / 取消提示等），其余行仅写入本地 pipeline.log。
# 客户端解析同样引用此常量。两端必须使用同一符号才能对得上。
CLIENT_VISIBLE_LOG_PREFIX = '>>>'

# 支持的视频容器格式后缀
VIDEO_CONTAINER_SUFFIXES = {'.mp4', '.mov', '.mkv', '.avi', '.webm', '.m4v'}

# ── 流水线派生文件命名约定 ────────────────────────────────
# 以下常量定义流水线各阶段产生的派生文件命名规则，
# 用于路径构建和扫描时排除非原始视频。

# 压缩上传视频的 stem 后缀（如 xxx_upload_480p.mp4）
COMPRESSED_UPLOAD_SUFFIX = '_upload_480p'

# 翻译后视频的 stem 后缀模板（如 xxx_translated_en.mp4）
TRANSLATED_SUFFIX_TEMPLATE = '_translated_{lang_code}'

# 流水线各阶段产生的派生文件 stem 标记，用于扫描时排除非原始视频。
# 新增派生文件类型时只需在此处添加标记，所有扫描器自动生效。
PIPELINE_DERIVED_STEM_MARKERS = (
    '_translated_',
    '_match_audio',
    '_vocals',
    '_others',
    COMPRESSED_UPLOAD_SUFFIX,
    '_denoised',
)

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
        preferred_suffix = mux_source_video.suffix or '.mp4'
    return input_path.with_name(
        f"{input_path.stem}{TRANSLATED_SUFFIX_TEMPLATE.format(lang_code=lang_code)}{preferred_suffix}"
    )


def build_compressed_upload_path(video_path: Path) -> Path:
    """构建压缩上传视频的输出路径（如 xxx_upload_480p.mp4）。

    与原视频同目录、同 stem，仅后缀变为 COMPRESSED_UPLOAD_SUFFIX + .mp4。
    保证 build_segments_dir 一致（segments 目录基于视频所在目录）。
    """
    return video_path.with_name(
        f"{video_path.stem}{COMPRESSED_UPLOAD_SUFFIX}.mp4"
    )


# ============================================================
# 存在性检查函数
# ============================================================

def has_complete_segment_outputs(output_dir: str | Path, export_format: str = 'mp3') -> bool:
    """判断分段输出是否已完整（音频文件与 ASR 文本一一对应）。

    检查逻辑：
    1. output_dir 和其下的 ASR 子目录必须存在；
    2. output_dir 中的音频文件 stem 集合与 ASR 目录中的 .txt 文件 stem 集合
       （排除 full_text.srt）完全一致。

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
