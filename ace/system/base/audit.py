# vim: ts=4:sw=4:et:cc=120
#
#
#


class AuditTrackingBaseInterface:
    async def audit(self, action: str, user: str, details: str):
        """Appends the given action and user (and optional details) to the audit log."""
        raise NotImplementedError()
