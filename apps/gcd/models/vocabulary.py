"""
The names of the sequence types and of the character roles, as the database
holds them. They come from the fixtures, not from the code, so makemessages
does not see them: this module gives each name a msgid. The pages translate
a name when they show it and keep the English name for data, search and
export.
"""
from django.utils.translation import gettext_noop

# gcd_story_type (fixture storytype.yaml) in sort order, without the
# DEPRECATED_TYPES of story.py, which no form offers.
STORY_TYPE_NAMES = (
    gettext_noop('comic story'),
    gettext_noop('text story'),
    gettext_noop('text article'),
    gettext_noop('photo story'),
    gettext_noop('cover'),
    gettext_noop('cover reprint (on interior page)'),
    gettext_noop('cartoon'),
    gettext_noop('illustration'),
    gettext_noop('comics-form advertising'),
    gettext_noop('advertisement'),
    gettext_noop('promo (ad from the publisher)'),
    gettext_noop('preview (from the publisher)'),
    gettext_noop('activity'),
    gettext_noop('in-house column'),
    gettext_noop('public service announcement'),
    gettext_noop('character profile'),
    gettext_noop('statement of ownership'),
    gettext_noop('foreword, introduction, preface, afterword'),
    gettext_noop('credits, title page'),
    gettext_noop('recap'),
    gettext_noop('letters page'),
    gettext_noop('insert or dust jacket'),
    gettext_noop('filler'),
    gettext_noop('about comics'),
    gettext_noop('table of contents'),
    gettext_noop('blank page(s)'),
)

# gcd_character_role (fixture characterrole.json) in sort order.
CHARACTER_ROLE_NAMES = (
    gettext_noop('antagonist'),
    gettext_noop('cameo'),
    gettext_noop('featured'),
    gettext_noop('guest'),
    gettext_noop('supporting'),
    gettext_noop('villain'),
)
