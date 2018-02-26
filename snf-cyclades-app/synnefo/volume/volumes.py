# Copyright (C) 2010-2016 GRNET S.A. and individual contributors
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

from django.conf import settings
from snf_django.lib.api import faults
from synnefo.db.models import Volume, VolumeMetadata, VirtualMachine
from synnefo.volume import util
from synnefo.logic import server_attachments, utils, commands
from synnefo.plankton.backend import OBJECT_AVAILABLE
from synnefo import quotas
from synnefo.api.util import get_random_helper_vm

log = logging.getLogger(__name__)


def get_volume(volume_id):
    """Simple function to get and lock a Volume."""
    return Volume.objects.select_for_update().get(id=volume_id, deleted=False)


def get_vm(vm_id):
    """Simple function to get and lock a Virtual Machine."""
    vms = VirtualMachine.objects.select_for_update()
    try:
        return vms.get(id=vm_id, deleted=False)
    except VirtualMachine.DoesNotExist:
        raise faults.BadRequest("Virtual machine '%s' does not exist" % vm_id)


def create(user_id, size, server=None, name=None, description=None,
           source_volume_id=None, source_snapshot_id=None,
           source_image_id=None, volume_type_id=None, metadata=None,
           project_id=None, shared_to_project=False):
    """Create a new volume and optionally attach it to a server.

    This function serves as the main entry-point for volume creation. It gets
    the necessary data either from the API or from an snf-manage command and
    then feeds that data to the lower-level functions that handle the actual
    creation of the volume and the server attachments.
    """
    volume_type = None

    # If given a server id, assert that it exists and that it belongs to the
    # user.
    if server:
        volume_type = server.flavor.volume_type
        # If the server's volume type conflicts with the provided volume type,
        # raise an exception.
        if volume_type_id and \
           volume_type.id != util.normalize_volume_type_id(volume_type_id):
            raise faults.BadRequest("Cannot create a volume with type '%s' to"
                                    " a server with volume type '%s'."
                                    % (volume_type_id, volume_type.id))

    # If the user has not provided a valid volume type, raise an exception.
    if volume_type is None:
        volume_type = util.get_volume_type(volume_type_id,
                                           include_deleted=False,
                                           exception=faults.BadRequest)

    # We cannot create a non-detachable volume without a server.
    if server is None:
        util.assert_detachable_volume_type(volume_type)

    volume = create_common(user_id, size, name=name,
                           description=description,
                           source_image_id=source_image_id,
                           source_snapshot_id=source_snapshot_id,
                           source_volume_id=source_volume_id,
                           volume_type=volume_type, metadata={},
                           project_id=project_id,
                           shared_to_project=shared_to_project)

    if server is not None:
        server_attachments.attach_volume(server, volume)
    else:
        quotas.issue_and_accept_commission(volume, action="BUILD")
        # If the volume has been created in the DB, consider it available.
        volume.status = "AVAILABLE"
        volume.save()

    return volume


