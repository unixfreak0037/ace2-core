# vim: ts=4:sw=4:et:cc=120
#
# defines the core system object
# a system is an object that extends all of these interfaces
#

from ace.crypto import EncryptionSettings

from ace.system.base import (
    AlertingBaseInterface,
    AnalysisModuleTrackingBaseInterface,
    AnalysisTrackingBaseInterface,
    AnalysisRequestTrackingBaseInterface,
    CachingBaseInterface,
    ConfigurationBaseInterface,
    EventBaseInterface,
    StorageBaseInterface,
    WorkQueueBaseInterface,
    AuthenticationBaseInterface,
    AuditTrackingBaseInterface,
    TokenizationBaseInterface,
)


class ACESystem(
    AlertingBaseInterface,
    AnalysisTrackingBaseInterface,
    AnalysisModuleTrackingBaseInterface,
    AnalysisRequestTrackingBaseInterface,
    CachingBaseInterface,
    ConfigurationBaseInterface,
    EventBaseInterface,
    StorageBaseInterface,
    WorkQueueBaseInterface,
    AuthenticationBaseInterface,
    AuditTrackingBaseInterface,
    TokenizationBaseInterface,
):

    # the encryption settings for this system
    # encryption is not enabled by default
    encryption_settings: EncryptionSettings

    def new_root(self, *args, **kwargs):
        """Returns a new RootAnalysis object for this system."""
        from ace.analysis import RootAnalysis

        return RootAnalysis(system=self, *args, **kwargs)

    async def reset(self):
        """Resets the system. Useful for unit testing."""
        pass

    # should be called before start() is called
    async def initialize(self):
        """Called once when the system is first created.
        Be sure to call await super().initialize if you override this method."""
        pass

    # called to start the system
    async def start(self):
        """Called once as the system begins execution.
        Be sure to call await super().initialize if you override this method."""
        pass

    # called to stop the system
    async def stop(self):
        """Called once when the system is being shut down.
        Extend this to"""
        pass
