# Copyright (C) 2010-2016 GRNET S.A.
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
from collections import OrderedDict

from django.core.urlresolvers import reverse
from django.utils.html import escape

from synnefo.db import transaction
from synnefo.db.models import IPAddress, IPAddressHistory
from astakos.im.models import AstakosUser, Project

from synnefo_admin.admin.actions import (has_permission_or_403,
                                         get_allowed_actions,
                                         get_permitted_actions,)
from synnefo_admin.admin.resources.ips.utils import get_ip_or_404
from synnefo_admin.admin.resources.users.utils import get_user_or_404
from synnefo_admin.admin.tables import AdminJSONView
from synnefo_admin.admin.associations import (
    UserAssociation, QuotaAssociation, VMAssociation, VolumeAssociation,
    NetworkAssociation, NicAssociation, IPAssociation, IPLogAssociation,
    ProjectAssociation, SimpleVMAssociation, SimpleNetworkAssociation,
    SimpleNicAssociation)

from .utils import (get_contact_email, get_contact_name, get_user_details_href,
                    get_ip_or_404, get_network_details_href,
                    get_vm_details_href)
from .actions import cached_actions
from .filters import IPFilterSet


templates = {
    'list': 'admin/ip_list.html',
    'details': 'admin/ip_details.html',
}


class IPJSONView(AdminJSONView):
    model = IPAddress
    fields = ('pk', 'userid', 'address', 'floating_ip', 'created',)
    filters = IPFilterSet

    def format_data_row(self, row):
        row = list(row)
        row[4] = row[4].strftime("%Y-%m-%d %H:%M")
        return row

    def get_extra_data(self, qs):
        # FIXME: The `contact_name`, `contact_email` fields will cripple our db
        if self.form.cleaned_data['iDisplayLength'] < 0:
            qs = qs.only('pk', 'address', 'floating_ip', 'created', 'userid',)
        return [self.get_extra_data_row(row) for row in qs]

    def get_extra_data_row(self, inst):
        if self.dt_data['iDisplayLength'] < 0:
            extra_dict = {}
        else:
            extra_dict = OrderedDict()

        extra_dict['allowed_actions'] = {
            'display_name': "",
            'value': get_allowed_actions(cached_actions, inst,
                                         self.request.user),
            'visible': False,
        }
        extra_dict['id'] = {
            'display_name': "ID",
            'value': inst.pk,
            'visible': False,
        }
        extra_dict['item_name'] = {
            'display_name': "Name",
            'value': inst.address,
            'visible': False,
        }
        extra_dict['details_url'] = {
            'display_name': "Details",
            'value': reverse('admin-details', args=['ip', inst.pk]),
            'visible': True,
        }
        extra_dict['contact_id'] = {
            'display_name': "Contact ID",
            'value': inst.userid,
            'visible': False,
        }
        extra_dict['contact_email'] = {
            'display_name': "Contact email",
            'value': escape(get_contact_email(inst)),
            'visible': False,
        }
        extra_dict['contact_name'] = {
            'display_name': "Contact name",
            'value': escape(get_contact_name(inst)),
            'visible': False,
        }

        if self.form.cleaned_data['iDisplayLength'] < 0:
            extra_dict['minimal'] = {
                'display_name': "No summary available",
                'value': "Have you per chance pressed 'Select All'?",
                'visible': True,
            }
        else:
            extra_dict.update(self.add_verbose_data(inst))

        return extra_dict

    def add_verbose_data(self, inst):
        extra_dict = OrderedDict()
        extra_dict['user_info'] = {
            'display_name': "Owner",
            'value': get_user_details_href(inst),
            'visible': True,
        }
        extra_dict['vm_info'] = {
            'display_name': "VM",
            'value': get_vm_details_href(inst),
            'visible': True,
        }
        extra_dict['network_info'] = {
            'display_name': "Network info",
            'value': get_network_details_href(inst),
            'visible': True,
        }
        extra_dict['updated'] = {
            'display_name': "Update date",
            'value': inst.updated.strftime("%Y-%m-%d %H:%M"),
            'visible': True,
        }
        extra_dict['in_use'] = {
            'display_name': "Currently in Use",
            'value': inst.in_use(),
            'visible': True,
        }

        return extra_dict


JSON_CLASS = IPJSONView


@transaction.commit_on_success
@has_permission_or_403(cached_actions)
def do_action(request, op, id, data):
    """Apply the requested action on the specified ip."""
    if op == "contact":
        user = get_user_or_404(id)
    else:
        ip = get_ip_or_404(id, for_update=True)
    actions = get_permitted_actions(cached_actions, request.user)

    if op == 'contact':
        actions[op].apply(user, request)
    else:
        actions[op].apply(ip)


def catalog(request):
    """List view for Cyclades ips."""
    context = {}
    context['action_dict'] = get_permitted_actions(cached_actions,
                                                   request.user)
    context['filter_dict'] = IPFilterSet().filters.values()
    context['columns'] = ["ID", "Owner UUID", "Address", "Floating",
                          "Creation date", ""]
    context['item_type'] = 'ip'

    return context


def details(request, query):
    """Details view for Astakos users."""
    ip = get_ip_or_404(query)
    associations = []

    vm_list = [ip.nic.machine] if ip.in_use() else []
    associations.append(SimpleVMAssociation(request, vm_list,))

    network_list = [ip.nic.network] if ip.in_use() else []
    associations.append(SimpleNetworkAssociation(request, network_list,))

    nic_list = [ip.nic] if ip.in_use() else []
    associations.append(SimpleNicAssociation(request, nic_list,))

    user_list = AstakosUser.objects.filter(uuid=ip.userid)
    associations.append(UserAssociation(request, user_list,))

    project_list = Project.objects.filter(uuid=ip.project)
    associations.append(ProjectAssociation(request, project_list,))

    ip_log_list = IPAddressHistory.objects.filter(address=ip.address)
    associations.append(IPLogAssociation(request, ip_log_list))

    context = {
        'main_item': ip,
        'main_type': 'ip',
        'action_dict': get_permitted_actions(cached_actions, request.user),
        'associations_list': associations,
    }

    return context
