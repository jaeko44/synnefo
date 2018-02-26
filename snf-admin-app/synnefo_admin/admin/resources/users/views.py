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

from synnefo.db.models import (VirtualMachine, Network, IPAddressHistory,
                               Volume, NetworkInterface, IPAddress)
from astakos.im.models import AstakosUser, Project
from astakos.im import user_logic as users
from astakos.im import transaction

from django.db.models import Q

from synnefo_admin import admin_settings
from synnefo_admin.admin.actions import (has_permission_or_403,
                                         get_allowed_actions,
                                         get_permitted_actions,)
from synnefo_admin.admin.tables import AdminJSONView
from synnefo_admin.admin.associations import (
    UserAssociation, QuotaAssociation, VMAssociation, VolumeAssociation,
    NetworkAssociation, NicAssociation, IPAssociation, IPLogAssociation,
    ProjectAssociation)

from .utils import (get_user_or_404, get_quotas, get_user_groups,
                    get_enabled_providers, get_suspended_vms)
from .actions import cached_actions
from .filters import UserFilterSet

templates = {
    'list': 'admin/user_list.html',
    'details': 'admin/user_details.html',
}


class UserJSONView(AdminJSONView):
    model = AstakosUser
    fields = ('id', 'email', 'first_name', 'last_name', 'is_active',
              'is_rejected', 'moderated', 'email_verified')
    filters = UserFilterSet

    def get_extra_data(self, qs):
        if self.form.cleaned_data['iDisplayLength'] < 0:
            qs = qs.only('email', 'first_name', 'last_name', 'is_active',
                         'is_rejected', 'moderated', 'email_verified', 'uuid')
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
            'display_name': "UUID",
            'value': inst.uuid,
            'visible': True,
        }
        extra_dict['item_name'] = {
            'display_name': "Name",
            'value': escape(inst.realname),
            'visible': False,
        }
        extra_dict['details_url'] = {
            'display_name': "Details",
            'value': reverse('admin-details', args=['user', inst.uuid]),
            'visible': True,
        }
        extra_dict['contact_id'] = {
            'display_name': "Contact ID",
            'value': inst.uuid,
            'visible': False,
        }
        extra_dict['contact_email'] = {
            'display_name': "Contact email",
            'value': escape(inst.email),
            'visible': False,
        }
        extra_dict['contact_name'] = {
            'display_name': "Contact name",
            'value': escape(inst.realname),
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

        if inst.email_change_is_pending():
            extra_dict['pending_email'] = {
                'display_name': "E-mail pending verification",
                'value': inst.emailchanges.all()[0].new_email_address,
                'visible': True,
            }

        extra_dict['status'] = {
            'display_name': "Status",
            'value': inst.status_display,
            'visible': True,
        }
        extra_dict['groups'] = {
            'display_name': "Groups",
            'value': escape(get_user_groups(inst)),
            'visible': True,
        }
        extra_dict['enabled_providers'] = {
            'display_name': "Enabled providers",
            'value': get_enabled_providers(inst),
            'visible': True,
        }

        if (users.validate_user_action(inst, "ACCEPT") and
                inst.verification_code):
            extra_dict['activation_url'] = {
                'display_name': "Activation URL",
                'value': inst.get_activation_url(),
                'visible': True,
            }

        if inst.accepted_policy:
            extra_dict['moderation_policy'] = {
                'display_name': "Moderation policy",
                'value': inst.accepted_policy,
                'visible': True,
            }

        suspended_vms = get_suspended_vms(inst)

        extra_dict['suspended_vms'] = {
            'display_name': "Suspended VMs",
            'value': suspended_vms,
            'visible': True,
        }

        return extra_dict


JSON_CLASS = UserJSONView


@has_permission_or_403(cached_actions)
@transaction.commit_on_success
def do_action(request, op, id, data):
    """Apply the requested action on the specified user."""
    user = get_user_or_404(id, for_update=True)
    actions = get_permitted_actions(cached_actions, request.user)

    if op == 'reject':
        actions[op].apply(user, 'Rejected by the admin')
    elif op == 'contact':
        actions[op].apply(user, request)
    elif op == 'modify_email':
        if isinstance(data, dict):
            actions[op].apply(user, data.get('new_email'))
    else:
        actions[op].apply(user)


def catalog(request):
    """List view for Astakos users."""

    context = {}
    context['action_dict'] = get_permitted_actions(cached_actions,
                                                   request.user)
    context['filter_dict'] = UserFilterSet().filters.values()
    context['columns'] = ["ID", "E-mail", "First Name", "Last Name", "Active",
                          "Rejected", "Moderated", "Verified", ""]
    context['item_type'] = 'user'

    return context


def details(request, query):
    """Details view for Astakos users."""
    user = get_user_or_404(query)
    associations = []
    lim = admin_settings.ADMIN_LIMIT_ASSOCIATED_ITEMS_PER_CATEGORY

    quota_list = get_quotas(user)
    total = len(quota_list)
    quota_list = quota_list[:lim]
    associations.append(QuotaAssociation(request, quota_list, total=total))

    qor = Q(members=user) | Q(last_application__applicant=user)
    project_list = Project.objects.filter(qor)
    associations.append(ProjectAssociation(request, project_list))

    vm_list = VirtualMachine.objects.filter(userid=user.uuid)
    associations.append(VMAssociation(request, vm_list))

    volume_list = Volume.objects.filter(userid=user.uuid)
    associations.append(VolumeAssociation(request, volume_list))

    qor = Q(public=True, nics__machine__userid=user.uuid) | Q(userid=user.uuid)
    network_list = Network.objects.filter(qor)
    associations.append(NetworkAssociation(request, network_list))

    nic_list = NetworkInterface.objects.filter(userid=user.uuid)
    associations.append(NicAssociation(request, nic_list))

    ip_list = IPAddress.objects.filter(userid=user.uuid)
    associations.append(IPAssociation(request, ip_list))

    vm_ids = VirtualMachine.objects.filter(userid=user.uuid).values('id')
    ip_log_list = IPAddressHistory.objects.filter(user_id=user.uuid)
    associations.append(IPLogAssociation(request, ip_log_list))

    context = {
        'main_item': user,
        'main_type': 'user',
        'action_dict': get_permitted_actions(cached_actions, request.user),
        'associations_list': associations,
    }

    return context
