#!/usr/bin/env python3
# batch316: register DeepSeek Search & Fetch provider (rhDeepSeek316)
# Pairs with new file search/src/main/java/me/rerere/search/DeepSeekSearchService.kt
# (committed directly in the same commit, not patched here).
#
# Touches:
#   1. search/src/main/java/me/rerere/search/SearchService.kt
#        TYPES entry + getService branch + DeepSeekOptions serializable subclass
#        (blob SHA equals snapshot: no in-chain patch touched it, repo-state anchors safe)
#   2. app/src/main/java/me/rerere/rikkahub/ui/pages/setting/SettingSearchDetailPage.kt
#        editor when-branch + api-key form
#        (CI-form anchors: this file IS modified in-chain by the search-key
#         duplicate dialog patch, so anchors are taken from the snapshot form)
#   3. app/src/main/java/me/rerere/rikkahub/ui/pages/setting/SearchApiKeyDuplicate.kt
#        exhaustive when expression must learn the new branch or compile fails
#
# Diagnostics: ci_diag_batch316_deepseek.txt (this batch owns that name).
import os

Q = chr(34)
NL = chr(10)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIAG_LINES = []
DIAG_PATH = os.path.join(ROOT, 'ci_diag_batch316_deepseek.txt')


def ind(n):
    return chr(32) * n


def diag(line):
    DIAG_LINES.append(line)
    print('batch316: ' + line)


def read_file(path):
    handle = open(path, 'r', encoding='utf-8')
    try:
        return handle.read()
    finally:
        handle.close()


def write_file(path, content):
    parent = os.path.dirname(path)
    if parent and not os.path.isdir(parent):
        os.makedirs(parent, exist_ok=True)
    handle = open(path, 'w', encoding='utf-8')
    try:
        handle.write(content)
    finally:
        handle.close()


def balanced(old, new):
    for op, cl in (('(', ')'), ('{', '}'), ('[', ']')):
        if new.count(op) - new.count(cl) != old.count(op) - old.count(cl):
            return False
    return True


def apply_before(path, part, anchor, addition):
    content = read_file(path)
    if addition.strip() in content:
        diag(part + ' SKIP already applied')
        return
    if anchor not in content:
        lines = content.split(NL)
        nearby = ''
        for i, line in enumerate(lines):
            stripped = line.strip()
            if ('CustomJsOptions' in stripped) or ('SerperOptions' in stripped) or ('DeepSeek' in stripped):
                nearby = nearby + str(i + 1) + ': ' + stripped + ' | '
        raise RuntimeError(part + ' anchor missing; nearby lines: ' + nearby)
    new_content = content.replace(anchor, addition + anchor, 1)
    if not balanced(content, new_content):
        raise RuntimeError(part + ' bracket balance broken')
    write_file(path, new_content)
    diag(part + ' OK')


def apply_after(path, part, anchor, addition):
    content = read_file(path)
    if addition.strip() in content:
        diag(part + ' SKIP already applied')
        return
    if anchor not in content:
        lines = content.split(NL)
        nearby = ''
        for i, line in enumerate(lines):
            stripped = line.strip()
            if ('SerperOptions' in stripped) or ('DeepSeek' in stripped):
                nearby = nearby + str(i + 1) + ': ' + stripped + ' | '
        raise RuntimeError(part + ' anchor missing; nearby lines: ' + nearby)
    new_content = content.replace(anchor, anchor + addition, 1)
    if not balanced(content, new_content):
        raise RuntimeError(part + ' bracket balance broken')
    write_file(path, new_content)
    diag(part + ' OK')


SVC = os.path.join(ROOT, 'search', 'src', 'main', 'java', 'me', 'rerere', 'search', 'SearchService.kt')
DETAIL = os.path.join(ROOT, 'app', 'src', 'main', 'java', 'me', 'rerere', 'rikkahub', 'ui', 'pages', 'setting', 'SettingSearchDetailPage.kt')
DUP = os.path.join(ROOT, 'app', 'src', 'main', 'java', 'me', 'rerere', 'rikkahub', 'ui', 'pages', 'setting', 'SearchApiKeyDuplicate.kt')


