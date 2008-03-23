import math
from django.core.paginator import \
    ObjectPaginator as DjangoPaginator,\
    InvalidPage
from django.http import Http404

# This code is from http://www.djangosnippets.org/snippets/628/
# it uses the old Paginator API, i.e. no separation between paginator and page
# we either change that on our own or wait for the code to update on its own

class Paginator(object):
    """
    Much like Django's ``ObjectPaginator`` (which it uses), but always
    represents a specific current page instead of just providing an interface
    to the data. Based on the active page it makes a number of properties
    available which mostly work exactly like the context that the
    ``object_list`` generic view provides.

    ``__init__`` takes the same arguments as ``ObjectPaginator``, plus an
    additional parameter ``page`` to initialize the active page number. It does
    not need to be an int, i.e. it can come directly from ``request.GET``; if
    conversion to an integer fails, a ``Http404`` exception is raised.
    
    You can also later assign to to ``page`` attribute.
    
    >>> items = range(1,6789)
    >>> paginator = Paginator(items, num_per_page=10, page=3)
    >>> paginator.items
    [21, 22, 23, 24, 25, 26, 27, 28, 29, 30]
    >>> paginator.is_paginated
    True
    >>> paginator.results_per_page
    10
    >>> paginator.has_next
    True
    >>> paginator.has_previous
    True
    >>> paginator.page
    3
    >>> paginator.page0
    2
    >>> paginator.next
    4
    >>> paginator.previous
    2
    >>> paginator.last_on_page
    30
    >>> paginator.first_on_page
    21
    >>> paginator.pages
    679
    >>> paginator.hits
    6788
    """
    def __init__(self, *args, **kwargs):
        page = kwargs.pop('page', 1)
        self._paginator = DjangoPaginator(*args, **kwargs)
        
        # Resolve the page number; this is similar to what the Django
        # ``object_list`` generic view is doing.
        try:
            self.page = int(page)
        except ValueError:
            if page == 'last': self.page = self._paginator.pages
            else: raise Http404
        
    def _set_page(self, new_page):
        self.__page = new_page
        try:
            self.object_list = self._paginator.get_page(new_page-1)
        except InvalidPage:
            if new_page != -1: raise Http404
            else: self.object_list = []   # allow empty
        self.items = self.object_list # alias
        # update all exposed info for the new page number
        self.update_attrs()
    def _get_page(self): return self.__page
    page = property(_get_page, _set_page)

    def update_attrs(self):
        """Override in descendants to set custom fields."""
        self.page0 = self.page-1
        self.is_paginated = self._paginator.pages > 1
        self.results_per_page = self._paginator.num_per_page
        self.has_next = self._paginator.has_next_page(self.page-1)
        self.has_previous = self._paginator.has_previous_page(self.page-1)
        self.next = self.page+1
        self.previous = self.page-1
        self.last_on_page = self._paginator.last_on_page(self.page-1)
        self.first_on_page = self._paginator.first_on_page(self.page-1)
        self.pages = self._paginator.pages
        self.hits = self._paginator.hits
        self.page_range = self._paginator.page_range
    