def create_common(user_id, size, name=None, description=None,
                  source_volume_id=None, source_snapshot_id=None,
                  source_image_id=None, volume_type=None, metadata=None,
                  project_id=None, shared_to_project=False):
    """Common tasks and checks for the creation of a new volume.

    This function processes the necessary arguments in order to call the
    `_create_volume` function, which creates the volume in the DB.

    The main duty of `create_common` is to handle the metadata creation of the
    volume and to update the quota of the user.
    """
    # Assert that not more than one source are used
    sources = filter(lambda x: x is not None,
                     [source_volume_id, source_snapshot_id, source_image_id])
    if len(sources) > 1:
        raise faults.BadRequest("Volume can not have more than one source!")

    if source_volume_id is not None:
        source_type = "volume"
        source_uuid = source_volume_id
    elif source_snapshot_id is not None:
        source_type = "snapshot"
        source_uuid = source_snapshot_id
    elif source_image_id is not None:
        source_type = "image"
        source_uuid = source_image_id
    else:
        source_type = "blank"
        source_uuid = None

    if project_id is None:
        project_id = user_id

    if metadata is not None and \
       len(metadata) > settings.CYCLADES_VOLUME_MAX_METADATA:
        raise faults.BadRequest("Volumes cannot have more than %s metadata "
                                "items" %
                                settings.CYCLADES_VOLUME_MAX_METADATA)

    volume = _create_volume(user_id, project_id, size, source_type,
                            source_uuid, volume_type=volume_type,
                            name=name, description=description, index=None,
                            shared_to_project=shared_to_project)

    if metadata is not None:
        for meta_key, meta_val in metadata.items():
            utils.check_name_length(meta_key, VolumeMetadata.KEY_LENGTH,
                                    "Metadata key is too long")
            utils.check_name_length(meta_val, VolumeMetadata.VALUE_LENGTH,
                                    "Metadata value is too long")
            volume.metadata.create(key=meta_key, value=meta_val)

    return volume


def _create_volume(user_id, project, size, source_type, source_uuid,
                   volume_type, name=None, description=None, index=None,
                   delete_on_termination=True, shared_to_project=False):
    """Create the volume in the DB.

    This function can be called from two different places:
    1) During server creation, when creating the volumes of a new server
    2) During volume creation.
    """
    utils.check_name_length(name, Volume.NAME_LENGTH,
                            "Volume name is too long")
    utils.check_name_length(description, Volume.DESCRIPTION_LENGTH,
                            "Volume description is too long")
    validate_volume_termination(volume_type, delete_on_termination)

    if size is not None:
        try:
            size = int(size)
        except (TypeError, ValueError):
            raise faults.BadRequest("Volume size must be a positive integer")
        if size < 1:
            raise faults.BadRequest("Volume size must be a positive integer")
        if size > settings.CYCLADES_VOLUME_MAX_SIZE:
            raise faults.BadRequest("Maximum volume size is %sGB" %
                                    settings.CYCLADES_VOLUME_MAX_SIZE)

    # Only ext_ disk template supports cloning from another source. Otherwise
    # it must be the root volume so that 'snf-image' fill the volume
    can_have_source = (index == 0 or
                       volume_type.provider in settings.GANETI_CLONE_PROVIDERS)
    if not can_have_source and source_type != "blank":
        msg = ("Cannot specify a 'source' attribute for volume type '%s' with"
               " disk template '%s'" %
               (volume_type.id, volume_type.disk_template))
        raise faults.BadRequest(msg)

    source_version = None
    origin_size = None
    # TODO: Check Volume/Snapshot Status
    if source_type == "snapshot":
        source_snapshot = util.get_snapshot(user_id, source_uuid,
                                            exception=faults.BadRequest)
        snap_status = source_snapshot.get("status", "").upper()
        if snap_status != OBJECT_AVAILABLE:
            raise faults.BadRequest("Cannot create volume from snapshot, while"
                                    " snapshot is in '%s' status" %
                                    snap_status)
        source = Volume.prefix_source(source_uuid,
                                      source_type="snapshot")
        if size is None:
            raise faults.BadRequest("Volume size is required")
        elif (size << 30) < int(source_snapshot["size"]):
            raise faults.BadRequest("Volume size '%s' is smaller than"
                                    " snapshot's size '%s'"
                                    % (size << 30, source_snapshot["size"]))
        source_version = source_snapshot["version"]
        origin = source_snapshot["mapfile"]
        origin_size = source_snapshot["size"]
    elif source_type == "image":
        source_image = util.get_image(user_id, source_uuid,
                                      exception=faults.BadRequest)
        img_status = source_image.get("status", "").upper()
        if img_status != OBJECT_AVAILABLE:
            raise faults.BadRequest("Cannot create volume from image, while"
                                    " image is in '%s' status" % img_status)
        if size is None:
            raise faults.BadRequest("Volume size is required")
        elif (size << 30) < int(source_image["size"]):
            raise faults.BadRequest("Volume size '%s' is smaller than"
                                    " image's size '%s'"
                                    % (size << 30, source_image["size"]))
        source = Volume.prefix_source(source_uuid, source_type="image")
        source_version = source_image["version"]
        origin = source_image["mapfile"]
        origin_size = source_image["size"]
    elif source_type == "blank":
        if size is None:
            raise faults.BadRequest("Volume size is required")
        source = origin = None
    elif source_type == "volume":
        # Currently, Archipelago does not support cloning a volume
        raise faults.BadRequest("Cloning a volume is not supported")
        # source_volume = util.get_volume(user_id, source_uuid,
        #                                 for_update=True, non_deleted=True,
        #                                 exception=faults.BadRequest)
        # if source_volume.status != "IN_USE":
        #     raise faults.BadRequest("Cannot clone volume while it is in '%s'"
        #                             " status" % source_volume.status)
        # # If no size is specified, use the size of the volume
        # if size is None:
        #     size = source_volume.size
        # elif size < source_volume.size:
        #     raise faults.BadRequest("Volume size cannot be smaller than the"
        #                             " source volume")
        # source = Volume.prefix_source(source_uuid, source_type="volume")
        # origin = source_volume.backend_volume_uuid
    else:
        raise faults.BadRequest("Unknown source type")

    volume = Volume.objects.create(userid=user_id,
                                   project=project,
                                   index=index,
                                   shared_to_project=shared_to_project,
                                   size=size,
                                   volume_type=volume_type,
                                   name=name,
                                   description=description,
                                   delete_on_termination=delete_on_termination,
                                   source=source,
                                   source_version=source_version,
                                   origin=origin,
                                   status="CREATING")

    # Store the size of the origin in the volume object but not in the DB.
    # We will have to change this in order to support detachable volumes.
    volume.origin_size = origin_size

    return volume


