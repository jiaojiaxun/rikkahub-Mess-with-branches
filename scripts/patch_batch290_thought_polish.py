    for token in ['as? JsonArray', 'as? JsonPrimitive', 'previewLimit = 1200',
                  'previewLimit = 2400', 'onExpand = if (hasResultDetail)']:
        if token not in new_text:
            add_fail('tools selfcheck missing ' + token)
            return

    # Check only the newly written favicon function. The file legitimately
    # contains .jsonArray/.jsonObject in other, pre-existing parsers (and in
    # our own explanatory comment), so a whole-file substring check would
    # always reject the patch before writing it. Verify the real dangerous
    # accessor forms inside the function, not arbitrary occurrences anywhere.
    new_favicon = text_of(lines[fn_start:fn_start + len(replacement)])
    if 'as? JsonObject' not in new_favicon:
        add_fail('tools favicon safe object cast missing')
        return
    if '?.jsonArray' in new_favicon or '?.jsonObject' in new_favicon:
        add_fail('tools favicon still uses throwing json accessors')
        return
    if 'joinToString("\\n")' not in new_favicon:
        add_fail('tools favicon Kotlin newline literal malformed')
        return

    write(TOOLS, new_text)
    note('tools OK: ' + ','.join(applied))