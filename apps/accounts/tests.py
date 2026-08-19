from django.db import IntegrityError
from django.test import TestCase

from .models import Membership, Organization, User
from .permissions import get_role, has_role


class MembershipTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Acme", slug="acme")
        self.user = User.objects.create_user(email="a@example.com", password="pw")

    def test_unique_membership_per_org(self):
        Membership.objects.create(user=self.user, organization=self.org, role=Membership.Role.VIEWER)
        with self.assertRaises(IntegrityError):
            Membership.objects.create(user=self.user, organization=self.org, role=Membership.Role.EDITOR)

    def test_get_role_returns_none_without_membership(self):
        self.assertIsNone(get_role(self.user, self.org))

    def test_get_role_returns_role(self):
        Membership.objects.create(user=self.user, organization=self.org, role=Membership.Role.EDITOR)
        self.assertEqual(get_role(self.user, self.org), Membership.Role.EDITOR)

    def test_has_role_restricts_to_given_roles(self):
        Membership.objects.create(user=self.user, organization=self.org, role=Membership.Role.VIEWER)
        self.assertTrue(has_role(self.user, self.org))
        self.assertFalse(has_role(self.user, self.org, Membership.Role.ADMIN))
        self.assertTrue(has_role(self.user, self.org, Membership.Role.VIEWER, Membership.Role.ADMIN))

    def test_has_role_false_for_other_organization(self):
        other_org = Organization.objects.create(name="Other", slug="other")
        Membership.objects.create(user=self.user, organization=self.org, role=Membership.Role.ADMIN)
        self.assertFalse(has_role(self.user, other_org))
