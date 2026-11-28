"""Template loader for the pages edited on the site with templatesadmin."""

from django.template.loaders import filesystem

# The folder of the templates that templatesadmin edits, as the
# templates name it in their includes.
MANAGED_CONTENT = 'managed_content/'


class ManagedContentLoader(filesystem.Loader):
    """
    Read the managed content templates from disk on each use.

    It comes before the cached loader, which keeps the other templates
    compiled between requests, so that an edit shows at once.
    """

    def get_template_sources(self, template_name):
        """Look in the template folders for managed content names only."""
        if template_name.startswith(MANAGED_CONTENT):
            yield from super().get_template_sources(template_name)
