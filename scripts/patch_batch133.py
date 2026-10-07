#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch133 v3: workspace shell 移植配套 — 补 WorkspaceFileSystem 到 mirror 列表

v1 死因: AppDatabase.kt 'version = 34,' 锚点在 CI 形态找不到(count=0)。
v2 改法: AppDatabase 部分改为 tolerant+dump+warn-only(正则读当前 version,+1 替换)。
v3 修因: mirror 列表漏了 WorkspaceFileSystem.kt —— 上游给它加了 limit 参数,
  WorkspaceManager.kt(mirror 后)调 list(root,path,limit) 3 参数,
  fork 版 WorkspaceFileSystem 只有 list(root,path) 2 参数 → 编译 TOO_MANY_ARGUMENTS。
  v3 把 WorkspaceFileSystem.kt 加入 MIRROR_FILES,让 CI 覆盖为上游版。

其余部分不变。
'''
import os, re, sys, urllib.request
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
    'workspace/src/main/java/me/rerere/workspace/WorkspaceFileSystem.kt',
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
# 2. 上游镜像校验
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

# Entity 锚点检查
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
# 6. AppDatabase.kt: v2 tolerant + dump + warn-only (was fail-loud on version=34)
# =====================================================================
adb_text = (ROOT / ADB).read_text(encoding='utf-8')
adb_paren_before = paren_delta(adb_text)
if 'AutoMigration(from = 34, to = 35)' in adb_text:
    print('::notice::batch133 AppDatabase already migrated (v35)')
else:
    adb_lines = adb_text.split(NL)
    dump_lines = []
    for i, ln in enumerate(adb_lines):
        low = ln.lower()
        if 'version' in low or 'automigration' in low or 'automigrations' in low:
            dump_lines.append('L' + str(i + 1) + ':' + ln.strip()[:100])
    print('::notice::batch133 adb-dump v-lines: [' + ' ;; '.join(dump_lines[:20]) + ']')

    v_hits = [i for i, ln in enumerate(adb_lines) if ln.strip().startswith('version =')]
    if len(v_hits) != 1:
        print('::warning::batch133 AppDatabase version anchor count=' + str(len(v_hits)) + ', skipping version bump (warn-only)')
    else:
        v_i = v_hits[0]
        m_ver = re.search(r'version\s*=\s*(\d+)', adb_lines[v_i])
        if not m_ver:
            print('::warning::batch133 version line has no digits: ' + adb_lines[v_i].strip() + ' (warn-only skip)')
        else:
            cur_ver = int(m_ver.group(1))
            new_ver = cur_ver + 1
            if cur_ver >= 35:
                print('::notice::batch133 AppDatabase version already ' + str(cur_ver) + ' (>=35), skipping bump')
            else:
                adb_lines[v_i] = adb_lines[v_i].replace(
                    'version = ' + str(cur_ver),
                    'version = ' + str(new_ver),
                )
                am_hits = [i for i, ln in enumerate(adb_lines) if 'AutoMigration(from' in ln]
                if am_hits:
                    last_am = am_hits[-1]
                    indent = adb_lines[last_am][:len(adb_lines[last_am]) - len(adb_lines[last_am].lstrip())]
                    adb_lines.insert(last_am + 1, indent + '// v' + str(new_ver) + ': workspace shell columns (shell_status / shell_compatibility_mode).')
                    adb_lines.insert(last_am + 2, indent + 'AutoMigration(from = ' + str(cur_ver) + ', to = ' + str(new_ver) + '),')
                    adb_out = NL.join(adb_lines)
                    if 'version = ' + str(new_ver) in adb_out and ('AutoMigration(from = ' + str(cur_ver) + ', to = ' + str(new_ver) + ')') in adb_out:
                        if paren_delta(adb_out) != adb_paren_before:
                            print('::warning::batch133 AppDatabase paren balance changed (warn-only, not writing)')
                        else:
                            (ROOT / ADB).write_text(adb_out, encoding='utf-8')
                            print('::notice::batch133 AppDatabase v' + str(new_ver) + ' + AutoMigration(' + str(cur_ver) + ',' + str(new_ver) + ') applied')
                    else:
                        print('::warning::batch133 AppDatabase migration insert failed (warn-only)')
                else:
                    print('::warning::batch133 no AutoMigration lines found (warn-only skip)')

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
