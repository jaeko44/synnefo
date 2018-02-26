# Copyright (C) 2010-2017 GRNET S.A.
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

#from optparse import make_option

from snf_django.management.commands import ListCommand
from synnefo.db.models import VolumeType
from logging import getLogger
log = getLogger(__name__)

def get_specs(vtype):
    return  ', '.join([str(spec) for spec in vtype.specs.all()])

def get_flavors(vtype):
    return vtype.flavors.filter(deleted=False).count()


def get_volumes(vtype):
    return vtype.volumes.filter(deleted=False).count()


def get_servers(vtype):
    return vtype.servers.filter(deleted=False).count()


class Command(ListCommand):
    help = "List Volume Types"

    option_list = ListCommand.option_list

    object_class = VolumeType
    deleted_field = "deleted"

    FIELDS = {
        "id": ("id", "ID"),
        "name": ("name", "Name"),
        "disk_template": ("disk_template", "Disk template"),
        "flavors": (get_flavors, "Number of flavors using this volume type"),
        "volumes": (get_volumes, "Number of volumes using this volume type"),
        "deleted": ("deleted", "Whether volume type is deleted or not"),
        "specs": (get_specs, "The key-value pair specs of the volume type"),
    }

    fields = ["id", "name", "disk_template", "flavors", "volumes", "deleted", "specs"]
