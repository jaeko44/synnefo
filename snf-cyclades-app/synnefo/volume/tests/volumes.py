# Copyright (C) 2010-2017 GRNET S.A. and individual contributors
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

import django.test
from django.test.utils import override_settings
from snf_django.utils.testing import (mocked_quotaholder, MurphysLaw)
from synnefo.db import models_factory as mf
from synnefo.db.models import Volume, VirtualMachine
from synnefo.volume import volumes
from synnefo.cyclades_settings import cyclades_services
from synnefo.lib.services import get_service_path
from snf_django.lib.api import faults
from mock import patch
from copy import deepcopy

# Import these functions directly in order to not be overwritten by patch()
from synnefo.volume.volumes import create_common
from synnefo.quotas import handle_resource_commission


class QuotaAssertions(django.test.SimpleTestCase):

    """Helper assertions regarding quotas and commissions."""

    def assertCommissionEqual(self, mqh, expected_commission):
        """Assert that the latest quota commission was the expected one."""
        #_, args, __ = mqh.issue_one_commission.mock_calls[-1]
        _, args, __ = mqh.issue_one_commission.mock_calls[0]
        commission_resources = args[1]
        self.assertEqual(commission_resources, expected_commission)

    def assertNoCommission(self, mqh):
        """Assert that no commission was sent."""
        self.assertEqual(mqh.issue_one_commission.call_count, 0)

    def assertAcceptedSerial(self, mqh, expected_serial):
        """Assert that a serial was accepted."""
        # Find all accepted serials
        self.assertIsNotNone(expected_serial)
        accepted_serials = []
        for _, args, __ in mqh.resolve_commissions.mock_calls:
            accepted_serials += args[0]

        # Check if provided serial is in them
        msg = "Serial '{}' is not in accepted ones {}".format(
            expected_serial.serial, accepted_serials)
        self.assertIn(expected_serial.serial, accepted_serials, msg)

    def assertPendingSerial(self, mqh, expected_serial):
        """Assert that a serial is pending."""
        # Find all pending serials
        self.assertIsNotNone(expected_serial)
        pending_serials = []
        for _, args, __ in mqh.resolve_commissions.mock_calls:
            pending_serials += args[1]

        # Check if provided serial is in them
        msg = "Serial '{}' is not in pending ones {}".format(
            expected_serial.serial, pending_serials)
        self.assertIn(expected_serial.serial, pending_serials, msg)


