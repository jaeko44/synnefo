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

from optparse import make_option
import re

from django.db import IntegrityError
from snf_django.management.commands import SynnefoCommand, CommandError

from synnefo.management import pprint, common
from synnefo.db.models import VolumeType

HELP_MSG = """Create a new Volume Type."""


class Command(SynnefoCommand):
    help = HELP_MSG

    option_list = SynnefoCommand.option_list + (
        make_option(
            "--name",
            dest="name",
            default=None,
            help="The display name of the volume type."),
        make_option(
            "--disk-template",
            dest="disk_template",
            default=None,
            help="The disk template of the volume type"),
        make_option(
            "--specs",
            dest="specs",
            help="Comma separated spec key, value pairs "
                 "Example --specs key1=value1,key2=value2")
    )

    @common.convert_api_faults
    def handle(self, *args, **options):
        if args:
            raise CommandError("Command doesn't accept any arguments")

        name = options.get("name")
        disk_template = options.get("disk_template")

        if name is None:
            raise CommandError("Please specify the name of the volume type.")
        if disk_template is None:
            raise CommandError("Please specify the disk template of the volume"
                               " type.")
        if len(name) > VolumeType.NAME_LENGTH:
            raise CommandError("Name of the volume type can't be more than %s"
                               " characters." % VolumeType.NAME_LENGTH)
        if len(disk_template) > VolumeType.DISK_TEMPLATE_LENGTH:
            raise CommandError("Disk template of the volume type can't be more"
                               " than %s characters." %
                               VolumeType.DISK_TEMPLATE_LENGTH)
        try:
            vtype = VolumeType.objects.create(name=name,
                                              disk_template=disk_template)
        except IntegrityError as e:
            raise CommandError("Failed to create volume type: %s" % e)

        specs = options.get('specs')
        if specs:
            spec_regex = re.compile(r'^(?P<key>.+?)=(?P<value>.+)$')
            specs = specs.split(',')
            for spec in specs:
                match = spec_regex.match(spec)
                if match is None:
                    raise CommandError("Incorrect spec format. Expected: "
                                       " <key>=<value> ,found: \'%s\' " % spec)
                k, v = match.group('key'), match.group('value')
                spec = vtype.specs.create(key=k)
                spec.value = v
                spec.save()
        self.stdout.write("Created volume Type '%s' in DB:\n" % vtype.id)

        pprint.pprint_volume_type(vtype, stdout=self.stdout)
