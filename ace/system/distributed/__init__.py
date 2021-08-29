# vim: ts=4:sw=4:et:cc=120
#
from ace.system.distributed.application import (
    app,
    verify_admin_api_key,
    TAG_ALERTS,
    TAG_AUTH,
    TAG_ANALYSIS_MODULE,
    TAG_ANALYSIS_REQUEST,
    TAG_ANALYSIS_TRACKING,
    TAG_CONFIG,
    TAG_STORAGE,
    TAG_WORK_QUEUE,
)

# importing these modules is what ends up loading the routes
import ace.system.distributed.alerting
import ace.system.distributed.analysis_tracking
import ace.system.distributed.auth
import ace.system.distributed.config
import ace.system.distributed.module_tracking
import ace.system.distributed.request_tracking
import ace.system.distributed.storage
import ace.system.distributed.work_queue
