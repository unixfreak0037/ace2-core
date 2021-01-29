# vim: sw=4:ts=4:et:cc=120
#

from ace.api.base import AceAPI

# global reference to api connection
global_ace_api = None


def get_api() -> AceAPI:
    return global_ace_api


def set_api(api: AceAPI):
    assert isinstance(api, AceAPI)
    global global_ace_api
    global_ace_api = api
