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

from django.core.exceptions import ObjectDoesNotExist

from astakos.im.models import AstakosUser
from synnefo.db.models import IPAddress, VirtualMachine, Network

from synnefo_admin.admin.utils import create_details_href


def get_ip_details_href(ip_log):
    addr = ip_log.address
    try:
        ip = IPAddress.objects.get(address=addr, network__public=True)
        return create_details_href('ip', addr, ip.id)
    except ObjectDoesNotExist:
        return addr


def get_vm_details_href(ip_log):
    vm = VirtualMachine.objects.get(pk=ip_log.server_id)
    return create_details_href('vm', vm.name, vm.pk)


def get_network_details_href(ip_log):
    network = Network.objects.get(pk=ip_log.network_id)
    return create_details_href('network', network.name, network.pk)


def get_user_details_href(ip_log):
    user = AstakosUser.objects.get(uuid=ip_log.user_id)
    return create_details_href('user', user.realname, user.email, user.uuid)


def get_user_uuid_from_server(server_id):
    vm = VirtualMachine.objects.get(pk=server_id)
    return vm.userid
