# Markdown rendering and HTML sanitization

Full Notes fields and existing Markdown descriptions/biographies use
`render_markdown()` in `apps/gcd/markdown_extension.py`. Short reprint and
character/group appearance annotations remain plain text, escaped for HTML
display; they do not pass through the Markdown renderer.

## Why sanitize?

Markdown conversion can preserve raw HTML supplied in the source. Converting
Markdown therefore does not by itself make the result safe to insert into a
page. The renderer uses `nh3` to allow only the HTML elements, attributes, CSS
classes, and URL schemes listed below before calling Django's `mark_safe()`.
This prevents source text from introducing scripts, event handlers, or arbitrary
page styling through the rendered field.

## Processing order and previews

1. Convert source using `MARKDOWNX_MARKDOWN_EXTENSIONS` and its extension
   configuration. This includes line breaks, GCD references, automatic URL
   links, and the existing Tailwind formatting classes.
2. `SafeHTMLExtension` runs the shared cleaner as a final Markdown
   postprocessor, after raw HTML and generated links have been restored.
   Markdownx previews use this extension through the same settings.
3. The display renderer cleans the result unconditionally before marking it
   safe. With the default settings this deliberately cleans twice. The second
   pass ensures display safety does not depend on a deployment retaining the
   preview extension in its settings.

Removing the extension from settings would remove preview sanitization, but
would not disable the display renderer's final cleaning pass. Keep the
extension configured so previews and displayed fields use the same policy.

## Allowlist

The executable policy is `HTML_CLEANER`; keep this document in sync with it.

Allowed elements:

```text
a abbr b blockquote br caption code dd del div dl dt em
h1 h2 h3 h4 h5 h6 hr i img li ol p pre s span strong sub sup
table tbody td tfoot th thead tr ul
```

Allowed source attributes:

| Element | Attributes |
| --- | --- |
| `a` | `href`, `title` |
| `abbr` | `title` |
| `img` | `src`, `alt`, `title`, `width`, `height` |
| `td` | `colspan`, `rowspan` |
| `th` | `colspan`, `rowspan`, `scope` |

The only allowed CSS classes are `pt-4` on `p`, `list-disc list-outside ps-8`
on `ul`, and `list-decimal list-outside ps-8` on `ol`. These come from
`MARKDOWN_CLASSES`, which is also used by the Tailwind extension. Other
attributes, including `style`, `id`, `target`, and event handlers such as
`onclick` and `onerror`, are not allowed. The cleaner adds its default
`rel="noopener noreferrer"` to links.

Explicit URL schemes are limited to `http`, `https`, and `mailto`. Relative
links, including GCD links, are retained. URLs with schemes such as
`javascript` or `data` are not retained as link/image destinations. This is
HTML sanitization, not a check that a destination is trustworthy or available;
allowed remote images can still cause the browser to fetch their sources.

## Examples and compatibility

| Source | Display behavior |
| --- | --- |
| `**bold**` | Bold text is retained. |
| `[reference](https://example.org)` | A clickable link is retained. |
| `<a href="/issue/123/">Issue</a>` | The relative link is retained. |
| `<img src="x" onerror="alert(1)">` | The image element is retained; its event handler is removed. |
| `<div style="position:fixed" onclick="alert(1)">Text</div>` | The text/container remains without the style or handler. |
| `[click](javascript:alert%281%29)` | No executable JavaScript link destination survives. |

Existing raw HTML may display differently if it relies on elements,
attributes, or styling outside this policy. Lists, tables, images, and common
formatting elements are allowed, but this does not add new Markdown syntax
extensions (for example, allowing HTML tables does not enable pipe-table
Markdown syntax).

Cleaning changes rendered output only. Stored source is not rewritten; table
exports and revision source diffs retain the editable source. There is no
database migration or data conversion. Deployments must install the added
`nh3>=0.3,<0.4` dependency from `requirements.txt`.

## Maintenance and validation

`apps/gcd/tests/test_notes_rendering.py` covers display/preview agreement,
removal of executable HTML, display cleaning without the preview extension,
representative legacy HTML, source preservation, and the plain-text annotation
boundary. Run these tests when changing the policy. Synthetic cases do not
constitute an audit of all existing production HTML; compatibility should be
reviewed before broadening or narrowing the allowlist.
