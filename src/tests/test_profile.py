"""
Tests for Profile class
"""

from uuid import UUID

import pytest

from myc_http_tools.models.licensed_resources import (
    LicensedResource,
    LicensedResources,
)
from myc_http_tools.models.owner import Owner
from myc_http_tools.models.permission import Permission
from myc_http_tools.models.profile import Profile
from myc_http_tools.models.tenants_ownership import (
    TenantOwnership,
    TenantsOwnership,
)
from myc_http_tools.models.verbose_status import VerboseStatus


class TestProfile:
    """Test cases for Profile class"""

    def test_profile_creation_minimal(self):
        """Test creating a Profile with minimal required fields"""
        profile = Profile(
            acc_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
            is_subscription=True,
            is_staff=False,
            owner_is_active=True,
            account_is_active=True,
            account_was_approved=True,
            account_was_archived=False,
            account_was_deleted=False,
        )

        assert profile.acc_id == UUID("123e4567-e89b-12d3-a456-426614174000")
        assert profile.is_subscription is True
        assert profile.is_staff is False
        assert profile.owner_is_active is True
        assert profile.account_is_active is True
        assert profile.account_was_approved is True
        assert profile.account_was_archived is False
        assert profile.account_was_deleted is False
        assert profile.owners == []
        assert profile.verbose_status is None
        assert profile.licensed_resources is None
        assert profile.tenants_ownership is None
        assert profile.meta is None
        assert profile.filtering_state is None

    def test_profile_creation_with_all_fields(self):
        """Test creating a Profile with all fields populated"""
        owner = Owner(
            id=UUID("987fcdeb-51a2-43d1-9f12-345678901234"),
            email="test@example.com",
            first_name="John",
            last_name="Doe",
            username="johndoe",
            is_principal=True,
        )

        tenant_ownership = TenantOwnership(
            id=UUID("456e7890-e89b-12d3-a456-426614174567"),
            name="Test Tenant",
            since="2024-01-01T00:00:00Z",
        )

        tenants_ownership = TenantsOwnership(records=[tenant_ownership])

        licensed_resource = LicensedResource(
            tenant_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
            acc_id=UUID("987fcdeb-51a2-43d1-9f12-345678901234"),
            role_id=UUID("456e7890-e89b-12d3-a456-426614174567"),
            role="admin",
            perm=Permission.READ,
            sys_acc=True,
            acc_name="Test Account",
            verified=True,
        )

        licensed_resources = LicensedResources(records=[licensed_resource])

        profile = Profile(
            owners=[owner],
            acc_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
            is_subscription=True,
            is_staff=True,
            owner_is_active=True,
            account_is_active=True,
            account_was_approved=True,
            account_was_archived=False,
            account_was_deleted=False,
            verbose_status=VerboseStatus.VERIFIED,
            licensed_resources=licensed_resources,
            tenants_ownership=tenants_ownership,
            meta={"key": "value", "number": 42},
            filtering_state=["filter1", "filter2"],
        )

        assert len(profile.owners) == 1
        assert profile.owners[0] == owner
        assert profile.acc_id == UUID("123e4567-e89b-12d3-a456-426614174000")
        assert profile.is_subscription is True
        assert profile.is_staff is True
        assert profile.owner_is_active is True
        assert profile.account_is_active is True
        assert profile.account_was_approved is True
        assert profile.account_was_archived is False
        assert profile.account_was_deleted is False
        assert profile.verbose_status == VerboseStatus.VERIFIED
        assert profile.licensed_resources == licensed_resources
        assert profile.tenants_ownership == tenants_ownership
        assert profile.meta == {"key": "value", "number": 42}
        assert profile.filtering_state == ["filter1", "filter2"]

    def test_profile_creation_with_multiple_owners(self):
        """Test creating a Profile with multiple owners"""
        owner1 = Owner(
            id=UUID("987fcdeb-51a2-43d1-9f12-345678901234"),
            email="owner1@example.com",
            first_name="John",
            last_name="Doe",
            username="johndoe",
            is_principal=True,
        )

        owner2 = Owner(
            id=UUID("887fcdeb-51a2-43d1-9f12-345678901235"),
            email="owner2@example.com",
            first_name="Jane",
            last_name="Smith",
            username="janesmith",
            is_principal=False,
        )

        profile = Profile(
            owners=[owner1, owner2],
            acc_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
            is_subscription=True,
            is_staff=False,
            owner_is_active=True,
            account_is_active=True,
            account_was_approved=True,
            account_was_archived=False,
            account_was_deleted=False,
        )

        assert len(profile.owners) == 2
        assert profile.owners[0] == owner1
        assert profile.owners[1] == owner2

    def test_profile_creation_with_different_verbose_status(self):
        """Test creating a Profile with different VerboseStatus values"""
        for status in VerboseStatus:
            profile = Profile(
                acc_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
                is_subscription=True,
                is_staff=False,
                owner_is_active=True,
                account_is_active=True,
                account_was_approved=True,
                account_was_archived=False,
                account_was_deleted=False,
                verbose_status=status,
            )

            assert profile.verbose_status == status

    def test_profile_creation_with_meta_data(self):
        """Test creating a Profile with various meta data types"""
        meta_data = {
            "string": "test",
            "number": 42,
            "float": 3.14,
            "boolean": True,
            "list": [1, 2, 3],
            "dict": {"nested": "value"},
            "null": None,
        }

        profile = Profile(
            acc_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
            is_subscription=True,
            is_staff=False,
            owner_is_active=True,
            account_is_active=True,
            account_was_approved=True,
            account_was_archived=False,
            account_was_deleted=False,
            meta=meta_data,
        )

        assert profile.meta == meta_data

    def test_profile_creation_with_filtering_state(self):
        """Test creating a Profile with filtering state"""
        filtering_state = ["filter1", "filter2", "filter3"]

        profile = Profile(
            acc_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
            is_subscription=True,
            is_staff=False,
            owner_is_active=True,
            account_is_active=True,
            account_was_approved=True,
            account_was_archived=False,
            account_was_deleted=False,
            filtering_state=filtering_state,
        )

        assert profile.filtering_state == filtering_state

    def test_profile_creation_with_empty_optional_fields(self):
        """Test creating a Profile with empty optional fields"""
        profile = Profile(
            acc_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
            is_subscription=True,
            is_staff=False,
            owner_is_active=True,
            account_is_active=True,
            account_was_approved=True,
            account_was_archived=False,
            account_was_deleted=False,
            verbose_status=None,
            licensed_resources=None,
            tenants_ownership=None,
            meta=None,
            filtering_state=None,
        )

        assert profile.verbose_status is None
        assert profile.licensed_resources is None
        assert profile.tenants_ownership is None
        assert profile.meta is None
        assert profile.filtering_state is None

    def test_profile_validation_missing_required_fields(self):
        """Test Profile validation with missing required fields"""
        with pytest.raises(Exception):  # Pydantic validation error
            Profile()

        with pytest.raises(Exception):
            Profile(acc_id=UUID("123e4567-e89b-12d3-a456-426614174000"))

        with pytest.raises(Exception):
            Profile(
                acc_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
                is_subscription=True,
            )

    def test_profile_validation_invalid_uuid(self):
        """Test Profile validation with invalid UUID"""
        with pytest.raises(Exception):
            Profile(
                acc_id="invalid-uuid",
                is_subscription=True,
                is_staff=False,
                owner_is_active=True,
                account_is_active=True,
                account_was_approved=True,
                account_was_archived=False,
                account_was_deleted=False,
            )

    def test_profile_validation_invalid_boolean_fields(self):
        """Test Profile validation with invalid boolean fields"""
        with pytest.raises(Exception):
            Profile(
                acc_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
                is_subscription="not-a-boolean",
                is_staff=False,
                owner_is_active=True,
                account_is_active=True,
                account_was_approved=True,
                account_was_archived=False,
                account_was_deleted=False,
            )

    def test_with_read_access_without_licensed_resources(self):
        """Test with_read_access when licensed_resources is None"""
        profile = Profile(
            acc_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
            is_subscription=True,
            is_staff=False,
            owner_is_active=True,
            account_is_active=True,
            account_was_approved=True,
            account_was_archived=False,
            account_was_deleted=False,
            licensed_resources=None,
        )

        result = profile.with_read_access()

        # Following the gateway, the permission filter is always recorded even
        # when there are no licensed resources (no short-circuit).
        assert result.licensed_resources is None
        assert result.filtering_state == ["1:permission:0"]

    def test_with_write_access_without_licensed_resources(self):
        """Test with_write_access when licensed_resources is None"""
        profile = Profile(
            acc_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
            is_subscription=True,
            is_staff=False,
            owner_is_active=True,
            account_is_active=True,
            account_was_approved=True,
            account_was_archived=False,
            account_was_deleted=False,
            licensed_resources=None,
        )

        result = profile.with_write_access()

        # Following the gateway, the permission filter is always recorded even
        # when there are no licensed resources (no short-circuit).
        assert result.licensed_resources is None
        assert result.filtering_state == ["1:permission:1"]

    def test_with_read_access_with_licensed_resources(self):
        """Test with_read_access when licensed_resources is present"""
        read_resource = LicensedResource(
            tenant_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
            acc_id=UUID("987fcdeb-51a2-43d1-9f12-345678901234"),
            role_id=UUID("456e7890-e89b-12d3-a456-426614174567"),
            role="admin",
            perm=Permission.READ,
            sys_acc=True,
            acc_name="Read Account",
            verified=True,
        )

        write_resource = LicensedResource(
            tenant_id=UUID("223e4567-e89b-12d3-a456-426614174001"),
            acc_id=UUID("887fcdeb-51a2-43d1-9f12-345678901235"),
            role_id=UUID("556e7890-e89b-12d3-a456-426614174568"),
            role="editor",
            perm=Permission.WRITE,
            sys_acc=False,
            acc_name="Write Account",
            verified=False,
        )

        licensed_resources = LicensedResources(
            records=[read_resource, write_resource]
        )

        profile = Profile(
            acc_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
            is_subscription=True,
            is_staff=False,
            owner_is_active=True,
            account_is_active=True,
            account_was_approved=True,
            account_was_archived=False,
            account_was_deleted=False,
            licensed_resources=licensed_resources,
        )

        result = profile.with_read_access()

        # Should return a copy of the profile
        assert result is not profile  # Different objects
        assert result.acc_id == profile.acc_id
        assert result.is_subscription == profile.is_subscription
        assert result.licensed_resources is not None

        # Should contain both READ and WRITE permission resources (since WRITE >= READ)
        assert len(result.licensed_resources.records) == 2

        # Check that both resources are present
        perms = [record.perm for record in result.licensed_resources.records]
        assert Permission.READ in perms
        assert Permission.WRITE in perms

        # Check that urls is set to None
        assert result.licensed_resources.urls is None

    def test_with_write_access_with_licensed_resources(self):
        """Test with_write_access when licensed_resources is present"""
        read_resource = LicensedResource(
            tenant_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
            acc_id=UUID("987fcdeb-51a2-43d1-9f12-345678901234"),
            role_id=UUID("456e7890-e89b-12d3-a456-426614174567"),
            role="admin",
            perm=Permission.READ,
            sys_acc=True,
            acc_name="Read Account",
            verified=True,
        )

        write_resource = LicensedResource(
            tenant_id=UUID("223e4567-e89b-12d3-a456-426614174001"),
            acc_id=UUID("887fcdeb-51a2-43d1-9f12-345678901235"),
            role_id=UUID("556e7890-e89b-12d3-a456-426614174568"),
            role="editor",
            perm=Permission.WRITE,
            sys_acc=False,
            acc_name="Write Account",
            verified=False,
        )

        licensed_resources = LicensedResources(
            records=[read_resource, write_resource]
        )

        profile = Profile(
            acc_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
            is_subscription=True,
            is_staff=False,
            owner_is_active=True,
            account_is_active=True,
            account_was_approved=True,
            account_was_archived=False,
            account_was_deleted=False,
            licensed_resources=licensed_resources,
        )

        result = profile.with_write_access()

        # Should return a copy of the profile
        assert result is not profile  # Different objects
        assert result.acc_id == profile.acc_id
        assert result.is_subscription == profile.is_subscription
        assert result.licensed_resources is not None

        # Should only contain WRITE permission resources (since READ < WRITE)
        assert len(result.licensed_resources.records) == 1
        assert result.licensed_resources.records[0].perm == Permission.WRITE
        assert result.licensed_resources.records[0].acc_name == "Write Account"

        # Check that urls is set to None
        assert result.licensed_resources.urls is None

    def test_with_read_access_with_mixed_permissions(self):
        """Test with_read_access with multiple resources having different permissions"""
        read_resource1 = LicensedResource(
            tenant_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
            acc_id=UUID("987fcdeb-51a2-43d1-9f12-345678901234"),
            role_id=UUID("456e7890-e89b-12d3-a456-426614174567"),
            role="admin",
            perm=Permission.READ,
            sys_acc=True,
            acc_name="Read Account 1",
            verified=True,
        )

        read_resource2 = LicensedResource(
            tenant_id=UUID("223e4567-e89b-12d3-a456-426614174001"),
            acc_id=UUID("887fcdeb-51a2-43d1-9f12-345678901235"),
            role_id=UUID("556e7890-e89b-12d3-a456-426614174568"),
            role="viewer",
            perm=Permission.READ,
            sys_acc=False,
            acc_name="Read Account 2",
            verified=False,
        )

        write_resource = LicensedResource(
            tenant_id=UUID("323e4567-e89b-12d3-a456-426614174002"),
            acc_id=UUID("787fcdeb-51a2-43d1-9f12-345678901236"),
            role_id=UUID("656e7890-e89b-12d3-a456-426614174569"),
            role="editor",
            perm=Permission.WRITE,
            sys_acc=False,
            acc_name="Write Account",
            verified=True,
        )

        licensed_resources = LicensedResources(
            records=[read_resource1, read_resource2, write_resource]
        )

        profile = Profile(
            acc_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
            is_subscription=True,
            is_staff=False,
            owner_is_active=True,
            account_is_active=True,
            account_was_approved=True,
            account_was_archived=False,
            account_was_deleted=False,
            licensed_resources=licensed_resources,
        )

        result = profile.with_read_access()

        # Should contain all resources since all have READ or higher permission
        assert len(result.licensed_resources.records) == 3

        # Check that all resources are present
        perms = [record.perm for record in result.licensed_resources.records]
        assert perms.count(Permission.READ) == 2
        assert perms.count(Permission.WRITE) == 1

        # Check that urls is set to None
        assert result.licensed_resources.urls is None

    def test_with_write_access_with_mixed_permissions(self):
        """Test with_write_access with multiple resources having different permissions"""
        read_resource1 = LicensedResource(
            tenant_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
            acc_id=UUID("987fcdeb-51a2-43d1-9f12-345678901234"),
            role_id=UUID("456e7890-e89b-12d3-a456-426614174567"),
            role="admin",
            perm=Permission.READ,
            sys_acc=True,
            acc_name="Read Account 1",
            verified=True,
        )

        read_resource2 = LicensedResource(
            tenant_id=UUID("223e4567-e89b-12d3-a456-426614174001"),
            acc_id=UUID("887fcdeb-51a2-43d1-9f12-345678901235"),
            role_id=UUID("556e7890-e89b-12d3-a456-426614174568"),
            role="viewer",
            perm=Permission.READ,
            sys_acc=False,
            acc_name="Read Account 2",
            verified=False,
        )

        write_resource1 = LicensedResource(
            tenant_id=UUID("323e4567-e89b-12d3-a456-426614174002"),
            acc_id=UUID("787fcdeb-51a2-43d1-9f12-345678901236"),
            role_id=UUID("656e7890-e89b-12d3-a456-426614174569"),
            role="editor",
            perm=Permission.WRITE,
            sys_acc=False,
            acc_name="Write Account 1",
            verified=True,
        )

        write_resource2 = LicensedResource(
            tenant_id=UUID("423e4567-e89b-12d3-a456-426614174003"),
            acc_id=UUID("687fcdeb-51a2-43d1-9f12-345678901237"),
            role_id=UUID("756e7890-e89b-12d3-a456-426614174570"),
            role="admin",
            perm=Permission.WRITE,
            sys_acc=True,
            acc_name="Write Account 2",
            verified=False,
        )

        licensed_resources = LicensedResources(
            records=[
                read_resource1,
                read_resource2,
                write_resource1,
                write_resource2,
            ]
        )

        profile = Profile(
            acc_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
            is_subscription=True,
            is_staff=False,
            owner_is_active=True,
            account_is_active=True,
            account_was_approved=True,
            account_was_archived=False,
            account_was_deleted=False,
            licensed_resources=licensed_resources,
        )

        result = profile.with_write_access()

        # Should only contain WRITE permission resources
        assert len(result.licensed_resources.records) == 2

        # Check that only WRITE resources are present
        perms = [record.perm for record in result.licensed_resources.records]
        assert perms.count(Permission.WRITE) == 2
        assert Permission.READ not in perms

        # Check that urls is set to None
        assert result.licensed_resources.urls is None

    def test_with_permission_clears_urls_field(self):
        """Test that __with_permission methods clear the urls field"""
        # Create licensed resources with both records and urls
        read_resource = LicensedResource(
            tenant_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
            acc_id=UUID("987fcdeb-51a2-43d1-9f12-345678901234"),
            role_id=UUID("456e7890-e89b-12d3-a456-426614174567"),
            role="admin",
            perm=Permission.READ,
            sys_acc=True,
            acc_name="Read Account",
            verified=True,
        )

        licensed_resources = LicensedResources(
            records=[read_resource],
            urls=[
                "t/123e4567-e89b-12d3-a456-426614174000/a/987fcdeb-51a2-43d1-9f12-345678901234/r/456e7890-e89b-12d3-a456-426614174567?p=admin:0&s=1&v=1&n=UmVhZCBBY2NvdW50"
            ],
        )

        profile = Profile(
            acc_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
            is_subscription=True,
            is_staff=False,
            owner_is_active=True,
            account_is_active=True,
            account_was_approved=True,
            account_was_archived=False,
            account_was_deleted=False,
            licensed_resources=licensed_resources,
        )

        # with_read_access keeps the read resource; the filtered result is a
        # fresh records-only union (urls dropped).
        result_read = profile.with_read_access()
        assert result_read.licensed_resources.urls is None
        assert result_read.licensed_resources.records is not None

        # with_write_access filters out the read-only resource; an empty result
        # collapses licensed_resources to None (gateway behavior).
        result_write = profile.with_write_access()
        assert result_write.licensed_resources is None

    def test_profile_equality(self):
        """Test Profile equality comparison"""
        profile1 = Profile(
            acc_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
            is_subscription=True,
            is_staff=False,
            owner_is_active=True,
            account_is_active=True,
            account_was_approved=True,
            account_was_archived=False,
            account_was_deleted=False,
        )

        profile2 = Profile(
            acc_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
            is_subscription=True,
            is_staff=False,
            owner_is_active=True,
            account_is_active=True,
            account_was_approved=True,
            account_was_archived=False,
            account_was_deleted=False,
        )

        profile3 = Profile(
            acc_id=UUID("223e4567-e89b-12d3-a456-426614174001"),
            is_subscription=True,
            is_staff=False,
            owner_is_active=True,
            account_is_active=True,
            account_was_approved=True,
            account_was_archived=False,
            account_was_deleted=False,
        )

        assert profile1 == profile2
        assert profile1 != profile3

    def test_profile_string_representation(self):
        """Test Profile string representation"""
        profile = Profile(
            acc_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
            is_subscription=True,
            is_staff=False,
            owner_is_active=True,
            account_is_active=True,
            account_was_approved=True,
            account_was_archived=False,
            account_was_deleted=False,
        )

        profile_str = str(profile)
        # Pydantic doesn't include class name in string representation by default
        assert "123e4567-e89b-12d3-a456-426614174000" in profile_str
        assert "is_subscription=True" in profile_str

    def test_profile_model_copy(self):
        """Test Profile model_copy method"""
        profile = Profile(
            acc_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
            is_subscription=True,
            is_staff=False,
            owner_is_active=True,
            account_is_active=True,
            account_was_approved=True,
            account_was_archived=False,
            account_was_deleted=False,
        )

        profile_copy = profile.model_copy()

        assert profile_copy == profile
        assert profile_copy is not profile  # Different objects

    def test_profile_model_copy_with_updates(self):
        """Test Profile model_copy with updates"""
        profile = Profile(
            acc_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
            is_subscription=True,
            is_staff=False,
            owner_is_active=True,
            account_is_active=True,
            account_was_approved=True,
            account_was_archived=False,
            account_was_deleted=False,
        )

        profile_copy = profile.model_copy(update={"is_staff": True})
        assert profile_copy.is_staff is True
        assert profile.is_staff is False  # Original unchanged
        assert profile_copy.acc_id == profile.acc_id  # Other fields unchanged

    def test_profile_with_complex_meta_data(self):
        """Test Profile with complex nested meta data"""
        complex_meta = {
            "user": {
                "id": 123,
                "name": "John Doe",
                "preferences": {
                    "theme": "dark",
                    "notifications": True,
                    "language": "en",
                },
                "permissions": ["read", "write", "admin"],
            },
            "system": {
                "version": "1.0.0",
                "environment": "production",
                "features": {
                    "feature1": True,
                    "feature2": False,
                },
            },
            "timestamps": {
                "created": "2024-01-01T00:00:00Z",
                "updated": "2024-01-02T12:00:00Z",
            },
        }

        profile = Profile(
            acc_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
            is_subscription=True,
            is_staff=False,
            owner_is_active=True,
            account_is_active=True,
            account_was_approved=True,
            account_was_archived=False,
            account_was_deleted=False,
            meta=complex_meta,
        )

        assert profile.meta == complex_meta
        assert profile.meta["user"]["id"] == 123
        assert profile.meta["user"]["preferences"]["theme"] == "dark"
        assert profile.meta["system"]["features"]["feature1"] is True

    def test_profile_with_empty_lists(self):
        """Test Profile with empty lists for optional fields"""
        profile = Profile(
            acc_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
            is_subscription=True,
            is_staff=False,
            owner_is_active=True,
            account_is_active=True,
            account_was_approved=True,
            account_was_archived=False,
            account_was_deleted=False,
            owners=[],  # Empty list
            filtering_state=[],  # Empty list
        )

        assert profile.owners == []
        assert profile.filtering_state == []

    def test_profile_boolean_combinations(self):
        """Test Profile with various boolean field combinations"""
        boolean_fields = [
            "is_subscription",
            "is_staff",
            "owner_is_active",
            "account_is_active",
            "account_was_approved",
            "account_was_archived",
            "account_was_deleted",
        ]

        # Test all True
        profile_all_true = Profile(
            acc_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
            is_subscription=True,
            is_staff=True,
            owner_is_active=True,
            account_is_active=True,
            account_was_approved=True,
            account_was_archived=True,
            account_was_deleted=True,
        )

        for field in boolean_fields:
            assert getattr(profile_all_true, field) is True

        # Test all False
        profile_all_false = Profile(
            acc_id=UUID("223e4567-e89b-12d3-a456-426614174001"),
            is_subscription=False,
            is_staff=False,
            owner_is_active=False,
            account_is_active=False,
            account_was_approved=False,
            account_was_archived=False,
            account_was_deleted=False,
        )

        for field in boolean_fields:
            assert getattr(profile_all_false, field) is False

    def test_on_tenant_without_licensed_resources(self):
        """Test on_tenant when licensed_resources is None"""
        profile = Profile(
            acc_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
            is_subscription=True,
            is_staff=False,
            owner_is_active=True,
            account_is_active=True,
            account_was_approved=True,
            account_was_archived=False,
            account_was_deleted=False,
            licensed_resources=None,
        )

        tenant_id = UUID("223e4567-e89b-12d3-a456-426614174001")
        result = profile.on_tenant(tenant_id)

        # Should return a new profile with None licensed_resources
        assert result.licensed_resources is None
        assert result.filtering_state == [f"1:tenantId:{tenant_id}"]
        assert result.acc_id == profile.acc_id
        assert result.is_subscription == profile.is_subscription

    def test_on_tenant_with_licensed_resources_no_matches(self):
        """Test on_tenant when no licensed resources match the tenant_id"""
        # Create licensed resources for a different tenant
        licensed_resource = LicensedResource(
            acc_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
            sys_acc=False,
            tenant_id=UUID(
                "323e4567-e89b-12d3-a456-426614174002"
            ),  # Different tenant
            acc_name="Test Account",
            role="admin",
            role_id=UUID("423e4567-e89b-12d3-a456-426614174003"),
            perm=Permission.READ,
            verified=True,
        )

        licensed_resources = LicensedResources(records=[licensed_resource])

        profile = Profile(
            acc_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
            is_subscription=True,
            is_staff=False,
            owner_is_active=True,
            account_is_active=True,
            account_was_approved=True,
            account_was_archived=False,
            account_was_deleted=False,
            licensed_resources=licensed_resources,
        )

        tenant_id = UUID(
            "223e4567-e89b-12d3-a456-426614174001"
        )  # Different tenant
        result = profile.on_tenant(tenant_id)

        # Should return a new profile with None licensed_resources (no matches)
        assert result.licensed_resources is None
        assert result.filtering_state == [f"1:tenantId:{tenant_id}"]
        assert result.acc_id == profile.acc_id

    def test_on_tenant_with_licensed_resources_with_matches(self):
        """Test on_tenant when licensed resources match the tenant_id"""
        tenant_id = UUID("223e4567-e89b-12d3-a456-426614174001")

        # Create licensed resources for the target tenant
        licensed_resource1 = LicensedResource(
            acc_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
            sys_acc=False,
            tenant_id=tenant_id,  # Matching tenant
            acc_name="Test Account 1",
            role="admin",
            role_id=UUID("423e4567-e89b-12d3-a456-426614174003"),
            perm=Permission.READ,
            verified=True,
        )

        # Create licensed resources for a different tenant
        licensed_resource2 = LicensedResource(
            acc_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
            sys_acc=False,
            tenant_id=UUID(
                "323e4567-e89b-12d3-a456-426614174002"
            ),  # Different tenant
            acc_name="Test Account 2",
            role="user",
            role_id=UUID("523e4567-e89b-12d3-a456-426614174004"),
            perm=Permission.WRITE,
            verified=True,
        )

        licensed_resources = LicensedResources(
            records=[licensed_resource1, licensed_resource2]
        )

        profile = Profile(
            acc_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
            is_subscription=True,
            is_staff=False,
            owner_is_active=True,
            account_is_active=True,
            account_was_approved=True,
            account_was_archived=False,
            account_was_deleted=False,
            licensed_resources=licensed_resources,
        )

        result = profile.on_tenant(tenant_id)

        # Should return a new profile with filtered licensed_resources
        assert result.licensed_resources is not None
        assert len(result.licensed_resources.records) == 1
        assert result.licensed_resources.records[0] == licensed_resource1
        assert result.filtering_state == [f"1:tenantId:{tenant_id}"]
        assert result.acc_id == profile.acc_id

    def test_on_tenant_updates_filtering_state(self):
        """Test that on_tenant properly updates the filtering_state"""
        profile = Profile(
            acc_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
            is_subscription=True,
            is_staff=False,
            owner_is_active=True,
            account_is_active=True,
            account_was_approved=True,
            account_was_archived=False,
            account_was_deleted=False,
            filtering_state=["existing_filter"],
        )

        tenant_id = UUID("223e4567-e89b-12d3-a456-426614174001")
        result = profile.on_tenant(tenant_id)

        # Should preserve existing filters and add tenant filter
        assert result.filtering_state == [
            "existing_filter",
            f"2:tenantId:{tenant_id}",
        ]

    def test_on_tenant_adds_incremental_tenant_filter(self):
        """Test that on_tenant adds tenant filter incrementally"""
        profile = Profile(
            acc_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
            is_subscription=True,
            is_staff=False,
            owner_is_active=True,
            account_is_active=True,
            account_was_approved=True,
            account_was_archived=False,
            account_was_deleted=False,
            filtering_state=["existing_filter", "2:tenantId:old-tenant-id"],
        )

        new_tenant_id = UUID("223e4567-e89b-12d3-a456-426614174001")
        result = profile.on_tenant(new_tenant_id)

        # Should add the new tenant filter incrementally (not replace)
        assert result.filtering_state == [
            "existing_filter",
            "2:tenantId:old-tenant-id",
            f"3:tenantId:{new_tenant_id}",
        ]

    def test_on_tenant_incremental_filtering_cascade(self):
        """Test incremental filtering state as described in documentation"""
        # Start with empty filtering state
        profile = Profile(
            acc_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
            is_subscription=True,
            is_staff=False,
            owner_is_active=True,
            account_is_active=True,
            account_was_approved=True,
            account_was_archived=False,
            account_was_deleted=False,
            filtering_state=[],
        )

        tenant_id1 = UUID("123e4567-e89b-12d3-a456-426614174000")

        # First filter: tenant
        result1 = profile.on_tenant(tenant_id1)
        assert result1.filtering_state == [f"1:tenantId:{tenant_id1}"]

        # Second filter: another tenant (simulating permission filter would be "2:permission:1")
        tenant_id2 = UUID("123e4567-e89b-12d3-a456-426614174001")
        result2 = result1.on_tenant(tenant_id2)
        assert result2.filtering_state == [
            f"1:tenantId:{tenant_id1}",
            f"2:tenantId:{tenant_id2}",
        ]

        # Third filter: another tenant
        tenant_id3 = UUID("123e4567-e89b-12d3-a456-426614174002")
        result3 = result2.on_tenant(tenant_id3)
        assert result3.filtering_state == [
            f"1:tenantId:{tenant_id1}",
            f"2:tenantId:{tenant_id2}",
            f"3:tenantId:{tenant_id3}",
        ]

    def test_with_roles_without_licensed_resources(self):
        """Test with_roles when licensed_resources is None"""
        profile = Profile(
            acc_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
            is_subscription=True,
            is_staff=False,
            owner_is_active=True,
            account_is_active=True,
            account_was_approved=True,
            account_was_archived=False,
            account_was_deleted=False,
            licensed_resources=None,
        )

        roles = ["admin", "user"]
        result = profile.with_roles(roles)

        # Should return a new profile with None licensed_resources
        assert result.licensed_resources is None
        assert result.filtering_state == ["1:role:admin,user"]
        assert result.acc_id == profile.acc_id
        assert result.is_subscription == profile.is_subscription

    def test_with_roles_with_licensed_resources_no_matches(self):
        """Test with_roles when no licensed resources match the roles"""
        # Create licensed resources with different roles
        licensed_resource = LicensedResource(
            acc_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
            sys_acc=False,
            tenant_id=UUID("323e4567-e89b-12d3-a456-426614174002"),
            acc_name="Test Account",
            role="manager",  # Different role
            role_id=UUID("423e4567-e89b-12d3-a456-426614174003"),
            perm=Permission.READ,
            verified=True,
        )

        licensed_resources = LicensedResources(records=[licensed_resource])

        profile = Profile(
            acc_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
            is_subscription=True,
            is_staff=False,
            owner_is_active=True,
            account_is_active=True,
            account_was_approved=True,
            account_was_archived=False,
            account_was_deleted=False,
            licensed_resources=licensed_resources,
        )

        roles = ["admin", "user"]  # Different roles
        result = profile.with_roles(roles)

        # Should return a new profile with None licensed_resources (no matches)
        assert result.licensed_resources is None
        assert result.filtering_state == ["1:role:admin,user"]
        assert result.acc_id == profile.acc_id

    def test_with_roles_with_licensed_resources_with_matches(self):
        """Test with_roles when licensed resources match the roles"""
        roles = ["admin", "user"]

        # Create licensed resources with matching roles
        licensed_resource1 = LicensedResource(
            acc_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
            sys_acc=False,
            tenant_id=UUID("323e4567-e89b-12d3-a456-426614174002"),
            acc_name="Test Account 1",
            role="admin",  # Matching role
            role_id=UUID("423e4567-e89b-12d3-a456-426614174003"),
            perm=Permission.READ,
            verified=True,
        )

        # Create licensed resources with non-matching roles
        licensed_resource2 = LicensedResource(
            acc_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
            sys_acc=False,
            tenant_id=UUID("323e4567-e89b-12d3-a456-426614174002"),
            acc_name="Test Account 2",
            role="manager",  # Non-matching role
            role_id=UUID("523e4567-e89b-12d3-a456-426614174004"),
            perm=Permission.WRITE,
            verified=True,
        )

        # Create licensed resources with another matching role
        licensed_resource3 = LicensedResource(
            acc_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
            sys_acc=False,
            tenant_id=UUID("323e4567-e89b-12d3-a456-426614174002"),
            acc_name="Test Account 3",
            role="user",  # Matching role
            role_id=UUID("623e4567-e89b-12d3-a456-426614174005"),
            perm=Permission.READ,
            verified=True,
        )

        licensed_resources = LicensedResources(
            records=[licensed_resource1, licensed_resource2, licensed_resource3]
        )

        profile = Profile(
            acc_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
            is_subscription=True,
            is_staff=False,
            owner_is_active=True,
            account_is_active=True,
            account_was_approved=True,
            account_was_archived=False,
            account_was_deleted=False,
            licensed_resources=licensed_resources,
        )

        result = profile.with_roles(roles)

        # Should return a new profile with filtered licensed_resources
        assert result.licensed_resources is not None
        assert len(result.licensed_resources.records) == 2
        assert licensed_resource1 in result.licensed_resources.records
        assert licensed_resource3 in result.licensed_resources.records
        assert licensed_resource2 not in result.licensed_resources.records
        assert result.filtering_state == ["1:role:admin,user"]
        assert result.acc_id == profile.acc_id

    def test_with_roles_updates_filtering_state(self):
        """Test that with_roles properly updates the filtering_state"""
        profile = Profile(
            acc_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
            is_subscription=True,
            is_staff=False,
            owner_is_active=True,
            account_is_active=True,
            account_was_approved=True,
            account_was_archived=False,
            account_was_deleted=False,
            filtering_state=["existing_filter"],
        )

        roles = ["admin", "user"]
        result = profile.with_roles(roles)

        # Should preserve existing filters and add role filter
        assert result.filtering_state == [
            "existing_filter",
            "2:role:admin,user",
        ]

    def test_with_roles_adds_incremental_role_filter(self):
        """Test that with_roles adds role filter incrementally"""
        profile = Profile(
            acc_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
            is_subscription=True,
            is_staff=False,
            owner_is_active=True,
            account_is_active=True,
            account_was_approved=True,
            account_was_archived=False,
            account_was_deleted=False,
            filtering_state=["existing_filter", "2:role:old-role"],
        )

        new_roles = ["admin", "user"]
        result = profile.with_roles(new_roles)

        # Should add the new role filter incrementally (not replace)
        assert result.filtering_state == [
            "existing_filter",
            "2:role:old-role",
            "3:role:admin,user",
        ]

    def test_with_roles_single_role(self):
        """Test with_roles with a single role"""
        # Create licensed resources
        licensed_resource = LicensedResource(
            acc_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
            sys_acc=False,
            tenant_id=UUID("323e4567-e89b-12d3-a456-426614174002"),
            acc_name="Test Account",
            role="admin",
            role_id=UUID("423e4567-e89b-12d3-a456-426614174003"),
            perm=Permission.READ,
            verified=True,
        )

        licensed_resources = LicensedResources(records=[licensed_resource])

        profile = Profile(
            acc_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
            is_subscription=True,
            is_staff=False,
            owner_is_active=True,
            account_is_active=True,
            account_was_approved=True,
            account_was_archived=False,
            account_was_deleted=False,
            licensed_resources=licensed_resources,
        )

        roles = ["admin"]  # Single role
        result = profile.with_roles(roles)

        # Should return a new profile with filtered licensed_resources
        assert result.licensed_resources is not None
        assert len(result.licensed_resources.records) == 1
        assert result.licensed_resources.records[0] == licensed_resource
        assert result.filtering_state == ["1:role:admin"]

    def test_with_roles_empty_list(self):
        """Test with_roles with an empty roles list"""
        # Create licensed resources
        licensed_resource = LicensedResource(
            acc_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
            sys_acc=False,
            tenant_id=UUID("323e4567-e89b-12d3-a456-426614174002"),
            acc_name="Test Account",
            role="admin",
            role_id=UUID("423e4567-e89b-12d3-a456-426614174003"),
            perm=Permission.READ,
            verified=True,
        )

        licensed_resources = LicensedResources(records=[licensed_resource])

        profile = Profile(
            acc_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
            is_subscription=True,
            is_staff=False,
            owner_is_active=True,
            account_is_active=True,
            account_was_approved=True,
            account_was_archived=False,
            account_was_deleted=False,
            licensed_resources=licensed_resources,
        )

        roles = []  # Empty list
        result = profile.with_roles(roles)

        # Should return a new profile with None licensed_resources (no matches)
        assert result.licensed_resources is None
        assert result.filtering_state == ["1:role:"]

    def test_with_roles_incremental_filtering_cascade(self):
        """Test incremental filtering state with roles as described in documentation"""
        # Start with empty filtering state
        profile = Profile(
            acc_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
            is_subscription=True,
            is_staff=False,
            owner_is_active=True,
            account_is_active=True,
            account_was_approved=True,
            account_was_archived=False,
            account_was_deleted=False,
            filtering_state=[],
        )

        # First filter: tenant
        tenant_id = UUID("123e4567-e89b-12d3-a456-426614174000")
        result1 = profile.on_tenant(tenant_id)
        assert result1.filtering_state == [f"1:tenantId:{tenant_id}"]

        # Second filter: roles (simulating permission filter would be "2:permission:1")
        roles = ["admin", "user"]
        result2 = result1.with_roles(roles)
        assert result2.filtering_state == [
            f"1:tenantId:{tenant_id}",
            "2:role:admin,user",
        ]

        # Third filter: more roles
        more_roles = ["manager"]
        result3 = result2.with_roles(more_roles)
        assert result3.filtering_state == [
            f"1:tenantId:{tenant_id}",
            "2:role:admin,user",
            "3:role:manager",
        ]

    def test_get_related_account_or_error_staff_privileges(self):
        """Test get_related_account_or_error with staff privileges"""
        profile = Profile(
            acc_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
            is_subscription=True,
            is_staff=True,
            is_manager=False,
            owner_is_active=True,
            account_is_active=True,
            account_was_approved=True,
            account_was_archived=False,
            account_was_deleted=False,
        )

        result = profile.get_related_account_or_error()

        assert result.type == "has_staff_privileges"
        assert hasattr(result, "type")

    def test_get_related_account_or_error_manager_privileges(self):
        """Test get_related_account_or_error with manager privileges"""
        profile = Profile(
            acc_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
            is_subscription=True,
            is_staff=False,
            is_manager=True,
            owner_is_active=True,
            account_is_active=True,
            account_was_approved=True,
            account_was_archived=False,
            account_was_deleted=False,
        )

        result = profile.get_related_account_or_error()

        assert result.type == "has_manager_privileges"
        assert hasattr(result, "type")

    def test_get_related_account_or_error_staff_over_manager(self):
        """Test that staff privileges take precedence over manager privileges"""
        profile = Profile(
            acc_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
            is_subscription=True,
            is_staff=True,  # Staff should take precedence
            is_manager=True,
            owner_is_active=True,
            account_is_active=True,
            account_was_approved=True,
            account_was_archived=False,
            account_was_deleted=False,
        )

        result = profile.get_related_account_or_error()

        assert result.type == "has_staff_privileges"
        assert hasattr(result, "type")

    def test_get_related_account_or_error_with_licensed_resources(self):
        """Test get_related_account_or_error with licensed resources"""
        account_id1 = UUID("11111111-1111-1111-1111-111111111111")
        account_id2 = UUID("22222222-2222-2222-2222-222222222222")
        tenant_id = UUID("33333333-3333-3333-3333-333333333333")
        role_id = UUID("44444444-4444-4444-4444-444444444444")

        licensed_resource1 = LicensedResource(
            acc_id=account_id1,
            sys_acc=False,
            tenant_id=tenant_id,
            role_id=role_id,
            acc_name="Account 1",
            role="user",
            perm=Permission.READ,
            verified=True,
        )

        licensed_resource2 = LicensedResource(
            acc_id=account_id2,
            sys_acc=False,
            tenant_id=tenant_id,
            role_id=role_id,
            acc_name="Account 2",
            role="admin",
            perm=Permission.WRITE,
            verified=True,
        )

        licensed_resources = LicensedResources(
            records=[licensed_resource1, licensed_resource2]
        )

        profile = Profile(
            acc_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
            is_subscription=True,
            is_staff=False,
            is_manager=False,
            owner_is_active=True,
            account_is_active=True,
            account_was_approved=True,
            account_was_archived=False,
            account_was_deleted=False,
            licensed_resources=licensed_resources,
        )

        result = profile.get_related_account_or_error()

        assert result.type == "allowed_accounts"
        assert len(result.accounts) == 2
        assert account_id1 in result.accounts
        assert account_id2 in result.accounts

    def test_get_related_account_or_error_empty_licensed_resources(self):
        """Test get_related_account_or_error with empty licensed resources"""
        from myc_http_tools.exceptions import InsufficientLicensesError

        licensed_resources = LicensedResources(records=[])

        profile = Profile(
            acc_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
            is_subscription=True,
            is_staff=False,
            is_manager=False,
            owner_is_active=True,
            account_is_active=True,
            account_was_approved=True,
            account_was_archived=False,
            account_was_deleted=False,
            licensed_resources=licensed_resources,
        )

        with pytest.raises(InsufficientLicensesError) as exc_info:
            profile.get_related_account_or_error()

        assert exc_info.value.code == "MYC00019"
        assert exc_info.value.exp_true is True
        assert "Insufficient licenses" in exc_info.value.message

    def test_get_related_account_or_error_none_licensed_resources(self):
        """Test get_related_account_or_error with None licensed resources"""
        from myc_http_tools.exceptions import InsufficientPrivilegesError

        profile = Profile(
            acc_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
            is_subscription=True,
            is_staff=False,
            is_manager=False,
            owner_is_active=True,
            account_is_active=True,
            account_was_approved=True,
            account_was_archived=False,
            account_was_deleted=False,
            filtering_state=["1:tenantId:123", "2:role:user"],
        )

        with pytest.raises(InsufficientPrivilegesError) as exc_info:
            profile.get_related_account_or_error()

        assert exc_info.value.code == "MYC00019"
        assert exc_info.value.exp_true is True
        assert "Insufficient privileges" in exc_info.value.message
        assert "no accounts" in exc_info.value.message
        assert exc_info.value.filtering_state == [
            "1:tenantId:123",
            "2:role:user",
        ]
        assert "1:tenantId:123, 2:role:user" in exc_info.value.message

    def test_get_related_account_or_error_no_privileges_empty_filtering_state(
        self,
    ):
        """Test get_related_account_or_error with no privileges and empty filtering state"""
        from myc_http_tools.exceptions import InsufficientPrivilegesError

        profile = Profile(
            acc_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
            is_subscription=True,
            is_staff=False,
            is_manager=False,
            owner_is_active=True,
            account_is_active=True,
            account_was_approved=True,
            account_was_archived=False,
            account_was_deleted=False,
        )

        with pytest.raises(InsufficientPrivilegesError) as exc_info:
            profile.get_related_account_or_error()

        assert exc_info.value.code == "MYC00019"
        assert exc_info.value.exp_true is True
        assert "Insufficient privileges" in exc_info.value.message
        assert "no accounts" in exc_info.value.message
        assert exc_info.value.filtering_state == []
        assert exc_info.value.message.endswith("(no accounts): ")

    def test_get_related_account_or_error_with_urls_licensed_resources(self):
        """Test get_related_account_or_error with URL-based licensed resources"""
        # Create a URL that will be parsed into a LicensedResource
        tenant_id = "123e4567-e89b-12d3-a456-426614174000"
        account_id = "987fcdeb-51a2-43d1-9f12-345678901234"
        role_id = "456e7890-e89b-12d3-a456-426614174567"
        role_name = "user"
        permission_code = "0"
        sys_value = "0"
        verified_value = "1"
        name_encoded = "dGVzdCBhY2NvdW50"  # "test account" in base64

        url = f"t/{tenant_id}/a/{account_id}/r/{role_id}?p={role_name}:{permission_code}&s={sys_value}&v={verified_value}&n={name_encoded}"

        licensed_resources = LicensedResources(urls=[url])

        profile = Profile(
            acc_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
            is_subscription=True,
            is_staff=False,
            is_manager=False,
            owner_is_active=True,
            account_is_active=True,
            account_was_approved=True,
            account_was_archived=False,
            account_was_deleted=False,
            licensed_resources=licensed_resources,
        )

        result = profile.get_related_account_or_error()

        assert result.type == "allowed_accounts"
        assert len(result.accounts) == 1
        assert result.accounts[0] == UUID(account_id)

    def test_get_related_account_or_error_priority_order(self):
        """Test that the priority order is correct: staff > manager > licensed resources"""
        account_id = UUID("11111111-1111-1111-1111-111111111111")
        tenant_id = UUID("33333333-3333-3333-3333-333333333333")
        role_id = UUID("44444444-4444-4444-4444-444444444444")

        licensed_resource = LicensedResource(
            acc_id=account_id,
            sys_acc=False,
            tenant_id=tenant_id,
            role_id=role_id,
            acc_name="Test Account",
            role="user",
            perm=Permission.READ,
            verified=True,
        )

        licensed_resources = LicensedResources(records=[licensed_resource])

        # Test 1: Staff should take precedence over everything
        profile_staff = Profile(
            acc_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
            is_subscription=True,
            is_staff=True,
            is_manager=True,  # Manager is True but staff should win
            owner_is_active=True,
            account_is_active=True,
            account_was_approved=True,
            account_was_archived=False,
            account_was_deleted=False,
            licensed_resources=licensed_resources,  # Licensed resources exist but staff should win
        )

        result = profile_staff.get_related_account_or_error()
        assert result.type == "has_staff_privileges"

        # Test 2: Manager should take precedence over licensed resources
        profile_manager = Profile(
            acc_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
            is_subscription=True,
            is_staff=False,
            is_manager=True,  # Manager is True
            owner_is_active=True,
            account_is_active=True,
            account_was_approved=True,
            account_was_archived=False,
            account_was_deleted=False,
            licensed_resources=licensed_resources,  # Licensed resources exist but manager should win
        )

        result = profile_manager.get_related_account_or_error()
        assert result.type == "has_manager_privileges"

        # Test 3: Licensed resources should be used when no staff/manager privileges
        profile_licensed = Profile(
            acc_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
            is_subscription=True,
            is_staff=False,
            is_manager=False,  # No staff/manager privileges
            owner_is_active=True,
            account_is_active=True,
            account_was_approved=True,
            account_was_archived=False,
            account_was_deleted=False,
            licensed_resources=licensed_resources,  # Licensed resources should be used
        )

        result = profile_licensed.get_related_account_or_error()
        assert result.type == "allowed_accounts"
        assert len(result.accounts) == 1
        assert result.accounts[0] == account_id

    def test_on_account_without_licensed_resources(self):
        """Test on_account without licensed resources"""
        profile = Profile(
            acc_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
            is_subscription=True,
            is_staff=False,
            is_manager=False,
            owner_is_active=True,
            account_is_active=True,
            account_was_approved=True,
            account_was_archived=False,
            account_was_deleted=False,
        )

        target_account_id = UUID("987fcdeb-51a2-43d1-9f12-345678901234")
        result = profile.on_account(target_account_id)

        # Should return a new profile with None licensed_resources
        assert result.licensed_resources is None
        assert result.filtering_state == [
            "1:accountId:987fcdeb-51a2-43d1-9f12-345678901234"
        ]
        assert result.acc_id == profile.acc_id  # Original profile unchanged

    def test_on_account_with_licensed_resources_no_matches(self):
        """Test on_account with licensed resources but no matches"""
        account_id1 = UUID("11111111-1111-1111-1111-111111111111")
        account_id2 = UUID("22222222-2222-2222-2222-222222222222")
        tenant_id = UUID("33333333-3333-3333-3333-333333333333")
        role_id = UUID("44444444-4444-4444-4444-444444444444")

        licensed_resource1 = LicensedResource(
            acc_id=account_id1,
            sys_acc=False,
            tenant_id=tenant_id,
            role_id=role_id,
            acc_name="Account 1",
            role="user",
            perm=Permission.READ,
            verified=True,
        )

        licensed_resource2 = LicensedResource(
            acc_id=account_id2,
            sys_acc=False,
            tenant_id=tenant_id,
            role_id=role_id,
            acc_name="Account 2",
            role="admin",
            perm=Permission.WRITE,
            verified=True,
        )

        licensed_resources = LicensedResources(
            records=[licensed_resource1, licensed_resource2]
        )

        profile = Profile(
            acc_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
            is_subscription=True,
            is_staff=False,
            is_manager=False,
            owner_is_active=True,
            account_is_active=True,
            account_was_approved=True,
            account_was_archived=False,
            account_was_deleted=False,
            licensed_resources=licensed_resources,
        )

        # Try to filter by an account that doesn't exist
        target_account_id_exists = UUID("11111111-1111-1111-1111-111111111111")
        target_account_id_not_exists = UUID(
            "88888888-8888-8888-8888-888888888888"
        )
        result_exists = profile.on_account(target_account_id_exists)
        result_not_exists = profile.on_account(target_account_id_not_exists)

        # Should return a new profile with None licensed_resources (no matches)
        assert result_exists.licensed_resources is not None
        assert len(result_exists.licensed_resources.to_licenses_vector()) == 1

        assert result_not_exists.licensed_resources is None

        assert result_exists.filtering_state == [
            "1:accountId:11111111-1111-1111-1111-111111111111"
        ]

        assert result_not_exists.filtering_state == [
            "1:accountId:88888888-8888-8888-8888-888888888888"
        ]

        assert (
            result_exists.acc_id == profile.acc_id
        )  # Original profile unchanged
        assert (
            result_not_exists.acc_id == profile.acc_id
        )  # Original profile unchanged

    def test_on_account_with_licensed_resources_with_matches(self):
        """Test on_account with licensed resources with matches"""
        account_id1 = UUID("11111111-1111-1111-1111-111111111111")
        account_id2 = UUID("22222222-2222-2222-2222-222222222222")
        tenant_id = UUID("33333333-3333-3333-3333-333333333333")
        role_id = UUID("44444444-4444-4444-4444-444444444444")

        licensed_resource1 = LicensedResource(
            acc_id=account_id1,
            sys_acc=False,
            tenant_id=tenant_id,
            role_id=role_id,
            acc_name="Account 1",
            role="user",
            perm=Permission.READ,
            verified=True,
        )

        licensed_resource2 = LicensedResource(
            acc_id=account_id2,
            sys_acc=False,
            tenant_id=tenant_id,
            role_id=role_id,
            acc_name="Account 2",
            role="admin",
            perm=Permission.WRITE,
            verified=True,
        )

        licensed_resources = LicensedResources(
            records=[licensed_resource1, licensed_resource2]
        )

        profile = Profile(
            acc_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
            is_subscription=True,
            is_staff=False,
            is_manager=False,
            owner_is_active=True,
            account_is_active=True,
            account_was_approved=True,
            account_was_archived=False,
            account_was_deleted=False,
            licensed_resources=licensed_resources,
        )

        # Filter by account_id1
        result = profile.on_account(account_id1)

        # Should return a new profile with filtered licensed resources
        assert result.licensed_resources is not None
        assert len(result.licensed_resources.to_licenses_vector()) == 1
        assert (
            result.licensed_resources.to_licenses_vector()[0].acc_id
            == account_id1
        )
        assert result.filtering_state == [f"1:accountId:{account_id1}"]
        assert result.acc_id == profile.acc_id  # Original profile unchanged

    def test_on_account_updates_filtering_state(self):
        """Test that on_account updates filtering state"""
        profile = Profile(
            acc_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
            is_subscription=True,
            is_staff=False,
            is_manager=False,
            owner_is_active=True,
            account_is_active=True,
            account_was_approved=True,
            account_was_archived=False,
            account_was_deleted=False,
            filtering_state=["existing_filter"],
        )

        target_account_id = UUID("987fcdeb-51a2-43d1-9f12-345678901234")
        result = profile.on_account(target_account_id)

        assert result.filtering_state == [
            "existing_filter",
            f"2:accountId:{target_account_id}",
        ]

    def test_on_account_adds_incremental_account_filter(self):
        """Test that on_account adds incremental account filter"""
        profile = Profile(
            acc_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
            is_subscription=True,
            is_staff=False,
            is_manager=False,
            owner_is_active=True,
            account_is_active=True,
            account_was_approved=True,
            account_was_archived=False,
            account_was_deleted=False,
            filtering_state=["1:tenantId:old-tenant-id"],
        )

        target_account_id = UUID("987fcdeb-51a2-43d1-9f12-345678901234")
        result = profile.on_account(target_account_id)

        assert result.filtering_state == [
            "1:tenantId:old-tenant-id",
            f"2:accountId:{target_account_id}",
        ]

    def test_on_account_incremental_filtering_cascade(self):
        """Test incremental filtering cascade with on_account"""
        profile = Profile(
            acc_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
            is_subscription=True,
            is_staff=False,
            is_manager=False,
            owner_is_active=True,
            account_is_active=True,
            account_was_approved=True,
            account_was_archived=False,
            account_was_deleted=False,
            filtering_state=[],
        )

        # First filter: tenant
        tenant_id = UUID("123e4567-e89b-12d3-a456-426614174000")
        result1 = profile.on_tenant(tenant_id)
        assert result1.filtering_state == [f"1:tenantId:{tenant_id}"]

        # Second filter: account
        account_id = UUID("987fcdeb-51a2-43d1-9f12-345678901234")
        result2 = result1.on_account(account_id)
        assert result2.filtering_state == [
            f"1:tenantId:{tenant_id}",
            f"2:accountId:{account_id}",
        ]

        # Third filter: roles
        roles = ["admin", "user"]
        result3 = result2.with_roles(roles)
        assert result3.filtering_state == [
            f"1:tenantId:{tenant_id}",
            f"2:accountId:{account_id}",
            "3:role:admin,user",
        ]

    def test_on_account_with_urls_licensed_resources(self):
        """Test on_account with URL-based licensed resources"""
        # Create a URL that will be parsed into a LicensedResource
        tenant_id = "123e4567-e89b-12d3-a456-426614174000"
        account_id = "987fcdeb-51a2-43d1-9f12-345678901234"
        role_id = "456e7890-e89b-12d3-a456-426614174567"
        role_name = "user"
        permission_code = "0"
        sys_value = "0"
        verified_value = "1"
        name_encoded = "dGVzdCBhY2NvdW50"  # "test account" in base64

        url = f"t/{tenant_id}/a/{account_id}/r/{role_id}?p={role_name}:{permission_code}&s={sys_value}&v={verified_value}&n={name_encoded}"

        licensed_resources = LicensedResources(urls=[url])

        profile = Profile(
            acc_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
            is_subscription=True,
            is_staff=False,
            is_manager=False,
            owner_is_active=True,
            account_is_active=True,
            account_was_approved=True,
            account_was_archived=False,
            account_was_deleted=False,
            licensed_resources=licensed_resources,
        )

        # Filter by the account ID from the URL
        target_account_id = UUID(account_id)
        result = profile.on_account(target_account_id)

        # Should return a new profile with filtered licensed resources
        assert result.licensed_resources is not None
        assert len(result.licensed_resources.to_licenses_vector()) == 1
        assert (
            result.licensed_resources.to_licenses_vector()[0].acc_id
            == target_account_id
        )
        assert result.filtering_state == [f"1:accountId:{target_account_id}"]

    def test_chained_methods_usage(self):
        """Test chained method calls as shown in the example format"""
        # Define global roles for testing
        __GLOBAL_ROLES = ["admin", "user"]

        # Create a customer ID for testing
        customer_id = UUID("987fcdeb-51a2-43d1-9f12-345678901234")

        # Create licensed resources for testing
        read_resource = LicensedResource(
            tenant_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
            acc_id=customer_id,
            role_id=UUID("456e7890-e89b-12d3-a456-426614174567"),
            role="admin",
            perm=Permission.READ,
            sys_acc=True,
            acc_name="Test Account",
            verified=True,
        )

        write_resource = LicensedResource(
            tenant_id=UUID("223e4567-e89b-12d3-a456-426614174001"),
            acc_id=UUID("887fcdeb-51a2-43d1-9f12-345678901235"),
            role_id=UUID("556e7890-e89b-12d3-a456-426614174568"),
            role="user",
            perm=Permission.WRITE,
            sys_acc=False,
            acc_name="Write Account",
            verified=False,
        )

        licensed_resources = LicensedResources(
            records=[read_resource, write_resource]
        )

        # Create initial profile
        profile = Profile(
            acc_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
            is_subscription=True,
            is_staff=False,
            is_manager=False,
            owner_is_active=True,
            account_is_active=True,
            account_was_approved=True,
            account_was_archived=False,
            account_was_deleted=False,
            licensed_resources=licensed_resources,
        )

        # Test the chained method calls as shown in the example
        profile.is_manager = False
        profile.is_staff = False

        # Step 0: Initial state
        assert profile.licensed_resources is not None
        assert len(profile.licensed_resources.records) == 2
        assert profile.filtering_state is None

        # Step 1: Filter by account
        profile = profile.on_account(customer_id)
        assert profile.licensed_resources is not None
        assert len(profile.licensed_resources.records) == 1
        assert profile.licensed_resources.records[0].acc_id == customer_id
        assert profile.filtering_state == [f"1:accountId:{customer_id}"]

        # Step 2: Filter by read access
        profile = profile.with_read_access()
        assert profile.licensed_resources is not None
        assert len(profile.licensed_resources.records) == 1
        assert profile.licensed_resources.records[0].perm == Permission.READ
        assert profile.licensed_resources.urls is None  # URLs should be cleared

        # Step 3: Filter by roles
        profile = profile.with_roles(__GLOBAL_ROLES)
        assert profile.licensed_resources is not None
        assert len(profile.licensed_resources.records) == 1
        assert profile.licensed_resources.records[0].role == "admin"
        assert profile.filtering_state == [
            f"1:accountId:{customer_id}",
            "2:permission:0",
            "3:role:admin,user",
        ]

        # Step 4: Get related accounts
        related_accounts = profile.get_related_account_or_error()
        assert related_accounts.type == "allowed_accounts"
        assert len(related_accounts.accounts) == 1
        assert related_accounts.accounts[0] == customer_id

    def test_chained_methods_with_no_matches(self):
        """Test chained method calls when filters result in no matches"""
        # Define global roles for testing
        __GLOBAL_ROLES = ["admin", "user"]

        # Create a customer ID that won't match any resources
        customer_id = UUID("99999999-9999-9999-9999-999999999999")

        # Create licensed resources for a different account
        read_resource = LicensedResource(
            tenant_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
            acc_id=UUID(
                "11111111-1111-1111-1111-111111111111"
            ),  # Different account
            role_id=UUID("456e7890-e89b-12d3-a456-426614174567"),
            role="admin",
            perm=Permission.READ,
            sys_acc=True,
            acc_name="Test Account",
            verified=True,
        )

        licensed_resources = LicensedResources(records=[read_resource])

        # Create initial profile
        profile = Profile(
            acc_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
            is_subscription=True,
            is_staff=False,
            is_manager=False,
            owner_is_active=True,
            account_is_active=True,
            account_was_approved=True,
            account_was_archived=False,
            account_was_deleted=False,
            licensed_resources=licensed_resources,
        )

        # Test the chained method calls
        profile.is_manager = False
        profile.is_staff = False

        # Step 1: Filter by account (no matches)
        profile = profile.on_account(customer_id)
        assert profile.licensed_resources is None  # No matches
        assert profile.filtering_state == [f"1:accountId:{customer_id}"]

        # Step 2: Filter by read access (still no matches)
        profile = profile.with_read_access()
        assert profile.licensed_resources is None  # Still no matches

        # Step 3: Filter by roles (still no matches)
        profile = profile.with_roles(__GLOBAL_ROLES)
        assert profile.licensed_resources is None  # Still no matches
        # The permission filter is now recorded even with no matches (gateway
        # behavior, no short-circuit).
        assert profile.filtering_state == [
            f"1:accountId:{customer_id}",
            "2:permission:0",
            "3:role:admin,user",
        ]

        # Step 4: Get related accounts should raise an error
        from myc_http_tools.exceptions import InsufficientPrivilegesError

        with pytest.raises(InsufficientPrivilegesError) as exc_info:
            profile.get_related_account_or_error()

        assert exc_info.value.code == "MYC00019"
        assert "Insufficient privileges" in exc_info.value.message
        assert "no accounts" in exc_info.value.message

    def test_chained_methods_with_staff_privileges(self):
        """Test chained method calls with staff privileges (should bypass licensed resources)"""
        # Define global roles for testing
        __GLOBAL_ROLES = ["admin", "user"]

        # Create a customer ID
        customer_id = UUID("987fcdeb-51a2-43d1-9f12-345678901234")

        # Create licensed resources
        read_resource = LicensedResource(
            tenant_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
            acc_id=customer_id,
            role_id=UUID("456e7890-e89b-12d3-a456-426614174567"),
            role="admin",
            perm=Permission.READ,
            sys_acc=True,
            acc_name="Test Account",
            verified=True,
        )

        licensed_resources = LicensedResources(records=[read_resource])

        # Create initial profile with staff privileges
        profile = Profile(
            acc_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
            is_subscription=True,
            is_staff=True,  # Staff privileges
            is_manager=False,
            owner_is_active=True,
            account_is_active=True,
            account_was_approved=True,
            account_was_archived=False,
            account_was_deleted=False,
            licensed_resources=licensed_resources,
        )

        # Test the chained method calls
        profile.is_manager = False
        # Note: is_staff is already True, but we can test the chain

        # Step 1: Filter by account
        profile = profile.on_account(customer_id)
        assert profile.licensed_resources is not None
        assert len(profile.licensed_resources.records) == 1

        # Step 2: Filter by read access
        profile = profile.with_read_access()
        assert profile.licensed_resources is not None
        assert len(profile.licensed_resources.records) == 1

        # Step 3: Filter by roles
        profile = profile.with_roles(__GLOBAL_ROLES)
        assert profile.licensed_resources is not None
        assert len(profile.licensed_resources.records) == 1

        # Step 4: Get related accounts should return staff privileges (bypasses licensed resources)
        related_accounts = profile.get_related_account_or_error()
        assert related_accounts.type == "has_staff_privileges"
