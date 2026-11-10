import unittest
from unittest.mock import patch
from uuid import uuid4

from fastapi import HTTPException

from backend.agency_os_security import (
    ContactCreate,
    require_agency_membership,
    verify_supabase_access_token,
)


class SecureTenantFoundationTests(unittest.TestCase):
    def test_missing_bearer_token_fails_closed(self):
        with self.assertRaises(HTTPException) as raised:
            verify_supabase_access_token(None)
        self.assertEqual(raised.exception.status_code, 401)

    def test_bearer_token_is_validated_by_supabase_auth(self):
        user_id = str(uuid4())
        with patch("backend.agency_os_security._auth_config", return_value=("https://example.supabase.co", "anon")):
            with patch("backend.agency_os_security.urllib.request.urlopen") as open_url:
                class Response:
                    def __enter__(self): return self
                    def __exit__(self, *args): return False
                    def read(self): return ('{"id":"' + user_id + '","email":"agent@example.com"}').encode()
                open_url.return_value = Response()
                result = verify_supabase_access_token("Bearer verified-token")
        self.assertEqual(result["id"], user_id)
        request = open_url.call_args.args[0]
        self.assertEqual(request.get_header("Authorization"), "Bearer verified-token")

    def test_read_only_member_cannot_write(self):
        agency_id = uuid4()
        user = {"id": str(uuid4())}
        membership = {"agency_id": str(agency_id), "user_id": user["id"], "role": "read_only", "status": "active"}
        with patch("backend.agency_os_security._database_connection") as connect:
            connection = connect.return_value
            cursor = connection.cursor.return_value.__enter__.return_value
            cursor.fetchone.return_value = membership
            with self.assertRaises(HTTPException) as raised:
                require_agency_membership(agency_id, user, write=True)
        self.assertEqual(raised.exception.status_code, 403)

    def test_user_without_agency_membership_is_denied(self):
        agency_id = uuid4()
        user = {"id": str(uuid4())}
        with patch("backend.agency_os_security._database_connection") as connect:
            connection = connect.return_value
            cursor = connection.cursor.return_value.__enter__.return_value
            cursor.fetchone.return_value = None
            with self.assertRaises(HTTPException) as raised:
                require_agency_membership(agency_id, user)
        self.assertEqual(raised.exception.status_code, 404)

    def test_contact_payload_rejects_blank_first_name(self):
        with self.assertRaises(ValueError):
            ContactCreate(first_name="   ")

    def test_contact_payload_rejects_invalid_preferred_method(self):
        with self.assertRaises(ValueError):
            ContactCreate(first_name="Sam", preferred_contact_method="fax")


if __name__ == "__main__":
    unittest.main()
