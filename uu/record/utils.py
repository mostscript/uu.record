# loose coupling notification:
from zope.event import notify as base_notify

try:
    from plone.app.contentrules.handlers import _status, DuplicateRuleFilter

    def notify(*args, **kwargs):
        """
        Work around https://teamspace.upiq.org/trac/ticket/206, that
        is that content rules are greedily assuming all notified objects
        are contentish.
        """
        _status.rule_filter = DuplicateRuleFilter()
        _status.rule_filter.in_progress = True
        base_notify(*args, **kwargs)
        _status.rule_filter.in_progress = False


except ImportError:
    notify = base_notify


safe_notify = notify

