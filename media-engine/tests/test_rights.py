import unittest

from media_engine.models import PUBLISH_AUTO, PUBLISH_REVIEW_REQUIRED, STATUS_APPROVED
from media_engine.rights import can_auto_publish, can_publish_candidate


class RightsGuardTests(unittest.TestCase):
    def test_public_third_party_cannot_auto_publish(self):
        source = {"permission_status": "public_third_party", "permission_evidence": ""}
        target = {"mode": PUBLISH_AUTO}
        result = can_auto_publish(source, target)
        self.assertFalse(result.allowed)
        self.assertIn("public third-party", result.reason)

    def test_authorized_community_requires_evidence_for_auto_publish(self):
        source = {"permission_status": "authorized_community", "permission_evidence": ""}
        target = {"mode": PUBLISH_AUTO}
        result = can_auto_publish(source, target)
        self.assertFalse(result.allowed)
        self.assertIn("evidence", result.reason)

    def test_authorized_community_with_evidence_can_auto_publish(self):
        source = {"permission_status": "authorized_community", "permission_evidence": "email approval 2026-05-09"}
        target = {"mode": PUBLISH_AUTO}
        result = can_auto_publish(source, target)
        self.assertTrue(result.allowed)

    def test_review_required_needs_approval(self):
        source = {"permission_status": "authorized_community", "permission_evidence": "email approval 2026-05-09"}
        target = {"mode": PUBLISH_REVIEW_REQUIRED, "require_approval": 1}
        candidate = {"status": "rendered"}
        result = can_publish_candidate(source, target, candidate)
        self.assertFalse(result.allowed)
        self.assertIn("approved", result.reason)

    def test_review_required_blocks_public_third_party_even_when_approved(self):
        source = {"permission_status": "public_third_party", "permission_evidence": ""}
        target = {"mode": PUBLISH_REVIEW_REQUIRED, "require_approval": 1}
        candidate = {"status": STATUS_APPROVED}
        result = can_publish_candidate(source, target, candidate)
        self.assertFalse(result.allowed)
        self.assertIn("permission evidence", result.reason)

    def test_review_required_allows_authorized_approved_candidate(self):
        source = {"permission_status": "authorized_community", "permission_evidence": "email approval 2026-05-09"}
        target = {"mode": PUBLISH_REVIEW_REQUIRED, "require_approval": 1}
        candidate = {"status": STATUS_APPROVED}
        result = can_publish_candidate(source, target, candidate)
        self.assertTrue(result.allowed)


if __name__ == "__main__":
    unittest.main()
