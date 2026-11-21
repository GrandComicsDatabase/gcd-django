"""The stylesheet must work in browsers without CSS nesting.

Such browsers drop a rule written inside another rule, so output.css
must hold only plain rules, inside at-rules like @media at most.
"""

from pathlib import Path

OUTPUT_CSS = Path(__file__).resolve().parents[3] / 'static/css/output.css'


def nested_selectors(css):
    """Return the preludes of the blocks opened inside a style rule."""
    nested = []
    open_blocks = []  # True for a style rule, False for an at-rule.
    prelude = ''
    position = 0
    while position < len(css):
        character = css[position]
        if css.startswith('/*', position):
            end = css.find('*/', position + 2)
            position = len(css) if end == -1 else end + 2
            continue
        if character == '\\':
            prelude += css[position:position + 2]
            position += 2
            continue
        if character in '"\'':
            end = position + 1
            while end < len(css) and css[end] != character:
                end += 2 if css[end] == '\\' else 1
            prelude += css[position:end + 1]
            position = end + 1
            continue
        if character == '{':
            prelude = prelude.strip()
            if open_blocks and open_blocks[-1]:
                nested.append(prelude)
            open_blocks.append(not prelude.startswith('@'))
            prelude = ''
        elif character == '}':
            if open_blocks:
                open_blocks.pop()
            prelude = ''
        elif character == ';':
            prelude = ''
        else:
            prelude += character
        position += 1
    return nested


def test_nested_rules_are_found():
    assert nested_selectors(
        '@media (min-width: 640px) { .a { color: red; } }') == []
    assert nested_selectors(
        '.a { color: red; b { color: blue; } }') == ['b']
    assert nested_selectors(
        '.a { @media (min-width: 640px) { color: blue; } }') == [
            '@media (min-width: 640px)']


def test_no_rule_is_nested_in_output_css():
    css = OUTPUT_CSS.read_text(encoding='utf-8')

    assert nested_selectors(css) == []
