#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch248: 中文缺失补齐收尾（45 条）—— 覆盖 batch247 漏掉的 grok_* 五条 + 全部剩余可见文案

【batch246 / batch247 的实证结果 —— 从 snapshot 的 ci_diag 实读, 本批的输入】
  batch246:  fill_zh ADDED=20 existing=0 ph_mismatch=0 no_en=0   (20 条 local_tools 全部写入)
  batch247:  fill_zh added=47 existing=0 ph_skip=0 no_en=0        (47 条 gemini/grok 全部写入)
  两边占位符/幂等校验均 0 跳过 => 写入零风险。
  同时两份 dump 的 missing 计数自洽: 101(246 时) - 47(247 写入) = 54(247 时) => 幂等保护生效。

【batch247 的两个漏项, 本批补上(先认账)】
  1. grok_token_available / grok_token_expired / grok_token_not_checked / grok_token_unavailable
     / grok_weekly_limit 共 5 条 —— 我列清单时基于 batch245 被截断在 [:70] 的 dump,
     这 5 条按字母序排在截断线之外, 被我漏掉。batch247 自己的 dump 把它们列出来了。
  2. assistant_page_local_tools_keyboard_setup_message —— batch246 时它的 dump 被截断,
     我在 batch246 明确说"不盲译, 留下批"。batch246/247 的完整 dump 已给出完整原文, 本批补。

【新发现的占位符坑, 本批修正】
  search_duplicate_key_message 用的是**裸 %s**(不带序号), 我 batch246/247 的 placeholders()
  正则只匹配带序号的 %1$s / %1$d, 不匹配裸 %s —— 若直接补会漏校验。
  本批把占位符正则放宽为 %(\d+\$)?(\.\d+)?[sdif], 覆盖 %s / %d / %1$s / %1$.2f / %2$.1f 全部形态。
  涉及到的真实占位符(逐条核对过):
    %1$d          search_duplicate_key_message 之外的 accounts_count / hf_downloads_format
    %s            search_duplicate_key_message
    %1$s          files_error_format / search_failed_format / search_duplicate_key_message 之外
    %1$.2f        local_llm_hf_file_size_gb_format
    %1$.1f,%2$.1f local_llm_perf_telemetry_format
    %1$d,%2$d     workspace_detail_selected_count

【不补的(有意为之, 不是漏)】
  · language_arabic / language_persian / language_urdu —— 语言名按惯例保持原文(带国旗 emoji)
  · theme_name_claude —— 主题名是专有名词, 不翻译

【本批做什么】
  向 values-zh/strings.xml 新增 45 条中文(纯新增, 不覆盖已有条目), 写入前三项校验:
    a. 幂等(zh 已有该 key 则跳过)
    b. 占位符校验(修正后的全形态正则)
    c. 转义(' -> \\' + & < > XML 转义)
  其中 plugin_import_security_warning_* 与 workspace_detail_* 在 en 里**本来就是中文**
  (fork 作者习惯), 本批在 zh 里补同样的中文保持一致。

【为什么本批不可能假绿或改坏】
  · 只改 values-zh/strings.xml, 纯新增, 不动任何 .kt
  · 三项校验任一不通过就跳过该条(不写入), 并把跳过原因写进报告
  · 落地判定 = snapshot 能读到 ci_diag_batch248.txt 且 values-zh 出现新 key

五查:
 1. import 清单: 零(资源文件)
 2. 同文件冲突: values-zh 被在链 batch197v2/92/245/246/247 改过; 本批只在 </resources> 前追加,
    不触碰已有条目 => 锚点不相交
 3. 作用域: 零
 4. 括号配对: 校验插入块 <string> 与 </string> 数量相等
 5. 函数签名: 零