def attach(server, volume_id):
    """Attach a volume to a server."""
    volume = get_volume(volume_id)
    server_attachments.attach_volume(server, volume)

    return volume


def delete_detached_volume(volume):
    """Delete a detached volume.

    There is actually no way (that involves Ganeti) to delete a detached
    volume. Instead, we need to attach it to a helper VM and then delete it.
    The purpose of this function is to do the first step; find an available
    helper VM and attach the volume to it. In order to differentiate this
    action from a common attach action, we set the volume status as DELETING.
    Then, the dispatcher will handle the deletion of the volume.
    """
    # Fetch a random helper VM from an online and undrained Ganeti backend
    server = get_random_helper_vm(for_update=True)
    if server is None:
        raise faults.ItemNotFound("Cannot find an available helper server")
    log.debug("Using helper server %s for the removal of volume %s",
              server, volume)

    # Attach the volume to the helper server, in order to delete it
    # internally later.
    server_attachments.attach_volume(server, volume)
    volume.status = "DELETING"
    volume.save()

    return volume


def delete_volume_from_helper(volume, helper_vm):
    """Delete a volume that has been attached to a helper VM.

    This special-purpose function should be called only by the dispatcher, when
    we are notified that a detached volume has been attached to a helper VM.
    """
    if not helper_vm.helper:
        raise faults.BadRequest("Server %s is not a helper server" %
                                helper_vm.backend_vm_id)
    log.debug("Attempting to delete volume '%s' from helper server '%s'",
              volume.id, helper_vm.id)
    server_attachments.delete_volume(helper_vm, volume)
    log.info("Deleting volume '%s' from server '%s', job: %s",
             volume.id, helper_vm.id, volume.backendjobid)


