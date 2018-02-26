# Copyright (C) 2010-2014 GRNET S.A.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import logging
import django_filters

from django.db.models import Q

from astakos.im.models import AstakosUser, Project
from astakos.im import auth_providers

from synnefo_admin.admin.queries_common import (query, model_filter,
                                                get_model_field, process_queries)

from .utils import get_groups

choice2query = {
    ('ACTIVE', ''): Q(is_active=True),
    ('INACTIVE', ''): Q(is_active=False, moderated=True) | Q(is_rejected=True),
    ('PENDING MODERATION', ''): Q(moderated=False, email_verified=True),
    ('PENDING EMAIL VERIFICATION', ''): Q(email_verified=False),
}


auth_providers = [(key, '_') for key in auth_providers.PROVIDERS.iterkeys()]


@model_filter
def filter_user(queryset, queries):
    q = process_queries("user", queries)
    return queryset.filter(q)


@model_filter
def filter_vm(queryset, queries):
    q = process_queries("vm", queries)
    ids = get_model_field("vm", q, 'userid')
    return queryset.filter(uuid__in=ids)


@model_filter
def filter_volume(queryset, queries):
    q = process_queries("volume", queries)
    ids = get_model_field("volume", q, 'userid')
    return queryset.filter(uuid__in=ids)


@model_filter
def filter_network(queryset, queries):
    q = process_queries("network", queries)
    ids = get_model_field("network", q, 'userid')
    return queryset.filter(uuid__in=ids)


@model_filter
def filter_ip(queryset, queries):
    q = process_queries("ip", queries)
    ids = get_model_field("ip", q, 'userid')
    return queryset.filter(uuid__in=ids)


@model_filter
def filter_project(queryset, queries):
    q = process_queries("project", queries)
    member_ids = Project.objects.filter(q).values('members__uuid')
    owner_ids = Project.objects.filter(q).values('owner__uuid')
    qor = Q(uuid__in=member_ids) | Q(uuid__in=owner_ids)
    return queryset.filter(qor)


def filter_has_auth_providers(queryset, choices):
    if not choices:
        return queryset

    q = Q()
    for c in choices:
        q |= Q(auth_providers__module=c)
    return queryset.filter(q).distinct()


def filter_has_not_auth_providers(queryset, choices):
    if not choices:
        return queryset

    q = Q()
    for c in choices:
        q |= Q(auth_providers__module=c)

    # We cannot use `exclude` here as `exclude` does not play nicely with
    # multi-valued fields (see https://code.djangoproject.com/ticket/14645)
    #
    # Instead, we create a subquery to filter all users that actually match the
    # requested providers and then exclude them. Given that the subquery is in
    # the same database, it probably has small overhead.
    user_ids = AstakosUser.objects.filter(q).values('id')
    return queryset.exclude(id__in=user_ids).distinct()


def filter_status(queryset, choices):
    choices = choices or ()
    if len(choices) == len(choice2query.keys()):
        return queryset
    q = Q()
    for c in choices:
        q |= choice2query[(c, '')]
    return queryset.filter(q).distinct()


def filter_group(queryset, choices):
    """Filter by group name for user.

    Since not all users need to be in a group, we always process the request
    given even if all choices are selected.
    """
    choices = choices or ()
    q = Q()
    for c in choices:
        q |= Q(groups__name__exact=c)
    return queryset.filter(q).distinct()


class UserFilterSet(django_filters.FilterSet):

    """A collection of filters for users.

    This filter collection is based on django-filter's FilterSet.
    """

    user = django_filters.CharFilter(label='User', action=filter_user)
    vm = django_filters.CharFilter(label='HAS VM', action=filter_vm)
    vol = django_filters.CharFilter(label='HAS Volume', action=filter_volume)
    net = django_filters.CharFilter(label='HAS Network', action=filter_network)
    ip = django_filters.CharFilter(label='HAS IP', action=filter_ip)
    proj = django_filters.CharFilter(label='IN Project', action=filter_project)
    status = django_filters.MultipleChoiceFilter(
        label='Status', action=filter_status, choices=choice2query.keys())
    groups = django_filters.MultipleChoiceFilter(
        label='Group', action=filter_group, choices=get_groups())
    has_auth_providers = django_filters.MultipleChoiceFilter(
        label='HAS Auth Providers', action=filter_has_auth_providers,
        choices=auth_providers)
    has_not_auth_providers = django_filters.MultipleChoiceFilter(
        label='HAS NOT Auth Providers', action=filter_has_not_auth_providers,
        choices=auth_providers)

    class Meta:
        model = AstakosUser
        fields = ('user', 'status', 'groups', 'has_auth_providers',
                  'has_not_auth_providers', 'vm', 'vol', 'net', 'ip', 'proj')
