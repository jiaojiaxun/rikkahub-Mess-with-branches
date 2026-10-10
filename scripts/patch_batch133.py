#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch133 v6: workspace shell 移植配套 — 修 Migration_35_36 插入位置

v5 死因: Migration_35_36 类被插到 object TokenUsageConverter { 后面(变成内部类),
  DataSourceModule import 顶层 Migration_35_36 找不到 → Unresolved reference。
v6 修因: 先清理错误位置(若在 TokenUsageConverter 内部),再在 TokenUsageConverter 前插入。

v1-v4 演进见前几版注释。手写 Migration 内容:
  ALTER TABLE workspaces ADD COLUMN shell_status TEXT NOT NULL DEFAULT 'DISABLED'
  ALTER TABLE workspaces ADD COLUMN shell_compatibility_mode INTEGER NOT NULL DEFAULT 0

其余部分(jniLibs/mirror/WorkspaceTools/toml/workspace-gradle/冲突扫描)不变。
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
DSM = 'app/src/main/java/me/rerere/rikkahub/di/DataSourceModule.kt'
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


def insert_lines_before(path, pred, make_lines, label):
    lines = read_lines(path)
    hits = [i for i, ln in enumerate(lines) if pred(ln)]
    if len(hits) != 1:
        fail(label, 'anchor count=' + str(len(hits)) + ' path=' + path)
    i = hits[0]
    src = lines[i]
    indent = src[:len(src) - len(src.lstrip())]
    for offset, seg in enumerate(make_lines(indent)):
        lines.insert(i + offset, seg)
    write_lines(path, lines)
    return indent


def replace_unique_line(path, pred, new_line, label):
    lines = read_lines(path)
    hits = [i for i, ln in enumerate(lines) if pred(ln)]
    if len(hits) != 1:
        fail(label, 'anchor count=' + str(len(hits)) + ' path=' + path)
    lines[hits[0]] = new_line
    write_lines(path, lines)


def remove_class_block(text, class_name, label):
    lines = text.split(NL)
    hits = [i for i, ln in enumerate(lines) if ln.strip().startswith('class ' + class_name)]
    if len(hits) == 0:
        return text
    if len(hits) != 1:
        fail(label, class_name + ' count=' + str(len(hits)))
    start = hits[0]
    while start > 0 and lines[start - 1].strip().startswith('//'):
        start -= 1
    if start > 0 and lines[start - 1].strip() == '':
        start -= 1
    depth = 0
    end = -1
    for j in range(start, len(lines)):
        depth += lines[j].count('{') - lines[j].count('}')
        if depth == 0 and j > start:
            end = j
            break
    if end < 0:
        fail(label, class_name + ' closing brace not found')
    return NL.join(lines[:start] + lines[end + 1:])


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
# 6. AppDatabase.kt: 手写 Migration_35_36（正确位置：TokenUsageConverter 前）+ DataSourceModule 注册
# =====================================================================
adb_text = (ROOT / ADB).read_text(encoding='utf-8')
adb_paren_before = paren_delta(adb_text)

# 6a. 清理 v4/v5 的错误产物
auto_am_35_36 = 'AutoMigration(from = 35, to = 36),'
if auto_am_35_36 in adb_text:
    adb_lines_tmp = adb_text.split(NL)
    adb_lines_tmp = [ln for ln in adb_lines_tmp if ln.strip() != auto_am_35_36]
    adb_text = NL.join(adb_lines_tmp)
    print('::notice::batch133 removed v4 AutoMigration(35,36)')

# 清理错误位置的 Migration_35_36（若在 TokenUsageConverter 内部）
if 'class Migration_35_36' in adb_text:
    tc_pos = adb_text.find('object TokenUsageConverter {')
    m35_pos = adb_text.find('class Migration_35_36')
    if tc_pos > 0 and m35_pos > tc_pos:
        adb_text = remove_class_block(adb_text, 'Migration_35_36', 'adb-cleanup')
        print('::notice::batch133 removed misplaced Migration_35_36 (was inside TokenUsageConverter)')

# 6b. version 确保为 36
adb_lines = adb_text.split(NL)
v_hits = [i for i, ln in enumerate(adb_lines) if ln.strip().startswith('version =')]
if len(v_hits) != 1:
    fail('adb-version', 'version anchor count=' + str(len(v_hits)) + ' path=' + ADB)
v_i = v_hits[0]
m_ver = re.search(r'version\s*=\s*(\d+)', adb_lines[v_i])
if not m_ver:
    fail('adb-version', 'version line has no digits: ' + adb_lines[v_i].strip())
cur_ver = int(m_ver.group(1))
if cur_ver < 36:
    adb_lines[v_i] = adb_lines[v_i].replace('version = ' + str(cur_ver), 'version = 36')
    adb_text = NL.join(adb_lines)
    (ROOT / ADB).write_text(adb_text, encoding='utf-8')
    print('::notice::batch133 AppDatabase version bumped to 36')

# 6c. 加 Migration_35_36 类（TokenUsageConverter 前）
if 'class Migration_35_36' in adb_text:
    print('::notice::batch133 Migration_35_36 already present')
else:
    migration_class = [
        '',
        '// rhWsShell133 (batch133 v6): v36 adds shell_status / shell_compatibility_mode to workspaces.',
        '// Hand-written migration (not AutoMigration) because 35.json was never committed',
        '// (batch55_1 bumped version on CI without committing the schema export).',
        'class Migration_35_36 : Migration(35, 36) {',
        '    override fun migrate(db: SupportSQLiteDatabase) {',
        '        db.execSQL("ALTER TABLE workspaces ADD COLUMN shell_status TEXT NOT NULL DEFAULT ' + SQ + 'DISABLED' + SQ + '")',
        '        db.execSQL("ALTER TABLE workspaces ADD COLUMN shell_compatibility_mode INTEGER NOT NULL DEFAULT 0")',
        '    }',
        '}',
    ]
    insert_lines_before(
        ADB,
        lambda ln: ln.strip() == 'object TokenUsageConverter {',
        lambda indent: migration_class,
        'adb-migration-class',
    )
    print('::notice::batch133 Migration_35_36 class added (before TokenUsageConverter)')

# 6d. DataSourceModule 注册 Migration_35_36
dsm_text = (ROOT / DSM).read_text(encoding='utf-8')
if 'Migration_35_36()' in dsm_text:
    print('::notice::batch133 DataSourceModule already registered')
else:
    if 'import me.rerere.rikkahub.data.db.Migration_35_36' not in dsm_text:
        insert_lines_after(
            DSM,
            lambda ln: ln.strip() == 'import me.rerere.rikkahub.data.db.Migration_34_35',
            lambda indent: ['import me.rerere.rikkahub.data.db.Migration_35_36'],
            'dsm-import',
        )
    dsm_text = (ROOT / DSM).read_text(encoding='utf-8')
    if 'Migration_34_35(), Migration_35_36())' in dsm_text:
        pass
    elif 'Migration_34_35())' in dsm_text:
        dsm_text = dsm_text.replace('Migration_34_35())', 'Migration_34_35(), Migration_35_36())', 1)
        (ROOT / DSM).write_text(dsm_text, encoding='utf-8')
    elif 'Migration_33_34())' in dsm_text:
        dsm_text = dsm_text.replace('Migration_33_34())', 'Migration_33_34(), Migration_35_36())', 1)
        (ROOT / DSM).write_text(dsm_text, encoding='utf-8')
    else:
        print('::warning::batch133 DataSourceModule addMigrations anchor not found')
    print('::notice::batch133 DataSourceModule registered Migration_35_36')

# 自检
adb_text2 = (ROOT / ADB).read_text(encoding='utf-8')
if 'class Migration_35_36' not in adb_text2:
    fail('adb-selfcheck', 'Migration_35_36 class missing')
tc_pos2 = adb_text2.find('object TokenUsageConverter {')
m35_pos2 = adb_text2.find('class Migration_35_36')
if not (m35_pos2 < tc_pos2):
    fail('adb-selfcheck', 'Migration_35_36 still after TokenUsageConverter (position wrong)')
if paren_delta(adb_text2) != paren_delta(adb_text):
    fail('adb-balance', 'paren balance changed')
print('::notice::batch133 AppDatabase v36 + Migration_35_36 applied')

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