def delete(volume):
    """Delete a Volume.

    The canonical way of deleting a volume is to send a command to Ganeti to
    remove the volume from a specific server. There are two cases however when
    a volume may not be attached to a server:

    * Case 1: The volume has been created only in DB and was never attached to
    a server. In this case, we can simply mark the volume as deleted without
    using Ganeti to do so.
    * Case 2: The volume has been detached from a VM. This means that there are
    still data in the storage backend. Thus, in order to delete the volume
    safely, we must attach it to a helper VM, thereby handing the delete action
    to the dispatcher.
    """
    server_id = volume.machine_id
    if server_id is not None:
        server = get_vm(server_id)
        server_attachments.delete_volume(server, volume)
        log.info("Deleting volume '%s' from server '%s', job: %s",
                 volume.id, server_id, volume.backendjobid)
    elif volume.backendjobid is None:
        # Case 1: Uninitialized volume
        if volume.status not in ("AVAILABLE", "ERROR"):
            raise faults.BadRequest("Volume is in invalid state: %s" %
                                    volume.status)
        log.debug("Attempting to delete uninitialized volume %s.", volume)
        util.mark_volume_as_deleted(volume, immediate=True)
        quotas.issue_and_accept_commission(volume, action="DESTROY")
        log.info("Deleting uninitialized volume '%s'", volume.id)
    else:
        # Case 2: Detached volume
        log.debug("Attempting to delete detached volume %s", volume)
        delete_detached_volume(volume)
        log.info("Deleting volume '%s' from helper server '%s', job: %s",
                 volume.id, volume.machine.id, volume.backendjobid)

    return volume


def detach(volume_id):
    """Detach a Volume"""
    volume = get_volume(volume_id)
    server_id = volume.machine_id
    if server_id is not None:
        server = get_vm(server_id)
        server_attachments.detach_volume(server, volume)
        log.info("Detaching volume '%s' from server '%s', job: %s",
                 volume.id, server_id, volume.backendjobid)
    else:
        raise faults.BadRequest("Volume is already detached")
    return volume


def update(volume, name=None, description=None, delete_on_termination=None):
    if name is not None:
        utils.check_name_length(name, Volume.NAME_LENGTH,
                                "Volume name is too long")
        volume.name = name
    if description is not None:
        utils.check_name_length(description, Volume.DESCRIPTION_LENGTH,
                                "Volume description is too long")
        volume.description = description
    if delete_on_termination is not None:
        validate_volume_termination(volume.volume_type, delete_on_termination)
        volume.delete_on_termination = delete_on_termination

    volume.save()
    return volume


def reassign_volume(volume, project, shared_to_project):
    if volume.index == 0:
        raise faults.Conflict("Cannot reassign: %s is a system volume" %
                              volume.id)

    server = volume.machine
    if server is not None:
        commands.validate_server_action(server, "REASSIGN")

    if volume.project == project:
        if volume.shared_to_project != shared_to_project:
            log.info("%s volume %s to project %s",
                "Sharing" if shared_to_project else "Unsharing",
                volume, project)
            volume.shared_to_project = shared_to_project
            volume.save()
    else:
        action_fields = {"to_project": project, "from_project": volume.project}
        log.info("Reassigning volume %s from project %s to %s, shared: %s",
                volume, volume.project, project, shared_to_project)
        volume.project = project
        volume.shared_to_project = shared_to_project
        volume.save()
        quotas.issue_and_accept_commission(volume, action="REASSIGN",
                                           action_fields=action_fields)
    return volume


def validate_volume_termination(volume_type, delete_on_termination):
    """Validate volume's termination mode based on volume's type.

    NOTE: Currently, detached volumes are not supported, so all volumes
    must be terminated upon instance deletion.

    """
    if delete_on_termination is False:
        # Only ext_* volumes can be preserved
        if volume_type.template != "ext":
            raise faults.BadRequest("Volumes of '%s' disk template cannot have"
                                    " 'delete_on_termination' attribute set"
                                    " to 'False'" % volume_type.disk_template)
        # But currently all volumes must be terminated
        raise faults.NotImplemented("Volumes with the 'delete_on_termination'"
                                    " attribute set to False are not"
                                    " supported")
