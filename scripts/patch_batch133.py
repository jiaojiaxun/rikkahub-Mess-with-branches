#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch133 v2: workspace shell 移植配套（fail-loud + 幂等）

v2 修复: AppDatabase 的 version 锚点从静态 'version = 34,' 改为动态正则匹配
(\\s*version\\s*=\\s*\\d+\\s*,), 因为 CI 形态下 version 可能已被在链 patch 改过。
迁移目标版本 = 当前版本 + 1, AutoMigration(from=old, to=new) 同步动态化。
幂等: 目标迁移已存在则跳过。

组成：
  1. jniLibs 下载: 从上游 ExTV/rikkahub-agent @a88f5854 拉 4 个 proot 二进制
     (arm64-v8a / x86_64 的 libproot_exec.so + libproot_loader.so), ELF 魔数校验,
     双源(jsdelivr -> raw.githubusercontent), 重试 3 次, 缺失则 exit(1)。
  2. 上游镜像校验: 10 个移植文件逐字节对比上游; 不一致则覆盖为上游版本并 ::warning 报告
     (安全网: 保证 CI 形态与上游逐字一致; WorkspaceTools 在插入前校验, Entity 走锚点检查)。
  3. WorkspaceTools.kt 两行插入: approvals map + listOf 注册 createInstallRootfsTool
     (WorkspaceInstallTool.kt 已随仓库推送, 同包无需 import)。
  4. libs.versions.toml + xz; workspace/build.gradle.kts + implementation(libs.xz)。
  5. AppDatabase.kt: version 动态 +1 + AutoMigration(from=old,to=new)。
  6. 冲突扫描: scripts/*.py 提及敏感文件则 ::warning (不阻塞)。

五查:
1. import 清单: 仅标准库; 插入 Kotlin 文本无新 import(同包+已存在)
2. 同文件冲突: AppDatabase/toml/workspace-build.gradle 无在链 patch 触碰(已抽查 131/132/100/124/89)
3. 作用域: listOf 内同级插入; map 顶层条目
4. 括号配对: 插入行自平衡(仅函数调用/条目), 全文件括号差值后验
5. 函数签名: 不改签名; 新增调用走已定义函数

Python 三查: 引号用 Q/SQ 构造且同一字面量只拼一次; NL 手写 concat 禁 f-string; helper 先定义后用, 失败显式 exit(1)+::error
'''
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
Q = chr(34)
SQ = chr(39)

UP = 'a88f5854b4d2e2706ea2ae8304a7d66a3f9f2bbc'
SRC1 = 'https://cdn.jsdelivr.net/gh/ExTV/rikkahub-agent@' + UP
SRC2 = 'https://raw.githubusercontent.com/ExTV/rikkahub-agent/' + UP

ELF_MAGIC = bytes([127, 69, 76, 70])

JNI_FILES = [
    ('arm64-v8a', 'libproot_exec.so'),
    ('arm64-v8a', 'libproot_loader.so'),
    ('x86_64', 'libproot_exec.so'),
    ('x86_64', 'libproot_loader.so'),
]

MIRROR_FILES = [
    'workspace/src/main/java/me/rerere/workspace/Workspace.kt',
    'workspace/src/main/java/me/rerere/workspace/WorkspaceManager.kt',
    'workspace/src/main/java/me/rerere/workspace/WorkspaceShellRunner.kt',
    'workspace/src/main/java/me/rerere/workspace/ProotShellRunner.kt',
    'workspace/src/main/java/me/rerere/workspace/RootfsInstaller.kt',
    'workspace/src/main/java/me/rerere/workspace/RootfsPatcher.kt',
    'workspace/src/main/java/me/rerere/workspace/WorkspaceBackgroundProcesses.kt',
    'app/src/main/java/me/rerere/rikkahub/data/repository/WorkspaceRepository.kt',
    'app/src/main/java/me/rerere/rikkahub/di/RepositoryModule.kt',
    'app/src/main/java/me/rerere/rikkahub/data/db/dao/WorkspaceDAO.kt',
]

WT = 'app/src/main/java/me/rerere/rikkahub/data/ai/tools/WorkspaceTools.kt'
TOML = 'gradle/libs.versions.toml'
WBG = 'workspace/build.gradle.kts'
ADB = 'app/src/main/java/me/rerere/rikkahub/data/db/AppDatabase.kt'
WE = 'app/src/main/java/me/rerere/rikkahub/data/db/entity/WorkspaceEntity.kt'


def fail(tag, msg):
    out = 'batch133 ' + str(tag) + ': ' + str(msg)
    print('::error::' + out[:1400])
    sys.stdout.flush()
    sys.exit(1)


def http_get(url, tries=3):
    last = None
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'rikkahub-ci/1.0'})
            with urllib.request.urlopen(req, timeout=90) as resp:
                code = resp.getcode()
                data = resp.read()
                if code and 200 <= int(code) < 300 and data:
                    return data
        except Exception as exc:
            last = exc
    print('::warning::batch133 http_get failed url=' + url + ' err=' + str(last)[:180])
    return None


def fetch_upstream(rel, required):
    data = http_get(SRC1 + '/' + rel)
    if data:
        return data
    data = http_get(SRC2 + '/' + rel)
    if data:
        return data
    if required:
        fail('fetch', 'cannot download upstream file: ' + rel)
    return None


def read_lines(path):
    return (ROOT / path).read_text(encoding='utf-8').split(NL)


def write_lines(path, lines):
    (ROOT / path).write_text(NL.join(lines), encoding='utf-8')


def insert_lines_after(path, pred, make_lines, label):
    lines = read_lines(path)
    hits = [i for i, ln in enumerate(lines) if pred(ln)]
    if len(hits) != 1:
        fail(label, 'anchor count=' + str(len(hits)) + ' path=' + path)
    i = hits[0]
    src = lines[i]
    indent = src[:len(src) - len(src.lstrip())]
    for offset, seg in enumerate(make_lines(indent)):
        lines.insert(i + 1 + offset, seg)
    write_lines(path, lines)
    return indent


def replace_unique_line(path, pred, new_line, label):
    lines = read_lines(path)
    hits = [i for i, ln in enumerate(lines) if pred(ln)]
    if len(hits) != 1:
        fail(label, 'anchor count=' + str(len(hits)) + ' path=' + path)
    lines[hits[0]] = new_line
    write_lines(path, lines)


def paren_delta(text):
    return text.count('(') - text.count(')') + (text.count('{') - text.count('}'))


# =====================================================================
# 1. jniLibs 下载
# =====================================================================
for abi, name in JNI_FILES:
    rel = 'workspace/src/main/jniLibs/' + abi + '/' + name
    target = ROOT / rel
    if target.exists() and target.read_bytes()[:4] == ELF_MAGIC:
        print('::notice::batch133 jniLibs present: ' + rel + ' size=' + str(target.stat().st_size))
        continue
    data = fetch_upstream(rel, required=True)
    if data[:4] != ELF_MAGIC:
        fail('jniLibs', 'downloaded file is not ELF: ' + rel)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    print('::notice::batch133 jniLibs downloaded: ' + rel + ' size=' + str(len(data)))

# =====================================================================
# 2. 上游镜像校验（WorkspaceTools 在插入前校验; Entity 走锚点检查）
# =====================================================================
print('::notice::batch133 mirror check begin (11 files)')
mirror_fixed = []
mirror_skipped = []
for rel in MIRROR_FILES + [WT]:
    up = fetch_upstream(rel, required=False)
    if up is None:
        mirror_skipped.append(rel)
        continue
    repo = (ROOT / rel).read_bytes()
    if repo == up:
        print('::notice::batch133 mirror ok: ' + rel)
    else:
        (ROOT / rel).write_bytes(up)
        mirror_fixed.append(rel)
        print('::warning file=' + rel + '::batch133 mirror fixed: repo copy differed from upstream, overwritten with upstream bytes')
if mirror_fixed:
    print('::notice::batch133 mirror fixed count=' + str(len(mirror_fixed)))
if mirror_skipped:
    print('::warning::batch133 mirror skipped (download failed): ' + str(mirror_skipped))

# Entity 锚点检查（有意偏离上游: 补了 defaultValue，不能走逐字节校验）
we_text = (ROOT / WE).read_text(encoding='utf-8')
want_default = 'defaultValue = ' + Q + 'DISABLED' + Q
if want_default not in we_text:
    print('::warning file=' + WE + '::batch133 entity check: missing ' + want_default)
if 'shell_compatibility_mode' not in we_text:
    print('::warning file=' + WE + '::batch133 entity check: missing shell_compatibility_mode')

# =====================================================================
# 3. WorkspaceTools.kt 两行插入
# =====================================================================
wt_text = (ROOT / WT).read_text(encoding='utf-8')
wt_paren_before = paren_delta(wt_text)
mark_key = Q + 'workspace_install_rootfs' + Q
if 'createInstallRootfsTool' in wt_text and mark_key in wt_text:
    print('::notice::batch133 WorkspaceTools already patched, skip')
else:
    insert_lines_after(
        WT,
        lambda ln: ln.strip().startswith(Q + 'workspace_background_kill' + Q),
        lambda indent: [indent + mark_key + ' to true,'],
        'wt-approvals',
    )
    insert_lines_after(
        WT,
        lambda ln: ln.strip() == 'createBackgroundKillTool(workspaceId, ::needsApproval, workspaceRepository),',
        lambda indent: [indent + 'createInstallRootfsTool(workspaceId, ::needsApproval, workspaceRepository),'],
        'wt-register',
    )
    wt_text2 = (ROOT / WT).read_text(encoding='utf-8')
    if 'createInstallRootfsTool(workspaceId' not in wt_text2 or mark_key not in wt_text2:
        fail('wt-selfcheck', 'insert did not apply cleanly')
    if paren_delta(wt_text2) != wt_paren_before:
        fail('wt-balance', 'paren balance changed')
    print('::notice::batch133 WorkspaceTools patched (install tool registered)')

# =====================================================================
# 4. libs.versions.toml + xz
# =====================================================================
toml_text = (ROOT / TOML).read_text(encoding='utf-8')
xz_line = 'xz = { module = ' + Q + 'org.tukaani:xz' + Q + ', version = ' + Q + '1.12' + Q + ' }'
if 'org.tukaani:xz' in toml_text:
    print('::notice::batch133 toml xz already present')
else:
    insert_lines_after(
        TOML,
        lambda ln: ln.lstrip().startswith('jmdns = {'),
        lambda indent: [xz_line],
        'toml-xz',
    )
    print('::notice::batch133 toml xz added')

# =====================================================================
# 5. workspace/build.gradle.kts + implementation(libs.xz)
# =====================================================================
wbg_text = (ROOT / WBG).read_text(encoding='utf-8')
if 'implementation(libs.xz)' in wbg_text:
    print('::notice::batch133 workspace gradle xz already present')
else:
    insert_lines_after(
        WBG,
        lambda ln: ln.strip() == 'implementation(libs.kotlinx.serialization.json)',
        lambda indent: [indent + 'implementation(libs.xz)'],
        'wbg-xz',
    )
    print('::notice::batch133 workspace gradle xz added')

# =====================================================================
# 6. AppDatabase.kt: version 动态 +1 + AutoMigration(from=old,to=new)
# =====================================================================
adb_text = (ROOT / ADB).read_text(encoding='utf-8')
adb_paren_before = paren_delta(adb_text)

version_hits = [i for i, ln in enumerate(read_lines(ADB)) if re.match(r'\s*version\s*=\s*\d+\s*,', ln)]
if len(version_hits) != 1:
    fail('adb-version', 'version anchor count=' + str(len(version_hits)) + ' path=' + ADB)
vi = version_hits[0]
m = re.search(r'version\s*=\s*(\d+)', read_lines(ADB)[vi])
if not m:
    fail('adb-version', 'cannot parse version number')
old_version = int(m.group(1))
new_version = old_version + 1
print('::notice::batch133 AppDatabase current version=' + str(old_version) + ' -> target=' + str(new_version))

target_am = 'AutoMigration(from = ' + str(old_version) + ', to = ' + str(new_version) + ')'
if target_am in adb_text:
    print('::notice::batch133 AppDatabase already migrated (v' + str(old_version) + '->' + str(new_version) + ')')
else:
    replace_unique_line(
        ADB,
        lambda ln: re.match(r'\s*version\s*=\s*\d+\s*,', ln) is not None,
        '    version = ' + str(new_version) + ',',
        'adb-version',
    )
    insert_lines_after(
        ADB,
        lambda ln: ln.strip() == 'AutoMigration(from = 29, to = 30, spec = Migration_29_30::class),',
        lambda indent: [
            indent + '// v' + str(new_version) + ': workspace shell columns (shell_status / shell_compatibility_mode, both with defaults).',
            indent + target_am + ',',
        ],
        'adb-automigration',
    )
    adb_text2 = (ROOT / ADB).read_text(encoding='utf-8')
    if ('version = ' + str(new_version) + ',') not in adb_text2 or target_am not in adb_text2:
        fail('adb-selfcheck', 'migration insert failed')
    if paren_delta(adb_text2) != adb_paren_before:
        fail('adb-balance', 'paren balance changed')
    print('::notice::batch133 AppDatabase v' + str(old_version) + '->' + str(new_version) + ' + AutoMigration applied')

# =====================================================================
# 7. 冲突扫描（不阻塞）
# =====================================================================
KEYWORDS = [
    'WorkspaceTools.kt', 'WorkspaceRepository.kt', 'WorkspaceEntity', 'WorkspaceDAO',
    'AppDatabase.kt', 'RepositoryModule', 'libs.versions.toml', 'workspace/build.gradle',
    'WorkspaceManager', 'WorkspaceDetail', 'WorkspacePage.kt', 'WorkspaceInstallTool',
    'workspace_shell', 'workspace_install_rootfs',
]
for p in sorted((ROOT / 'scripts').glob('patch_batch*.py')):
    if p.name == 'patch_batch133.py':
        continue
    try:
        text = p.read_text(encoding='utf-8', errors='ignore')
    except Exception:
        continue
    for kw in KEYWORDS:
        if kw in text:
            print('::warning file=scripts/' + p.name + '::batch133 conflict scan: mentions ' + kw)

print('batch133: ALL OK')