Python 三查: Q/SQ 变量构造引号; NL 显式 concat 禁 join/f-string/walrus; helper 先定义后用; 失败记录并继续
'''
import re
import sys
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
Q = chr(34)
BS = chr(92)
SQ = chr(39)
DIAG = 'ci_diag_batch248.txt'
STRINGS_EN = 'app/src/main/res/values/strings.xml'
STRINGS_ZH = 'app/src/main/res/values-zh/strings.xml'

# 修正后的全形态占位符正则: %s %d %f 以及带序号 %1$s 与带精度 %1$.2f / %2$.1f
PH_RE = re.compile(r'%([0-9]+\$)?(\.[0-9]+)?[sdif]')

ZH_FILL = [
    # --- batch247 漏掉的 grok_* 五条 ---
    ('grok_token_available', '令牌有效'),
    ('grok_token_expired', '令牌已过期'),
    ('grok_token_not_checked', '尚未检查令牌状态'),
    ('grok_token_unavailable', '令牌不可用'),
    ('grok_weekly_limit', '每周额度'),
    # --- batch246 时因截断没补的 keyboard_setup_message(完整原文已从 batch246/247 dump 拿到) ---
    ('assistant_page_local_tools_keyboard_setup_message',
     '键盘控制需要先安装配套的 agent-keyboard 应用，并将其设为当前输入法。安装后到「系统设置 > 系统 > 语言和输入法 > 屏幕键盘」切换到 agent-keyboard。两者缺一不可，否则所有键盘工具都会返回错误。'),
    # --- 其余可见文案 ---
    ('imggen_page_image_missing', '图片文件缺失，可能未从备份中恢复'),
    ('local_llm_catalog_tag_tools', '工具'),
    ('local_llm_hf_back_to_results', '返回搜索结果'),
    ('local_llm_hf_downloads_format', '%1$d 次下载'),
    ('local_llm_hf_file_size_gb_format', '%1$.2f GB'),
    ('local_llm_hf_files_error_format', '无法列出文件：%1$s'),
    ('local_llm_hf_loading_files', '正在加载文件…'),
    ('local_llm_hf_no_gguf_files', '此仓库中没有 .gguf 文件'),
    ('local_llm_hf_requires_access', '此仓库为受限或私有仓库，需要访问令牌（本应用不支持）。请改选公开仓库。'),
    ('local_llm_hf_search_action', '搜索'),
    ('local_llm_hf_search_failed_format', '搜索失败：%1$s'),
    ('local_llm_hf_search_no_results', '未找到 GGUF 仓库'),
    ('local_llm_hf_search_placeholder', '模型名，例如 Qwen3'),
    ('local_llm_hf_search_title', '搜索 HuggingFace'),
    ('local_llm_llamacpp_catalog_subtitle', '精选支持工具调用模板的 GGUF 模型，点一下即可安装。'),
    ('local_llm_llamacpp_catalog_title', '可用模型'),
    ('local_llm_llamacpp_import_action', '安装已有的 GGUF 文件'),
    ('local_llm_perf_telemetry_format', '预填充 %1$.1f tok/s · 解码 %2$.1f tok/s'),
    ('local_llm_spec_decoding_engaged_short', 'MTP 已开启'),
    ('local_llm_vision_retry', '重试视觉识别'),
    ('local_llm_vision_unavailable_caption', '此设备不支持视觉识别，将仅运行文本'),
    ('safe_mode_enter_app', '进入应用'),
    ('search_duplicate_key_continue', '仍然保存'),
    ('search_duplicate_key_message', '此 API 密钥已配置给 %s。密钥本身已隐藏。'),
    ('search_duplicate_key_title', '重复的 API 密钥'),
    ('setting_browser_per_tool_timeout_desc', '每次浏览器工具调用的硬时限。范围 10 秒至 10 分钟。'),
    ('setting_browser_per_tool_timeout_unit', '秒'),
    ('setting_browser_single_task_timeout_desc', '单次 AI 驱动的浏览器任务的硬上限，防止失控循环。范围 1 分钟至 60 分钟。'),
    ('setting_browser_single_task_timeout_unit', '分钟'),
    ('setting_page_search_web_fetch_tools_desc', '允许助手直接抓取并读取网页内容。默认开启；关闭则只使用你配置的搜索服务。'),
    ('setting_page_search_web_fetch_tools_title', '网页抓取与提取'),
    ('setting_tts_page_default_playback_speed', '默认播放速度'),
    ('setting_tts_page_default_playback_speed_description', '本地作用于所有 TTS 服务商，不改变其合成设置。'),
    ('stats_page_cache_hit_rate', '缓存命中率'),
    # --- 以下条目在 en 里本来就是中文, 在 zh 里补同样的内容保持一致 ---
    ('plugin_import_security_warning_action', '导入前请检查插件名称、作者、版本和权限声明。'),
    ('plugin_import_security_warning_message', '插件将在受限 QuickJS 沙箱中运行；网络请求仅允许清单中的域名，工具调用需要授权。请只导入可信来源的 ZIP 文件。'),
    ('plugin_import_security_warning_title', '插件安全提示'),
    ('workspace_detail_deselect_all', '取消全选'),
    ('workspace_detail_exit_selection', '退出多选'),
    ('workspace_detail_export_selected', '导出选中'),
    ('workspace_detail_select_all', '全选'),
    ('workspace_detail_selected_count', '已选 %1$d/%2$d 项'),
]

report = []


def note(msg):
    report.append(str(msg)[:900])


def lines_to_text(lines):
    out = ''
    for idx, line in enumerate(lines):
        if idx > 0:
            out += NL
        out += line
    return out


def read_lines(rel):
    p = ROOT / rel
    if not p.exists():
        return None
    return p.read_text(encoding='utf-8').split(NL)


def extract_values(lines):
    values = {}
    for line in lines:
        s = line.strip()
        if not s.startswith('<string'):
            continue
        i = s.find('name=' + Q)
        if i < 0:
            continue
        j = s.find(Q, i + 6)
        if j < 0:
            continue
        name = s[i + 6:j]
        k = s.find('>', j)
        m = s.rfind('</string>')
        if k < 0 or m < 0 or m <= k:
            values[name] = ''
            continue
        values[name] = s[k + 1:m]
    return values


def placeholders(text):
    found = set()
    for m in PH_RE.finditer(text):
        found.add(m.group(0))
    if '%%' in text:
        found.add('%%')
    return found


def xml_escape(text):
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def android_escape(text):
    return text.replace(SQ, BS + SQ)


def fill_zh():
    zp = ROOT / STRINGS_ZH
    ep = ROOT / STRINGS_EN
    if not zp.exists() or not ep.exists():
        note('FATAL strings missing zh=' + str(zp.exists()) + ' en=' + str(ep.exists()))
        return
    zlines = zp.read_text(encoding='utf-8').split(NL)
    en_values = extract_values(ep.read_text(encoding='utf-8').split(NL))
    have = extract_values(zlines)

    closing = -1
    for i in range(len(zlines) - 1, -1, -1):
        if zlines[i].strip() == '</resources>':
            closing = i
            break
    if closing < 0:
        note('FATAL </resources> not found')
        return

    block = []
    added = []
    existing = []
    ph_skip = []
    no_en = []
    for key, zh_text in ZH_FILL:
        if key in have:
            existing.append(key)
            continue
        if key not in en_values:
            no_en.append(key)
            continue
        en_ph = placeholders(en_values[key])
        zh_ph = placeholders(zh_text)
        if en_ph != zh_ph:
            ph_skip.append(key + '(en=' + ','.join(sorted(en_ph))
                           + ' zh=' + ','.join(sorted(zh_ph)) + ')')
            continue
        block.append('    <!-- rhZhRemaining248 -->')
        block.append('    <string name=' + Q + key + Q + '>' + xml_escape(android_escape(zh_text)) + '</string>')
        added.append(key)

    note('fill_zh added=' + str(len(added)) + ' existing=' + str(len(existing))
         + ' ph_skip=' + str(len(ph_skip)) + ' no_en=' + str(len(no_en)))
    for s in (ph_skip + no_en)[:14]:
        note('fill_zh SKIP ' + s)

    if not block:
        return
    joined = lines_to_text(block)
    if joined.count('<string') != joined.count('</string>'):
        note('FATAL inserted block tag imbalance, abort write')
        return
    zlines = zlines[:closing] + block + zlines[closing:]
    out = lines_to_text(zlines)
    for key in added:
        if ('name=' + Q + key + Q) not in out:
            note('FATAL selfcheck missing ' + key)
            return
    zp.write_text(out, encoding='utf-8')
    note('fill_zh WROTE ' + str(len(added)) + ' keys')


def dump_missing():
    en = read_lines(STRINGS_EN)
    zh = read_lines(STRINGS_ZH)
    if en is None or zh is None:
        note('P2 strings missing')
        return
    ken = extract_values(en)
    kzh = extract_values(zh)
    missing = []
    invis = 0
    for name in ken:
        if name in kzh:
            continue
        if name.startswith('accessibility_'):
            invis += 1
            continue
        missing.append(name + ' :: ' + ken[name][:600])
    note('P2 visible-ish missing=' + str(len(missing)) + ' accessibility_excluded=' + str(invis))
    for m in sorted(missing):
        note('P2 ' + m)


def write_diag():
    body = ''
    for line in report:
        body += str(line) + NL
    try:
        (ROOT / DIAG).write_text(body, encoding='utf-8')
        print('::error::batch248 diag written chars=' + str(len(body)) + ' lines=' + str(len(report)))
    except Exception as e:
        print('::error::batch248 diag write FAILED ' + str(e)[:300])
    sys.stdout.flush()


def main():
    for name, fn in [
        ('fill_zh remaining', fill_zh),
        ('dump remaining missing', dump_missing),
    ]:
        try:
            fn()
            note(name + ' OK')
        except SystemExit as e:
            note(name + ' EXIT ' + str(getattr(e, 'code', '?')))
        except Exception as e:
            note(name + ' EXCEPTION ' + type(e).__name__ + ' ' + str(e)[:300])
        print('::error::batch248 part done: ' + name)
        sys.stdout.flush()
    write_diag()
    print('::error::batch248 DONE lines=' + str(len(report)))


main()