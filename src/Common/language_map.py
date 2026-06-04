"""语言代码映射与目录名工具（无 lingua 依赖）。

供客户端和服务端共享使用，包含：
- 语言代码 → 显示名映射
- 显示名 → 语言代码反向映射
- 语言目录名解析
- 目标语言代码标准化
"""

from __future__ import annotations

from typing import Dict, List


# 语言代码 → 显示名映射（从服务端 language_utils.py 中提取，不含 lingua 依赖）
COMMON_LANGUAGE_CODE_MAP: Dict[str, str] = {
    'en': 'English',
    'zh': 'Chinese',
    'zh-cn': 'Chinese',
    'zh_cn': 'Chinese',
    'zh-tw': 'Traditional Chinese',
    'zh_tw': 'Traditional Chinese',
    'ru': 'Russian',
    'ja': 'Japanese',
    'ko': 'Korean',
    'es': 'Spanish',
    'fr': 'French',
    'pt': 'Portuguese',
    'de': 'German',
    'it': 'Italian',
    'th': 'Thai',
    'vi': 'Vietnamese',
    'id': 'Indonesian',
    'ms': 'Malay',
    'ar': 'Arabic',
    'hi': 'Hindi',
    'he': 'Hebrew',
    'my': 'Burmese',
    'ta': 'Tamil',
    'ur': 'Urdu',
    'bn': 'Bengali',
    'pl': 'Polish',
    'nl': 'Dutch',
    'ro': 'Romanian',
    'tr': 'Turkish',
    'km': 'Khmer',
    'lo': 'Lao',
    'yue': 'Cantonese',
    'cs': 'Czech',
    'el': 'Greek',
    'sv': 'Swedish',
    'hu': 'Hungarian',
    'da': 'Danish',
    'fi': 'Finnish',
    'uk': 'Ukrainian',
    'bg': 'Bulgarian',
    'sr': 'Serbian',
    'te': 'Telugu',
    'af': 'Afrikaans',
    'hy': 'Armenian',
    'as': 'Assamese',
    'ast': 'Asturian',
    'eu': 'Basque',
    'be': 'Belarusian',
    'bs': 'Bosnian',
    'ca': 'Catalan',
    'ceb': 'Cebuano',
    'hr': 'Croatian',
    'arz': 'Egyptian Arabic',
    'et': 'Estonian',
    'gl': 'Galician',
    'ka': 'Georgian',
    'gu': 'Gujarati',
    'is': 'Icelandic',
    'jv': 'Javanese',
    'kn': 'Kannada',
    'kk': 'Kazakh',
    'lv': 'Latvian',
    'lt': 'Lithuanian',
    'lb': 'Luxembourgish',
    'mk': 'Macedonian',
    'mai': 'Maithili',
    'mt': 'Maltese',
    'mr': 'Marathi',
    'acm': 'Mesopotamian Arabic',
    'ary': 'Moroccan Arabic',
    'ars': 'Najdi Arabic',
    'ne': 'Nepali',
    'az': 'North Azerbaijani',
    'apc': 'North Levantine Arabic',
    'uz': 'Northern Uzbek',
    'nb': 'Norwegian Bokmal',
    'nn': 'Norwegian Nynorsk',
    'oc': 'Occitan',
    'or': 'Odia',
    'pag': 'Pangasinan',
    'scn': 'Sicilian',
    'sd': 'Sindhi',
    'si': 'Sinhala',
    'sk': 'Slovak',
    'sl': 'Slovenian',
    'ajp': 'South Levantine Arabic',
    'sw': 'Swahili',
    'tl': 'Tagalog',
    'acq': 'Taizzi-Adeni Arabic',
    'sq': 'Tosk Albanian',
    'aeb': 'Tunisian Arabic',
    'vec': 'Venetian',
    'war': 'Waray',
    'cy': 'Welsh',
    'fa': 'Western Persian',
}

# 显示名 → 语言代码反向映射
COMMON_LANGUAGE_NAME_TO_CODE_MAP: Dict[str, str] = {
    name.lower(): code
    for code, name in COMMON_LANGUAGE_CODE_MAP.items()
}


def get_language_display_name(language_code: str) -> str:
    """将语言代码转换为可读的显示名称。"""
    normalized = (language_code or '').strip().lower()
    if not normalized:
        return language_code
    return COMMON_LANGUAGE_CODE_MAP.get(normalized, normalized)


def get_language_dir_name(language_code: str) -> str:
    """将语言代码转为目录名。

    优先在 COMMON_LANGUAGE_CODE_MAP 中查找代码映射；
    其次尝试通过显示名反向查找；
    都找不到则原样返回。
    """
    normalized = (language_code or '').strip()
    if not normalized:
        return language_code

    lowered = normalized.lower()
    if lowered in COMMON_LANGUAGE_CODE_MAP:
        return COMMON_LANGUAGE_CODE_MAP[lowered]

    mapped_code = COMMON_LANGUAGE_NAME_TO_CODE_MAP.get(lowered)
    if mapped_code is not None:
        return COMMON_LANGUAGE_CODE_MAP[mapped_code]

    return normalized


def normalize_target_language_codes(target_codes: List[str]) -> List[str]:
    """标准化目标语言代码：去重、小写、去空白。"""
    normalized: List[str] = []
    seen: set[str] = set()
    for code in target_codes or []:
        key = (code or '').strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        normalized.append(key)

    if not normalized:
        raise ValueError('未提供有效的目标语言代码')
    return normalized
