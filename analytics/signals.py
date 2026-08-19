"""
Django signal handlers, connected from ``AnalyticsConfig.ready()``.

Signals rather than middleware or view edits, because they let this app observe
authentication without any other app importing from it. Removing the app
removes these handlers and nothing else changes.

A note on this project specifically: it has no public login or signup — the
only account is the site owner's admin superuser, and ``/admin/`` is on the
collection exclusion list. So ``user_logged_in`` fires rarely and
``user_login_failed`` is, in practice, a report of people attempting to break
into the admin. That is exactly the signal worth keeping.
"""
from __future__ import annotations

import logging

from django.contrib.auth.signals import (
    user_logged_in,
    user_logged_out,
    user_login_failed,
)
from django.dispatch import receiver

from . import security
from .events import track_event, visitor_id_for
from .models import Visitor

logger = logging.getLogger(__name__)


@receiver(user_logged_in, dispatch_uid='analytics_user_logged_in')
def stitch_visitor_to_user(sender, request, user, **kwargs) -> None:
    """
    Attach the current visitor to the account that just authenticated.

    This is the one moment where an anonymous identifier and a real account are
    both in hand, so it is the only chance to connect the browsing that led up
    to a login with the account that resulted from it.
    """
    if request is None:
        return
    try:
        Visitor.objects.filter(visitor_id=visitor_id_for(request)).update(user=user)
        track_event(request, 'login', props={'method': 'session'})
    except Exception:
        # Analytics must never be able to break a login.
        logger.exception('Could not stitch visitor to user on login')


@receiver(user_logged_out, dispatch_uid='analytics_user_logged_out')
def record_logout(sender, request, user, **kwargs) -> None:
    if request is None:
        return
    try:
        track_event(request, 'logout')
    except Exception:
        logger.exception('Could not record logout event')


@receiver(user_login_failed, dispatch_uid='analytics_user_login_failed')
def record_failed_login(sender, credentials, request=None, **kwargs) -> None:
    """
    Log a rejected credential attempt.

    ``credentials`` is already masked by Django for anything password-shaped,
    so only the username survives, which is the part worth recording: a spray
    across many usernames reads differently from repeated attempts on one.
    """
    try:
        security.record_failed_login(request, (credentials or {}).get('username', ''))
    except Exception:
        logger.exception('Could not record failed login')
