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

from synnefo.db.models import IPAddress

from synnefo_admin.admin.queries_common import (process_queries, model_filter,
                                                get_model_field)


@model_filter
def filter_ip(queryset, queries):
    q = process_queries("ip", queries)
    return queryset.filter(q)


@model_filter
def filter_user(queryset, queries):
    q = process_queries("user", queries)
    ids = get_model_field("user", q, 'uuid')
    return queryset.filter(userid__in=ids)


@model_filter
def filter_vm(queryset, queries):
    q = process_queries("vm", queries)
    ids = get_model_field("vm", q, 'id')
    return queryset.filter(nic__machine__id__in=ids)


@model_filter
def filter_network(queryset, queries):
    q = process_queries("network", queries)
    ids = get_model_field("network", q, 'id')
    return queryset.filter(network__id__in=ids)


@model_filter
def filter_project(queryset, queries):
    q = process_queries("project", queries)
    ids = get_model_field("project", q, 'uuid')
    return queryset.filter(project__in=ids)


class IPFilterSet(django_filters.FilterSet):

    """A collection of filters for ips.

    This filter collection is based on django-filter's FilterSet.
    """

    ip = django_filters.CharFilter(label='IP', action=filter_ip)
    user = django_filters.CharFilter(label='OF User', action=filter_user)
    vm = django_filters.CharFilter(label='OF VM', action=filter_vm)
    net = django_filters.CharFilter(label='OF Network', action=filter_network)
    proj = django_filters.CharFilter(label='OF Project', action=filter_project)

    class Meta:
        model = IPAddress
        fields = ('ip', 'floating_ip', 'user', 'vm', 'net', 'proj')