class VolumesTestCommon(django.test.TestCase):

    """Tests for common tasks regarding volume creation.

    Basically, this test suite covers the main bulk of the actions that take
    place in `create_common`.
    """

    kwargs = {
        "user_id": "test_user",
        "size": 1,
        "name": "Test name",
        "description": "Test description",
    }

    def setUp(self):
        # The volume_type kwarg must be added during the setUp of the test
        # case, else there won't be any database to create this VolumeType to.
        self.kwargs.update(volume_type=mf.VolumeTypeFactory())

    def new_kwargs(self, **custom_kwargs):
        """Construct a dictionary of keyword arguments.

        This dictionary is based on the default kwargs of the test suite and is
        updated by user-provided ones.
        """
        # Deepcopy the common kwargs so that we don't affect the other tests.
        kwargs = deepcopy(self.kwargs)
        # Override or add more kwargs using the user-provided key-values
        kwargs.update(custom_kwargs)

        return kwargs

    def test_many_sources(self):
        """Test that we can't create a volume with more than one sources."""
        source_msg = "Volume can not have more than one source!"
        kwargs = self.new_kwargs(source_volume_id="dummy_volume_id",
                                 source_snapshot_id="dummy_snapshot_id")
        with self.assertRaisesMessage(faults.BadRequest, source_msg):
            volumes.create_common(**kwargs)

    @override_settings(CYCLADES_VOLUME_MAX_METADATA=1)
    @patch("synnefo.db.models.VolumeMetadata.KEY_LENGTH", 4)
    @patch("synnefo.db.models.VolumeMetadata.VALUE_LENGTH", 4)
    def test_metadata(self):
        """Test if volume metadata are set properly."""
        # Fail to add more metadata than allowed
        metadata = {
            "key1": "val1",
            "key2": "val2",
        }
        many_metadata_msg = "Volumes cannot have more than 1 metadata items"
        kwargs = self.new_kwargs(metadata=metadata)
        with self.assertRaisesMessage(faults.BadRequest, many_metadata_msg):
            volumes.create_common(**kwargs)

        # Fail to add too long metadata key
        metadata = {"longkey1": "val1"}
        long_metakey_msg = "Metadata key is too long"
        kwargs = self.new_kwargs(metadata=metadata)
        with self.assertRaisesMessage(faults.BadRequest, long_metakey_msg):
            volumes.create_common(**kwargs)

        # Fail to add too long metadata value
        metadata = {"key1": "longval1"}
        long_metaval_msg = "Metadata value is too long"
        kwargs = self.new_kwargs(metadata=metadata)
        with self.assertRaisesMessage(faults.BadRequest, long_metaval_msg):
            volumes.create_common(**kwargs)

        # Assert that metadata are set properly on successful volume creation
        metadata = {"key1": "val1"}
        kwargs = self.new_kwargs(metadata=metadata)
        vol = volumes.create_common(**kwargs)
        self.assertEqual(vol.metadata.count(), 1)
        created_metadata = vol.metadata.all()[0]
        key = created_metadata.key
        val = created_metadata.value
        self.assertEqual(key, "key1")
        self.assertEqual(val, "val1")

    @patch("synnefo.db.models.Volume.NAME_LENGTH", 4)
    def test_name_length(self):
        """Test if volume name is set properly."""
        long_name_msg = "Volume name is too long"

        # Fail to create volume with too long name.
        kwargs = self.new_kwargs(name="Test long name")
        with self.assertRaisesMessage(faults.BadRequest, long_name_msg):
            volumes.create_common(**kwargs)

        # Check if name was added properly.
        kwargs = self.new_kwargs(name="ok")
        vol = volumes.create_common(**kwargs)
        self.assertEqual(vol.name, "ok")

    @patch("synnefo.db.models.Volume.DESCRIPTION_LENGTH", 4)
    def test_description_length(self):
        """Test if volume description is set properly."""
        # Fail to create volume with too long description.
        long_description_msg = "Volume description is too long"
        kwargs = self.new_kwargs(description="Test long description")
        with self.assertRaisesMessage(faults.BadRequest, long_description_msg):
            volumes.create_common(**kwargs)

        # Check if description was added properly.
        kwargs = self.new_kwargs(description="ok")
        vol = volumes.create_common(**kwargs)
        self.assertEqual(vol.description, "ok")

    @override_settings(CYCLADES_VOLUME_MAX_SIZE=1)
    def test_size(self):
        """Test if volume size is calculated properly."""
        wrong_size_msg = "Volume size must be a positive integer"

        # Fail to create volume with invalid size.
        kwargs = self.new_kwargs(size="notInt")
        with self.assertRaisesMessage(faults.BadRequest, wrong_size_msg):
            volumes.create_common(**kwargs)

        # Fail to create volume with negative size.
        kwargs = self.new_kwargs(size="-1")
        with self.assertRaisesMessage(faults.BadRequest, wrong_size_msg):
            volumes.create_common(**kwargs)

        # Fail to create volume with too big size.
        large_size_msg = "Maximum volume size is 1GB"
        kwargs = self.new_kwargs(size="2")
        with self.assertRaisesMessage(faults.BadRequest, large_size_msg):
            volumes.create_common(**kwargs)

        # Check if size was added properly.
        kwargs = self.new_kwargs(size="1")
        vol = volumes.create_common(**kwargs)
        self.assertEqual(vol.size, 1)


