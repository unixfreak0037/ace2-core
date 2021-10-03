# Development Notes

*Why is there a coupling between the RemoteAPI and ACESystem?*

Originally there was just one global system reference. When testing the client/server system, there are actually two systems: the local stub system and the remote system. So it was impossible to run both at the same time for testing because they both changed what the global reference pointed to.

*Why not just use the api directly? Why have a RemoteACESystem that uses the api?*

This system can also be used locally for manual (command line) analysis. I want it to work the same no matter what system is actually being used.