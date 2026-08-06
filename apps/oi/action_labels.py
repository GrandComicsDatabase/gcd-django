"""Translated labels shared by workflow buttons and their instructions."""

from django.utils.translation import gettext_lazy as _


SUBMIT_CHANGES_FOR_APPROVAL = _('Submit Changes For Approval')
APPROVE = _('Approve')
SEND_BACK_TO_INDEXER = _('Send Back to Indexer')

WORKFLOW_ACTION_LABELS = {
    'submit': SUBMIT_CHANGES_FOR_APPROVAL,
    'approve': APPROVE,
    'disapprove': SEND_BACK_TO_INDEXER,
}
