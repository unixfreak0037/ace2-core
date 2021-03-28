# vim: ts=4:sw=4:et:cc=120
#
# defines the core system object
# a system is an object that extends all of these interfaces
#

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
    EncryptionBaseInterface,
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
    EncryptionBaseInterface,
    TokenizationBaseInterface,
):
    def new_root(self, *args, **kwargs):
        """Returns a new RootAnalysis object for this system."""
        from ace.analysis import RootAnalysis

        return RootAnalysis(system=self, *args, **kwargs)

    # XXX reset is really just for unit testing
    async def reset(self):
        pass

    # should be called before start() is called
    async def initialize(self):
        pass

    # called to start the system
    def start(self):
        pass

    # called to stop the system
    def stop(self):
        pass
