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
from collections import OrderedDict

from synnefo.db.models import IPAddressHistory

from synnefo_admin.admin.exceptions import AdminHttp404
from synnefo_admin.admin.utils import _filter_public_ip_log
from synnefo_admin.admin.tables import AdminJSONView

from .utils import (get_user_details_href, get_ip_details_href,
                    get_vm_details_href, get_network_details_href,
                    get_user_uuid_from_server,)
from .filters import IPLogFilterSet


templates = {
    'list': 'admin/ip_log_list.html',
}


class IPLogJSONView(AdminJSONView):
    model = IPAddressHistory
    fields = ('address', 'user_id', 'server_id', 'network_id', 'action',
              'action_date', 'action_reason')
    filters = IPLogFilterSet

    # This is a rather hackish method of plugging ourselves after
    # get_queryset()
    def set_object_list(self):
        """Show logs only for public IPs."""
        self.qs = _filter_public_ip_log(self.qs)
        return AdminJSONView.set_object_list(self)

    def get_extra_data_row(self, inst):
        extra_dict = OrderedDict()
        extra_dict['user_info'] = {
            'display_name': "User",
            'value': get_user_details_href(inst),
            'visible': True,
        }
        extra_dict['id'] = {
            'display_name': "ID",
            'value': inst.pk,
            'visible': False,
        }
        extra_dict['ip_info'] = {
            'display_name': "IP",
            'value': get_ip_details_href(inst),
            'visible': True,
        }
        extra_dict['vm_info'] = {
            'display_name': "VM",
            'value': get_vm_details_href(inst),
            'visible': True,
        }
        extra_dict['network_info'] = {
            'display_name': "Network",
            'value': get_network_details_href(inst),
            'visible': True,
        }
        extra_dict['reason'] = {
            'display_name': "Action reason",
            'value': inst.action_reason,
            'visible': True,
        }
        return extra_dict


JSON_CLASS = IPLogJSONView


def catalog(request):
    """List view for Cyclades ip log."""
    context = {}
    context['action_dict'] = None
    context['filter_dict'] = IPLogFilterSet().filters.values()
    context['columns'] = ["Address", "User", "Server ID", "Network ID",
                          "Action", "Date", "Reason", ""]
    context['item_type'] = 'ip_log'

    return context


def details(request, query):
    """Details view for Cyclades ip history."""
    raise AdminHttp404("There are no details for any entry of the IP History")
