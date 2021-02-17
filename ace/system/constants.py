# vim: ts=4:sw=4:et:cc=120

# supported tracking systems
TRACKING_SYSTEM_ANALYSIS_MODULE_TYPES = "analysis_module_types"
TRACKING_SYSTEM_ANALYSIS_REQUESTS = "analysis_requests"
TRACKING_SYSTEM_ANALYSIS_REQUEST_ASSIGNMENTS = "analysis_request_assignments"
TRACKING_SYSTEM_ROOT_ANALYSIS = "root_analysis"
TRACKING_SYSTEM_ANALYSIS = "analysis"

# analyis status
TRACKING_STATUS_NEW = "new"
TRACKING_STATUS_QUEUED = "queued"
TRACKING_STATUS_ANALYZING = "analyzing"
TRACKING_STATUS_PROCESSING = "processing"
TRACKING_STATUS_FINISHED = "finished"
TRACKING_STATUS_EXPIRED = "expired"

# system-level locks
# TODO these locks should not be acquire-able externally
SYSTEM_LOCK_EXPIRED_ANALYSIS_REQUESTS = "ace:expired_analysis_requests"

# supported events
# analysis tracking
EVENT_ANALYSIS_ROOT_NEW = "/core/analysis/root/new"
EVENT_ANALYSIS_ROOT_MODIFIED = "/core/analysis/root/modified"
EVENT_ANALYSIS_ROOT_EXPIRED = "/core/analysis/root/expired"
EVENT_ANALYSIS_ROOT_DELETED = "/core/analysis/root/deleted"
# analysis details tracking
EVENT_ANALYSIS_DETAILS_NEW = "/core/analysis/details/new"
EVENT_ANALYSIS_DETAILS_MODIFIED = "/core/analysis/details/modified"
EVENT_ANALYSIS_DETAILS_DELETED = "/core/analysis/details/deleted"
# alerting
EVENT_ALERT = "/core/alert/new"
EVENT_ALERT_SYSTEM_REGISTERED = "/core/alert/system/registered"
EVENT_ALERT_SYSTEM_UNREGISTERED = "/core/alert/system/unregistered"
# analysis module tracking
EVENT_AMT_NEW = "/core/module/new"
EVENT_AMT_MODIFIED = "/core/module/modified"
EVENT_AMT_DELETED = "/core/module/deleted"
# analysis request tracking
EVENT_AR_NEW = "/core/request/new"
EVENT_AR_DELETED = "/core/request/deleted"
EVENT_AR_EXPIRED = "/core/request/expired"
# caching
EVENT_CACHE_NEW = "/core/cache/new"
EVENT_CACHE_HIT = "/core/cache/hit"
# config
EVENT_CONFIG_SET = "/core/config/set"
EVENT_CONFIG_DELETE = "/core/config/delete"
# storage
EVENT_STORAGE_NEW = "/core/storage/new"
EVENT_STORAGE_DELETED = "/core/storage/deleted"
# work queues
EVENT_WORK_QUEUE_NEW = "/core/work/queue/new"
EVENT_WORK_QUEUE_DELETED = "/core/work/queue/deleted"
EVENT_WORK_ADD = "/core/work/add"
EVENT_WORK_REMOVE = "/core/work/remove"
EVENT_WORK_ASSIGNED = "/core/work/assigned"
# processing
EVENT_PROCESSING_REQUEST_OBSERVABLE = "/core/processing/request/observable"
EVENT_PROCESSING_REQUEST_ROOT = "/core/processing/request/root"
EVENT_PROCESSING_REQUEST_RESULT = "/core/processing/request/result"
