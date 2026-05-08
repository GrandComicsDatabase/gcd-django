# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""drf-spectacular helpers for the v2 API."""


def v2_endpoints_only(endpoints):
    """Drop non-``/api/v2/`` endpoints from a spectacular endpoint list.

    Used as a ``PREPROCESSING_HOOKS`` entry on the v2 ``SpectacularAPIView``
    so the v2 schema document only describes v2 paths even though we
    generate from the project urlconf.
    """
    return [
        endpoint
        for endpoint in endpoints
        if endpoint[0].startswith('/api/v2/')
    ]
