import string
from django.core.paginator import InvalidPage

# alphabetical pagination is based on
# https://djangosnippets.org/snippets/2732/

# the get_field-routine comes from
# http://stackoverflow.com/questions/20235807/how-to-get-foreign-key-values-with-getattr-from-models


def get_repr(value):
    if callable(value):
        return '%s' % value()
    return value


def get_field(instance, field):
    field_path = field.split('__')
    attr = instance
    for elem in field_path:
        try:
            attr = get_repr(getattr(attr, elem))
        except AttributeError:
            return None
    return attr


class AlphaPaginator(object):
    """Pagination for string-based objects"""

    def __init__(self, queryset, per_page=25, orphans=0,
                 allow_empty_first_page=True):
        # ignore allow_empty_first_page and orphans, just here for compliance
        self.page_range = []
        self.object_list = queryset
        self.count = len(self.object_list)
        self.number_offset = 0

        # chunk up the objects so we don't need to iterate over the whole list
        # for each letter
        chunks = {}

        # we sort them by the first model ordering key
        for obj in self.object_list:
            if queryset:
                obj_str = str(get_field(obj, obj._meta.ordering[0]))
            else:
                obj_str = str(obj)

            letter = str.upper(obj_str[0])

            if letter not in chunks:
                chunks[letter] = []

            chunks[letter].append(obj)

        # the process for assigning objects to each page
        current_page = NamePage(self)

        for letter in string.ascii_uppercase:
            if letter not in chunks:
                current_page.add([], letter)
                continue

            # the items in object_list starting with this letter
            sub_list = chunks[letter]

            new_page_count = len(sub_list) + current_page.count
            # First, check to see if sub_list will fit or it needs to go onto
            # a new page. If assigning this list will cause the page to
            # overflow and an underflow is closer to per_page than an overflow.
            # and the page isn't empty (which means len(sub_list) > per_page)
            if new_page_count > per_page and current_page.count > 0 and \
              abs(per_page - current_page.count) < \
              abs(per_page - new_page_count):
                # make a new page
                self.page_range.append(current_page)
                current_page = NamePage(self)

            current_page.add(sub_list, letter)

        # count issues for non-ASCII-letters start of series numbers
        for letter in chunks:
            if letter not in string.ascii_uppercase:
                self.number_offset += len(chunks[letter])

        # if we finished the for loop with a page that isn't empty, add it
        if current_page.count > 0:
            self.page_range.append(current_page)

    def page(self, num):
        """Returns a Page object for the given 1-based page number."""
        if len(self.page_range) == 0:
            return None
        elif num > 0 and num <= len(self.page_range):
            return self.page_range[num-1]
        else:
            raise InvalidPage

    @property
    def num_pages(self):
        """Returns the total number of pages"""
        return len(self.page_range)


class NamePage(object):
    def __init__(self, paginator):
        self.paginator = paginator
        self.object_list = []
        self.letters = []

    @property
    def count(self):
        return len(self.object_list)

    @property
    def start_letter(self):
        if len(self.letters) > 0:
            self.letters.sort(key=str.upper)
            return self.letters[0]
        else:
            return None

    @property
    def end_letter(self):
        if len(self.letters) > 0:
            self.letters.sort(key=str.upper)
            return self.letters[-1]
        else:
            return None

    @property
    def number(self):
        return self.paginator.page_range.index(self) + 1

    # just added the methods I needed to use in the templates
    # feel free to add the ones you need too
    def has_other_pages(self):
        return len(self.object_list) > 0

    def has_previous(self):
        return self.paginator.page_range.index(self)

    def has_next(self):
        return self.paginator.page_range.index(self) + 2

    def next_page_number(self):
        return self.paginator.page_range.index(self) + 2

    def previous_page_number(self):
        return self.paginator.page_range.index(self)

    def add(self, new_list, letter=None):
        if len(new_list) > 0:
            self.object_list = self.object_list + new_list
        if letter:
            self.letters.append(letter)

    def __repr__(self):
        if self.start_letter == self.end_letter:
            return self.start_letter
        else:
            return '%c-%c' % (self.start_letter, self.end_letter)
