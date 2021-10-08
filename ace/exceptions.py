# vim: ts=4:sw=4:et:cc=120

from ace.constants import (
    ERROR_AMS_UNKNOWN,
    ERROR_AMT_CIRC,
    ERROR_AMT_DEP,
    ERROR_AMT_EXTENDED_VERSION,
    ERROR_AMT_UNKNOWN,
    ERROR_AMT_VERSION,
    ERROR_AR_EXPIRED,
    ERROR_AR_LOCKED,
    ERROR_AR_UNKNOWN,
    ERROR_AUTH_DUPLICATE_API_KEY_NAME,
    ERROR_AUTH_INVALID_ACCESS,
    ERROR_AUTH_INVALID_API_KEY,
    ERROR_AUTH_INVALID_PASSWORD,
    ERROR_AUTH_MISSING_ENCRYPTION_SETTINGS,
    ERROR_OBS_UNKNOWN,
    ERROR_ROOT_EXISTS,
    ERROR_ROOT_UNKNOWN,
    ERROR_STORE_UNKNOWN_FILE,
    ERROR_WQ_INVALID,
)


class ACEError(Exception):
    code = None


class AnalysisRequestLockedError(ACEError):
    """Raised when process_analysis_request is unable to lock the request."""

    code = ERROR_AR_LOCKED


class InvalidWorkQueueError(ACEError):
    """Raised when a request to an invalid work queue is made."""

    code = ERROR_WQ_INVALID


class UnknownAnalysisRequestError(ACEError):
    code = ERROR_AR_UNKNOWN


class ExpiredAnalysisRequestError(ACEError):
    code = ERROR_AR_EXPIRED


class UnknownObservableError(ACEError):
    """Raised when there is an attempt to modify an unknown Observable object."""

    code = ERROR_OBS_UNKNOWN


class RootAnalysisExistsError(ACEError):
    """Raised when there is an attempt to track an existing RootAnalysis object."""

    code = ERROR_ROOT_EXISTS

    # def __init__(self, uuid: str):
    # super().__init__(f"RootAnalysis {uuid} is already tracked")


class UnknownAlertSystemError(ACEError):
    code = ERROR_AMS_UNKNOWN


class UnknownAnalysisModuleTypeError(ACEError):
    """Raised when a request is made for an unknown (unregistered analysis module type.)"""

    code = ERROR_AMT_UNKNOWN

    # def __init__(self, amt: Union[AnalysisModuleType, str]):
    # super().__init__(f"unknown AnalysisModuleType {amt}")


class AnalysisModuleTypeDependencyError(ACEError):
    """Raised when a request is made to register a module with a dependency on an unknown module."""

    code = ERROR_AMT_DEP

    # def __init__(self, amt: Union[AnalysisModuleType, str], dep: str):
    # super().__init__(f"invalid dependency for {amt}: {dep}")


class CircularDependencyError(Exception):
    """Raised when there is an attempt to register a type that would cause a circular dependency."""

    code = ERROR_AMT_CIRC

    # def __init__(self, chain: list[AnalysisModuleType]):
    # super().__init__("circular dependency error: {}".format(" -> ".join([_.name for _ in chain])))


class AnalysisModuleTypeVersionError(Exception):
    """Raised when a request for a analysis with an out-of-date version is made."""

    code = ERROR_AMT_VERSION


class AnalysisModuleTypeExtendedVersionError(Exception):
    """Raised when a request for a analysis with an out-of-date extended version is made."""

    code = ERROR_AMT_EXTENDED_VERSION


class UnknownRootAnalysisError(ValueError):
    """Raised when there is an attempt to modify an unknown RootAnalysis object."""

    code = ERROR_ROOT_UNKNOWN

    # def __init__(self, uuid: str):
    # super().__init__(f"unknown RootAnalysis {uuid}")


class MissingEncryptionSettingsError(RuntimeError):
    """Raised when an attempt to perform an operation requiring crypto is
    attempted before encryption settings are available."""

    code = ERROR_AUTH_MISSING_ENCRYPTION_SETTINGS


class InvalidPasswordError(Exception):
    """Thrown when an invalid password is provided."""

    code = ERROR_AUTH_INVALID_PASSWORD


class DuplicateApiKeyNameError(Exception):
    """An attempt was made to create an api key that already exists."""

    code = ERROR_AUTH_DUPLICATE_API_KEY_NAME


class InvalidApiKeyError(Exception):
    """A request was made with an invalid api key."""

    code = ERROR_AUTH_INVALID_API_KEY


class InvalidAccessError(Exception):
    """A request was made for an operation that requires an admin api key."""

    code = ERROR_AUTH_INVALID_ACCESS


class UnknownFileError(Exception):
    """A request was made to retrieve an unknown file."""

    code = ERROR_STORE_UNKNOWN_FILE


exception_map = {
    ERROR_AMS_UNKNOWN: UnknownAlertSystemError,
    ERROR_AMT_CIRC: CircularDependencyError,
    ERROR_AMT_DEP: AnalysisModuleTypeDependencyError,
    ERROR_AMT_EXTENDED_VERSION: AnalysisModuleTypeExtendedVersionError,
    ERROR_AMT_UNKNOWN: UnknownAnalysisModuleTypeError,
    ERROR_AMT_VERSION: AnalysisModuleTypeVersionError,
    ERROR_AR_EXPIRED: ExpiredAnalysisRequestError,
    ERROR_AR_LOCKED: AnalysisRequestLockedError,
    ERROR_AR_UNKNOWN: UnknownAnalysisRequestError,
    ERROR_AUTH_DUPLICATE_API_KEY_NAME: DuplicateApiKeyNameError,
    ERROR_AUTH_INVALID_ACCESS: InvalidAccessError,
    ERROR_AUTH_INVALID_API_KEY: InvalidApiKeyError,
    ERROR_AUTH_INVALID_PASSWORD: InvalidPasswordError,
    ERROR_AUTH_MISSING_ENCRYPTION_SETTINGS: MissingEncryptionSettingsError,
    ERROR_OBS_UNKNOWN: UnknownObservableError,
    ERROR_ROOT_EXISTS: RootAnalysisExistsError,
    ERROR_ROOT_UNKNOWN: UnknownRootAnalysisError,
    ERROR_STORE_UNKNOWN_FILE: UnknownFileError,
    ERROR_WQ_INVALID: InvalidWorkQueueError,
}

#
# all the exceptions defined below are not used by the api
#


class UnknownServiceError(Exception):
    """Thrown when a reference is made to an unknown service."""

    pass


class ServiceAlreadyRunningError(Exception):
    """Thrown when we try to start a service that is already running."""

    pass


class ServiceDisabledError(Exception):
    """Thrown when we try to start a service that is disabled."""

    pass


class InvalidServiceStateError(Exception):
    """Thrown when an attempt is made to execute something against a service
    when the service is in the wrong state."""

    pass