def p1_types():
    anchor = ind(12) + 'SerperOptions::class to ' + Q + 'Serper' + Q + ','
    addition = NL + ind(12) + 'DeepSeekOptions::class to ' + Q + 'DeepSeek' + Q + ', // rhDeepSeek316'
    apply_after(SVC, 'P1_TYPES', anchor, addition)


def p2_factory():
    anchor = ind(16) + 'is SearchServiceOptions.CustomJsOptions -> CustomJsSearchService'
    addition = ind(16) + 'is SearchServiceOptions.DeepSeekOptions -> DeepSeekSearchService // rhDeepSeek316' + NL
    apply_before(SVC, 'P2_FACTORY', anchor, addition)


def p3_options():
    anchor = ind(4) + '@Serializable' + NL + ind(4) + '@SerialName(' + Q + 'custom_js' + Q + ')'
    addition = (
        ind(4) + '@Serializable' + NL +
        ind(4) + '@SerialName(' + Q + 'deepseek' + Q + ')' + NL +
        ind(4) + 'data class DeepSeekOptions(' + NL +
        ind(8) + 'override val id: Uuid = Uuid.random(),' + NL +
        ind(8) + 'val apiKey: String = ' + Q + Q + ',' + NL +
        ind(4) + ') : SearchServiceOptions() // rhDeepSeek316' + NL + NL
    )
    apply_before(SVC, 'P3_OPTIONS', anchor, addition)


def p4_ui_when():
    anchor = ind(8) + 'is SearchServiceOptions.CustomJsOptions -> {'
    addition = (
        ind(8) + 'is SearchServiceOptions.DeepSeekOptions -> {' + NL +
        ind(12) + 'DeepSeekOptions(options) { onUpdateOptions(it) } // rhDeepSeek316' + NL +
        ind(8) + '}' + NL
    )
    apply_before(DETAIL, 'P4_UI_WHEN', anchor, addition)


def p5_ui_form():
    anchor = '@Composable' + NL + 'internal fun CustomJsOptions('
    addition = (
        '@Composable' + NL +
        'internal fun DeepSeekOptions(' + NL +
        '    options: SearchServiceOptions.DeepSeekOptions,' + NL +
        '    onUpdateOptions: (SearchServiceOptions.DeepSeekOptions) -> Unit' + NL +
        ') {' + NL +
        '    FormItem(' + NL +
        '        label = {' + NL +
        '            Text(stringResource(R.string.search_detail_api_key))' + NL +
        '        }' + NL +
        '    ) {' + NL +
        '        OutlinedTextField(' + NL +
        '            value = options.apiKey,' + NL +
        '            onValueChange = {' + NL +
        '                onUpdateOptions(options.copy(apiKey = it))' + NL +
        '            },' + NL +
        '            modifier = Modifier.fillMaxWidth()' + NL +
        '        )' + NL +
        '    }' + NL +
        '} // rhDeepSeek316' + NL + NL
    )
    apply_before(DETAIL, 'P5_UI_FORM', anchor, addition)


def p6_duplicate():
    anchor = ind(4) + 'is SearchServiceOptions.SerperOptions -> apiKey'
    addition = NL + ind(4) + 'is SearchServiceOptions.DeepSeekOptions -> apiKey // rhDeepSeek316'
    apply_after(DUP, 'P6_DUPLICATE', anchor, addition)


def main():
    parts = (p1_types, p2_factory, p3_options, p4_ui_when, p5_ui_form, p6_duplicate)
    for part in parts:
        try:
            part()
        except Exception as exc:
            diag('PART FAIL ' + str(exc))
    diag_text = ''
    for line in DIAG_LINES:
        diag_text = diag_text + line + NL
    write_file(DIAG_PATH, diag_text)
    failures = 0
    for line in DIAG_LINES:
        if 'FAIL' in line:
            failures = failures + 1
    if failures > 0:
        print('::error title=batch316::' + str(failures) + ' part(s) failed, see ci_diag_batch316_deepseek.txt')
    else:
        print('::notice title=batch316::all parts applied, see ci_diag_batch316_deepseek.txt')


main()