@patch("synnefo.logic.rapi_pool.GanetiRapiClient")
@override_settings(CYCLADES_DETACHABLE_DISK_TEMPLATES=("ext_archipelago",))
class VolumesTest(QuotaAssertions, django.test.TestCase):
    def setUp(self):
        # Volume types
        self.archip_vt = mf.VolumeTypeFactory(name="archipelago",
                                              disk_template="ext_archipelago")
        self.file_vt = mf.VolumeTypeFactory(name="file", disk_template="file")

        # Common arguments
        self.userid = "test_user"
        self.size = 1
        self.kwargs = {"user_id": self.userid, }

        # VMs
        self.archip_vm = mf.VirtualMachineFactory(
            userid=self.userid, flavor__volume_type=self.archip_vt)
        self.file_vm = mf.VirtualMachineFactory(
            userid=self.userid, flavor__volume_type=self.file_vt)

    def create_kwargs(self, **custom_kwargs):
        """Construct a dictionary of keyword arguments for the "create" action.

        This dictionary is based on the default kwargs of the test suite and is
        updated by user-provided ones.
        """
        # Deepcopy the common kwargs so that we don't affect the other tests.
        kwargs = deepcopy(self.kwargs)
        # Add some default kwargs that make sense for the "create" action.
        default_kwargs = {"size": self.size, }
        kwargs.update(default_kwargs)
        # Override or add more kwargs using the user-provided key-values
        kwargs.update(custom_kwargs)

        return kwargs

    def get_ganeti_args(self, mrapi):
        """Get all the args sent to Ganeti for `ModifyInstance`."""
        _, __, ganeti_kwargs = mrapi().ModifyInstance.mock_calls[0]
        return ganeti_kwargs

    def get_ganeti_disk_args(self, mrapi):
        """Get the disk args sent to Ganeti for `ModifyInstance`."""
        # Get the keyword arguments for the Ganeti call.
        ganeti_args = self.get_ganeti_args(mrapi)
        # The Ganeti call can refer to many disks, but we commonly address
        # just one.
        disk_kwargs = ganeti_args["disks"][0]

        return disk_kwargs

    def common_volume_checks(self, vol):
        self.assertEqual(vol.size, self.size)
        self.assertEqual(vol.userid, self.userid)
        self.assertEqual(vol.name, None)
        self.assertEqual(vol.description, None)
        self.assertEqual(vol.source_snapshot_id, None)
        self.assertEqual(vol.source, None)
        self.assertEqual(vol.origin, None)
        self.assertEqual(vol.source_volume_id, None)
        self.assertEqual(vol.source_image_id, None)

    def test_create_bad_volume_types(self, mrapi):
        """Various tests for the create action regarding volume types."""
        # No volume type
        kwargs = self.create_kwargs(server=None)
        with self.assertRaises(faults.BadRequest):
            volumes.create(**kwargs)

        # Conflicting volume types (ext_archipelago != file)
        conflict_msg = "Cannot create a volume with type '{}' to a server" \
                       " with volume type '{}'.".format(
                           self.archip_vt.id, self.file_vt.id)
        kwargs = self.create_kwargs(volume_type_id=self.archip_vt.id,
                                    server=self.file_vm)
        with self.assertRaisesMessage(faults.BadRequest, conflict_msg):
            volumes.create(**kwargs)

        # Non-detachable volume type
        non_detachable_msg = "Volume type 'file' is not detachable"
        kwargs = self.create_kwargs(volume_type_id=self.file_vt.id,
                                    server=None)
        with self.assertRaisesMessage(faults.BadRequest, non_detachable_msg):
            volumes.create(**kwargs)

    def test_create_standalone(self, mrapi):
        """Test if standalone volumes are created properly."""
        kwargs = self.create_kwargs(volume_type_id=self.archip_vt.id,
                                    server=None)
        with mocked_quotaholder() as m:
            vol = volumes.create(**kwargs)
        expected_commission = {(self.userid, "cyclades.disk"): self.size << 30}
        self.assertCommissionEqual(m, expected_commission)
        self.assertAcceptedSerial(m, vol.serial)

        self.common_volume_checks(vol)
        self.assertEqual(vol.machine, None)
        self.assertEqual(vol.volume_type, self.archip_vt)
        self.assertEqual(vol.status, "AVAILABLE")
        self.assertEqual(vol.index, None)

    def create_and_attach(self, mrapi, vm):
        """Common tests for create and attach operation."""
        kwargs = self.create_kwargs(server=vm)
        mrapi().ModifyInstance.return_value = 42
        with mocked_quotaholder() as m:
            vol = volumes.create(**kwargs)

        expected_commission = {(self.userid, "cyclades.disk"): self.size << 30}
        self.assertCommissionEqual(m, expected_commission)
        self.common_volume_checks(vol)
        self.assertEqual(vol.machine, vm)
        self.assertEqual(vol.volume_type, vm.flavor.volume_type)
        self.assertEqual(vol.index, 0)

        gnt_args = self.get_ganeti_args(mrapi)
        self.assertEqual(gnt_args["instance"], vm.backend_vm_id)
        disk_info = self.get_ganeti_disk_args(mrapi)[2]
        self.assertEqual(disk_info["size"], self.size << 10)
        self.assertEqual(disk_info["name"], vol.backend_volume_uuid)
        self.assertFalse("origin" in disk_info)

    def test_create_non_detachable_and_attach(self, mrapi):
        """Test if a simple volume can be created and attached to VM."""
        self.create_and_attach(mrapi, self.file_vm)
        disk_args = self.get_ganeti_disk_args(mrapi)
        disk_kwargs = disk_args[2]
        self.assertNotIn("reuse_data", disk_kwargs)

    def test_create_detachable_and_attach(self, mrapi):
        """Test if a detachable volume can be created and attached to VM."""
        self.create_and_attach(mrapi, self.archip_vm)
        disk_args = self.get_ganeti_disk_args(mrapi)
        disk_kwargs = disk_args[2]
        self.assertIn("reuse_data", disk_kwargs)
        self.assertEqual(disk_kwargs["reuse_data"], "False")

    def test_create_from_volume(self, mrapi):
        svol = mf.VolumeFactory(userid=self.userid, status="IN_USE",
                                volume_type=self.file_vm.flavor.volume_type)
        kwargs = deepcopy(self.kwargs)
        kwargs = self.create_kwargs(size=svol.size, server=self.file_vm)
        self.assertRaises(faults.BadRequest,
                          volumes.create,
                          source_volume_id=svol.id,
                          **kwargs)
        # # Check permissions
        # svol = mf.VolumeFactory(userid="other_user",
        #                         volume_type=self.file_vm.flavor.volume_type)
        # self.assertRaises(faults.BadRequest,
        #                   volumes.create,
        #                   source_volume_id=svol.id,
        #                   **self.kwargs)
        # # Invalid volume status
        # svol = mf.VolumeFactory(userid=self.userid, status="CREATING",
        #                         volume_type=self.file_vm.flavor.volume_type)
        # self.assertRaises(faults.BadRequest,
        #                   volumes.create,
        #                   source_volume_id=svol.id,
        #                   **self.kwargs)
        # svol = mf.VolumeFactory(userid=self.userid, status="AVAILABLE",
        #                         volume_type=self.file_vm.flavor.volume_type)
        # self.assertRaises(faults.BadRequest,
        #                   volumes.create,
        #                   source_volume_id=svol.id,
        #                   **self.kwargs)

        # svol.status = "IN_USE"
        # svol.save()
        # mrapi().ModifyInstance.return_value = 42
        # kwargs = deepcopy(self.kwargs)
        # kwargs["size"] = svol.size
        # with mocked_quotaholder():
        #     vol = volumes.create(source_volume_id=svol.id, **kwargs)

        # self.assertEqual(vol.size, svol.size)
        # self.assertEqual(vol.userid, self.userid)
        # self.assertEqual(vol.name, None)
        # self.assertEqual(vol.description, None)
        # self.assertEqual(vol.source, "volume:%s" % svol.id)
        # self.assertEqual(vol.origin, svol.backend_volume_uuid)
        # self.assertEqual(vol.volume_type, svol.volume_type)

        # name, args, kwargs = mrapi().ModifyInstance.mock_calls[0]
        # self.assertEqual(kwargs["instance"], self.file_vm.backend_vm_id)
        # disk_info = kwargs["disks"][0][2]
        # self.assertEqual(disk_info["size"], svol.size << 10)
        # self.assertEqual(disk_info["name"], vol.backend_volume_uuid)
        # self.assertEqual(disk_info["origin"], svol.backend_volume_uuid)

    @patch("synnefo.plankton.backend.PlanktonBackend")
    def test_create_from_snapshot(self, mimage, mrapi):
        # Wrong source
        mimage().__enter__().get_snapshot.side_effect = faults.ItemNotFound
        kwargs = self.create_kwargs(server=self.archip_vm,
                                    source_snapshot_id=421)
        self.assertRaises(faults.BadRequest, volumes.create, **kwargs)

        mimage().__enter__().get_snapshot.side_effect = None
        mimage().__enter__().get_snapshot.return_value = {
            'location': 'pithos://foo',
            'mapfile': 'snf-snapshot-43',
            'id': 12,
            'name': "test_image",
            'version': 42,
            'size': 1242,
            'disk_format': 'diskdump',
            'status': 'AVAILABLE',
            'properties': {'source_volume': 42}}

        mrapi().ModifyInstance.return_value = 42
        kwargs = self.create_kwargs(source_snapshot_id=12,
                                    server=self.archip_vm)
        with mocked_quotaholder():
            vol = volumes.create(**kwargs)

        self.assertEqual(vol.size, self.size)
        self.assertEqual(vol.userid, self.userid)
        self.assertEqual(vol.name, None)
        self.assertEqual(vol.description, None)
        self.assertEqual(int(vol.source_snapshot_id), 12)
        self.assertEqual(vol.source_volume_id, None)
        self.assertEqual(vol.source_image_id, None)
        self.assertEqual(vol.origin, "snf-snapshot-43")

        name, args, kwargs = mrapi().ModifyInstance.mock_calls[0]
        self.assertEqual(kwargs["instance"], self.archip_vm.backend_vm_id)
        disk_info = kwargs["disks"][0][2]
        self.assertEqual(disk_info["size"], self.size << 10)
        self.assertEqual(disk_info["name"], vol.backend_volume_uuid)
        self.assertEqual(disk_info["origin"], "snf-snapshot-43")

    def test_attach(self, mrapi):
        """Test the attach functionality."""
        # Fail to attach a non-detachable volume
        vol = mf.VolumeFactory(userid=self.userid, volume_type=self.file_vt,
                               machine=None, backendjobid="1134",
                               status="AVAILABLE")
        message = "Volume type '{}' is not detachable".format(
            self.file_vt.disk_template)
        with self.assertRaisesMessage(faults.BadRequest, message):
            volumes.attach(self.archip_vm, vol.id)

        # Fail to attach a volume that is in use
        vol.volume_type = self.archip_vt
        vol.userid = "test_user"
        vol.status = "IN_USE"
        vol.save()
        message = "Cannot attach volume while volume is in '{}' status".format(
            vol.status)
        with self.assertRaisesMessage(faults.BadRequest, message):
            volumes.attach(self.archip_vm, vol.id)

        # Fail to attach a volume to a server with a different volume type
        message = "Volume and server must have the same volume type"
        vol.status = "AVAILABLE"
        vol.save()
        with self.assertRaises(faults.BadRequest) as e:
            volumes.attach(self.file_vm, vol.id)
        self.assertIn(message, e.exception.message)

        # Attach a volume to a server
        mrapi().ModifyInstance.return_value = 42
        with mocked_quotaholder() as m:
            vol = volumes.attach(self.archip_vm, vol.id)
        # Assert that the volume is assigned to the VM, it has an appropriate
        # status and that no commission was sent.
        self.archip_vm = VirtualMachine.objects.get(pk=self.archip_vm.id)
        self.assertEqual(vol.machine, self.archip_vm)
        self.assertEqual(vol.volume_type, self.archip_vm.flavor.volume_type)
        self.assertEqual(self.archip_vm.volumes.filter().count(), 1)
        self.assertEqual(vol.index, 0)
        self.assertEqual(vol.status, "ATTACHING")
        self.assertNoCommission(m)

        disk_args = self.get_ganeti_disk_args(mrapi)
        self.assertEqual(disk_args[0], "add")
        self.assertEqual(disk_args[1], '-1')
        disk_kwargs = disk_args[2]
        self.assertEqual(disk_kwargs["reuse_data"], "True")
        self.assertEqual(disk_kwargs["name"], vol.backend_volume_uuid)
        self.assertEqual(disk_kwargs["size"], vol.size << 10)

    def test_detach(self, mrapi):
        """Test the detach functionality."""
        # Fail to detach a non-detachable volume
        vol = mf.VolumeFactory(volume_type=self.file_vt, machine=self.file_vm,
                               userid=self.userid, status="IN_USE")
        message = "Volume type '{}' is not detachable".format(
            self.file_vt.disk_template)
        with self.assertRaisesMessage(faults.BadRequest, message):
            volumes.detach(vol.id)

        # Fail to detach a volume that has never been attached to any server
        vol = mf.VolumeFactory(userid=self.userid, volume_type=self.archip_vt,
                               machine=None)
        message = "Volume is already detached"
        with self.assertRaisesMessage(faults.BadRequest, message):
            volumes.detach(vol.id)

        # Fail to detach a volume that is not in use
        vol = mf.VolumeFactory(userid=self.userid, volume_type=self.archip_vt)
        vol.machine = self.archip_vm
        vol.status = "CREATING"
        vol.save()
        message = "Cannot detach volume while volume is in '{}' status".format(
            vol.status)
        with self.assertRaisesMessage(faults.BadRequest, message):
            volumes.detach(vol.id)

        # Fail to detach the root volume of a vm
        vol.status = "IN_USE"
        vol.index = 0
        vol.save()
        message = "Cannot detach the root volume of server {}.".format(
            self.archip_vm)
        with self.assertRaisesMessage(faults.BadRequest, message):
            volumes.detach(vol.id)

        # Detach a volume from a server
        vol.userid = self.userid
        vol.index = 1
        vol.save()
        mrapi().ModifyInstance.return_value = 42
        with mocked_quotaholder() as m:
            vol = volumes.detach(vol.id)
        # Assert that the VM has just one volume, the volume has an appropriate
        # status and that no commission was sent.
        self.assertEqual(self.archip_vm.volumes.all().count(), 1)
        self.assertEqual(vol.status, "DETACHING")
        self.assertNoCommission(m)
        # Assert that Ganeti was instructed to keep the disks and that the
        # ModifyInstance command corresponds to the target volume and server.
        gnt_args = self.get_ganeti_args(mrapi)
        self.assertIn("keep_disks", gnt_args)
        disk_args = self.get_ganeti_disk_args(mrapi)
        self.assertEqual(disk_args[0], "remove")
        self.assertEqual(disk_args[1], vol.backend_volume_uuid)
        self.assertEqual(disk_args[2], {})

    def test_delete_attached(self, mrapi):
        # Test that we cannot delete root volume
        vm = mf.VirtualMachineFactory(userid=self.userid)
        vol = mf.VolumeFactory(machine=vm, userid=self.userid, status="IN_USE",
                               index=0, size=self.size)
        self.assertRaises(faults.BadRequest,
                          volumes.delete,
                          vol)

        # We can delete everything else
        vol.index = 1
        vol.save()
        mrapi().ModifyInstance.return_value = 42
        with mocked_quotaholder() as m:
            volumes.delete(vol)
        self.assertEqual(vol.backendjobid, 42)
        args, kwargs = mrapi().ModifyInstance.call_args

        expected_commission = {(self.userid, "cyclades.disk"):
                               - (self.size << 30)}
        self.assertCommissionEqual(m, expected_commission)
        self.assertEqual(vol.status, "DELETING")

        self.assertEqual(kwargs["instance"], vm.backend_vm_id)
        self.assertEqual(kwargs["disks"][0], ("remove",
                                              vol.backend_volume_uuid, {}))

    def test_delete_uninitialized(self, mrapi):
        """Test if we can delete an uninitialized volume."""
        # We cannot delete an uninitialized volume in invalid state
        vol = mf.VolumeFactory(machine=None, status="DELETING",
                               userid=self.userid, size=self.size)
        message = "Volume is in invalid state: %s" % vol.status
        with self.assertRaisesMessage(faults.BadRequest, message):
            volumes.delete(vol)

        # Test if the deletion and quota logic works as expected
        vol.status = "AVAILABLE"
        vol.save()
        with mocked_quotaholder() as m:
            vol = volumes.delete(vol)
        expected_commission = {(self.userid, "cyclades.disk"):
                               - (self.size << 30)}
        self.assertCommissionEqual(m, expected_commission)
        self.assertAcceptedSerial(m, vol.serial)
        self.assertEqual(vol.machine, None)
        self.assertEqual(vol.status, "DELETED")
        self.assertEqual(vol.deleted, True)

    def test_delete_detached(self, mrapi):
        """Test the deletion of a detached volume."""
        vol = mf.VolumeFactory(machine=None, status="AVAILABLE",
                               userid=self.userid, backendjobid=42,
                               volume_type=self.archip_vt)
        vm = mf.VirtualMachineFactory(userid=self.userid, helper=True,
                                      operstate="STOPPED",
                                      flavor__volume_type=self.archip_vt)

        mrapi().ModifyInstance.return_value = 42
        with mocked_quotaholder() as m:
            vol = volumes.delete(vol)

        self.assertNoCommission(m)
        self.assertEqual(vol.machine, vm)
        self.assertEqual(vol.status, "DELETING")
        self.assertEqual(vol.deleted, False)