class DiggPaginator(Paginator):
    """
    Adds attributes to enable Digg-style formatting, with a leading block of
    pages, an optional middle block, and another block at the end of the page
    range. They are available as attributes, to be used in the same manner
    as the default:
    
    {% for page in paginator.leading_range %} ...
    {% for page in paginator.main_range %} ...
    {% for page in paginator.trailing_range %} ...
    
    Additionally, ``page_range`` contains a nun-numeric ``False`` element
    for every transition between two ranges.
    
    {% for page in paginator.page_range %}
        {% if not page %} ...
        {% else %}{{ page }}
        {% endif %}
    {% endfor %}
    
    Additional arguments passed to the constructor allow customization of
    how those bocks are constructed:
    
    body=5, tail=2
    
    [1] 2 3 4 5 ... 91 92
    |_________|     |___|
    body            tail
              |_____|
              margin
    
    body=5, tail=2, padding=2
    
    1 2 ... 6 7 [8] 9 10 ... 91 92
            |_|     |__|
             ^padding^
    |_|     |__________|     |___|
    tail    body             tail
    
    ``margin`` is the minimum number of pages required between two ranges; if
    there are less, they are combined into one.
    
    # odd body length
    >>> print DiggPaginator(range(1,1000), 10, body=5, page=1)
    1 2 3 4 5 ... 99 100
    >>> print DiggPaginator(range(1,1000), 10, body=5, page=100)
    1 2 ... 96 97 98 99 100
    
    # even body length
    >>> print DiggPaginator(range(1,1000), 10, body=6, page=1)
    1 2 3 4 5 6 ... 99 100
    >>> print DiggPaginator(range(1,1000), 10, body=6, page=100)
    1 2 ... 95 96 97 98 99 100
    
    # leading range and main range are combined when close; note how
    # we have varying body and padding values, and their effect.
    >>> print DiggPaginator(range(1,1000), 10, body=5, padding=2, margin=2, page=3)
    1 2 3 4 5 ... 99 100
    >>> print DiggPaginator(range(1,1000), 10, body=6, padding=2, margin=2, page=4)
    1 2 3 4 5 6 ... 99 100
    >>> print DiggPaginator(range(1,1000), 10, body=5, padding=1, margin=2, page=6)
    1 2 3 4 5 6 7 ... 99 100
    >>> print DiggPaginator(range(1,1000), 10, body=5, padding=2, margin=2, page=7)
    1 2 ... 5 6 7 8 9 ... 99 100
    >>> print DiggPaginator(range(1,1000), 10, body=5, padding=1, margin=2, page=7)
    1 2 ... 5 6 7 8 9 ... 99 100
    
    # the trailing range works the same
    >>> print DiggPaginator(range(1,1000), 10, body=5, padding=2, margin=2, page=98)
    1 2 ... 96 97 98 99 100
    >>> print DiggPaginator(range(1,1000), 10, body=6, padding=2, margin=2, page=97)
    1 2 ... 95 96 97 98 99 100
    >>> print DiggPaginator(range(1,1000), 10, body=5, padding=1, margin=2, page=95)
    1 2 ... 94 95 96 97 98 99 100
    >>> print DiggPaginator(range(1,1000), 10, body=5, padding=2, margin=2, page=94)
    1 2 ... 92 93 94 95 96 ... 99 100
    >>> print DiggPaginator(range(1,1000), 10, body=5, padding=1, margin=2, page=94)
    1 2 ... 92 93 94 95 96 ... 99 100
    
    # all three ranges may be combined as well
    >>> print DiggPaginator(range(1,151), 10, body=6, padding=2, page=7)
    1 2 3 4 5 6 7 8 9 ... 14 15
    >>> print DiggPaginator(range(1,151), 10, body=6, padding=2, page=8)
    1 2 3 4 5 6 7 8 9 10 11 12 13 14 15
    >>> print DiggPaginator(range(1,151), 10, body=6, padding=1, page=8)
    1 2 3 4 5 6 7 8 9 ... 14 15
    
    # no leading or trailing ranges might be required if there are only
    # a very small number of pages
    >>> print DiggPaginator(range(1,80), 10, body=10, page=1)
    1 2 3 4 5 6 7 8
    >>> print DiggPaginator(range(1,80), 10, body=10, page=8)
    1 2 3 4 5 6 7 8
    >>> print DiggPaginator(range(1,12), 10, body=5, page=1)
    1 2
    
    # padding: default value
    >>> DiggPaginator(range(1,1000), 10, body=10).padding
    4

    # padding: automatic reduction
    >>> DiggPaginator(range(1,1000), 10, body=5).padding
    2
    >>> DiggPaginator(range(1,1000), 10, body=6).padding
    2

    # padding: sanity check
    >>> DiggPaginator(range(1,1000), 10, body=5, padding=3)
    Traceback (most recent call last):
    ValueError: padding too large for body (max 2)
    """
    def __init__(self, *args, **kwargs):
        self.body = kwargs.pop('body', 10)
        self.tail = kwargs.pop('tail', 2)
        self.margin = kwargs.pop('margin', 4)  # todo: make default relative to body?
        # validate padding value
        max_padding = int(math.ceil(self.body/2.0)-1)
        self.padding = kwargs.pop('padding', min(4, max_padding))
        if self.padding > max_padding:
            raise ValueError('padding too large for body (max %d)'%max_padding)
        super(DiggPaginator, self).__init__(*args, **kwargs)
        
    def update_attrs(self):
        super(DiggPaginator, self).update_attrs()
        # easier access
        page, pages, body, tail, padding, margin = \
            self.page, self.pages, self.body, self.tail, self.padding,\
            self.margin

        # put active page in middle of main range
        main_range = map(int, [
            math.floor(page-body/2.0)+1,  # +1 = shift odd body to right
            math.floor(page+body/2.0)])
        # adjust bounds
        if main_range[0] < 1:
            main_range = map(abs(main_range[0]-1).__add__, main_range)
        if main_range[1] > pages:
            main_range = map((pages-main_range[1]).__add__, main_range)
            
        # Determine leading and trailing ranges; if possible and appropriate,
        # combine them with the main range, in which case the resulting main
        # block might end up considerable larger than requested. While we
        # can't guarantee the exact size in those cases, we can at least try
        # to come as close as possible: we can reduce the other boundary to
        # max padding, instead of using half the body size, which would
        # otherwise be the case. If the padding is large enough, this will
        # of course have no effect.
        # Example:
        #     total pages=100, page=4, body=5, (default padding=2)
        #     1 2 3 [4] 5 6 ... 99 100
        #     total pages=100, page=4, body=5, padding=1
        #     1 2 3 [4] 5 ... 99 100
        # If it were not for this adjustment, both cases would result in the
        # first output, regardless of the padding value.
        if main_range[0] <= tail+margin:
            leading = []
            main_range = [1, max(body, min(page+padding, main_range[1]))]
            main_range[0] = 1
        else:
            leading = range(1, tail+1)
        # basically same for trailing range...
        if main_range[1] >= pages-(tail+margin)+1:
            trailing = []
            if not leading:
                # ... but handle the special case of neither leading nor
                # trailing ranges; otherwise, we would now modify the main
                # range low bound, which we just set in the previous section,
                # again.
                main_range = [1, pages]
            else:
                main_range = [min(pages-body+1, max(page-padding, main_range[0])), pages]
        else:
            trailing = range(pages-tail+1, pages+1)
            
        # finally, normalize values that are out of bound; this basically fixes
        # all the things the above code screwed up in the simple case of few
        # enough pages where one range would suffice.
        main_range = [max(main_range[0], 1), min(main_range[1], pages)]
            
        # set attributes
        self.main_range = range(main_range[0], main_range[1]+1)
        self.leading_range = leading
        self.trailing_range = trailing
        self.page_range = reduce(lambda x, y: x+((x and y) and [False])+y,
            [self.leading_range, self.main_range, self.trailing_range])
        
    def __str__(self):
        return " ... ".join(filter(None, [
                            " ".join(map(str, self.leading_range)),
                            " ".join(map(str, self.main_range)),
                            " ".join(map(str, self.trailing_range))]))

if __name__ == "__main__":
    import doctest
    doctest.testmod()