@patch("synnefo.logic.rapi_pool.GanetiRapiClient")
@override_settings(CYCLADES_DETACHABLE_DISK_TEMPLATES=("ext_archipelago",))
class VolumesTransactionsTest(QuotaAssertions,
                              django.test.TransactionTestCase):

    """Transaction tests for exceptions in volume actions."""

    def setUp(self):
        # Volume types
        self.archip_vt = mf.VolumeTypeFactory(name="archipelago",
                                              disk_template="ext_archipelago")
        self.userid = "test_user"
        self.archip_vm = mf.VirtualMachineFactory(
            userid=self.userid, flavor__volume_type=self.archip_vt)

        self.volume_name = "Unfortunate volume"
        self.size = 1
        self.kwargs = {
            "user_id": self.userid,
            "size": self.size,
            "volume_type_id": self.archip_vt.id,
            "server": None,
            "name": self.volume_name,
        }

    def test_create_standalone_create_common_ex(self, mrapi):
        """Create volume and crash right after that."""
        def mock_create_common(*args, **kwargs):
            create_common(*args, **kwargs)
            raise MurphysLaw

        with patch.object(volumes, "create_common") as m:
            m.side_effect = mock_create_common
            with self.assertRaises(MurphysLaw):
                with mocked_quotaholder() as mqh:
                    volumes.create(**self.kwargs)

        # Assert that no commission was sent
        self.assertNoCommission(mqh)

    def test_create_standalone_handle_resource_commission_ex(self, mrapi):
        """Create a volume, send commission and crash right after that."""
        def mock_handle_resource_commission(*args, **kwargs):
            handle_resource_commission(*args, **kwargs)
            raise MurphysLaw

        with patch("synnefo.quotas.handle_resource_commission") as m:
            m.side_effect = mock_handle_resource_commission
            with self.assertRaises(MurphysLaw):
                with mocked_quotaholder() as mqh:
                    volumes.create(**self.kwargs)

        # Assert that the commission was sent.
        expected_commission = {(self.userid, "cyclades.disk"): self.size << 30}
        self.assertCommissionEqual(mqh, expected_commission)

    def test_create_standalone_accept_serial_ex(self, mrapi):
        """Create a volume, send commission and crash when accepting serial."""
        with patch("synnefo.quotas.accept_serial") as m:
            m.side_effect = MurphysLaw
            with mocked_quotaholder() as mqh:
                volumes.create(**self.kwargs)

        # Assert that the transaction was commited and that the commission was
        # sent and accepted, albeit locally.
        vol = Volume.objects.get(name=self.volume_name)
        expected_commission = {(self.userid, "cyclades.disk"): self.size << 30}
        self.assertCommissionEqual(mqh, expected_commission)
        self.assertEqual(vol.serial.accept, True)

    def test_create_and_attach_ex(self, mrapi):
        """Create a volume and crash when attaching it to a VM."""
        self.kwargs["server"] = self.archip_vm
        mrapi().ModifyInstance.return_value = 42
        with patch("synnefo.logic.backend.attach_volume") as m:
            m.side_effect = MurphysLaw
            with self.assertRaises(MurphysLaw):
                with mocked_quotaholder() as mqh:
                    volumes.create(**self.kwargs)
        del self.kwargs["server"]

        # Assert that the commission was sent.
        expected_commission = {(self.userid, "cyclades.disk"): self.size << 30}
        self.assertCommissionEqual(mqh, expected_commission)
