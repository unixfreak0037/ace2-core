# vim: ts=4:sw=4:et:cc=120
#

import copy
import logging

from ace.analysis import recurse_tree
from ace.system import ACESystemInterface, get_system
from ace.system.alerting import track_alert
from ace.system.analysis_tracking import (
    UnknownRootAnalysisError,
    delete_root_analysis,
    get_root_analysis,
    track_root_analysis,
)
from ace.system.analysis_request import (
    AnalysisRequest,
    delete_analysis_request,
    get_analysis_request,
    get_analysis_request_by_observable,
    get_analysis_requests_by_root,
    get_linked_analysis_requests,
    link_analysis_requests,
    submit_analysis_request,
    track_analysis_request,
)
from ace.system.analysis_module import get_all_analysis_module_types
from ace.system.caching import cache_analysis_result, get_cached_analysis_result
from ace.system.constants import (
    EVENT_ANALYSIS_ROOT_EXPIRED,
    EVENT_CACHE_HIT,
    EVENT_PROCESSING_REQUEST_ROOT,
    EVENT_PROCESSING_REQUEST_OBSERVABLE,
    EVENT_PROCESSING_REQUEST_RESULT,
)
from ace.system.events import fire_event
from ace.system.exceptions import (
    UnknownAnalysisRequest,
    ExpiredAnalysisRequest,
    UnknownObservableError,
)


def process_analysis_request(ar: AnalysisRequest):
    """Processes an analysis request.
    This function implements the core logic of the system."""

    # need to lock this at the beginning so that nothing else modifies it
    # while we're processing it
    # TODO how long do we wait?
    with ar.root.lock():
        target_root = None
        # did we complete a request?
        if ar.is_observable_analysis_result:
            existing_ar = get_analysis_request(ar.id)

            # is this analysis request gone?
            if not existing_ar:
                logging.info(f"requested unknown analysis request {ar.id}")
                raise UnknownAnalysisRequest(ar)

            # did the ownership change?
            if existing_ar.owner != ar.owner:
                logging.info(f"requested expired analysis request {ar.id}")
                raise ExpiredAnalysisRequest(ar)

            # get the existing root analysis
            target_root = get_root_analysis(ar.root)
            if not target_root:
                logging.info(f"analysis request {ar.id} referenced unknown root {ar.root}")
                raise UnknownRootAnalysisError(ar)

            # should we cache these results?
            if ar.is_cachable and not ar.cache_hit:
                cache_analysis_result(ar)

            # NOTE
            # when applying the diff merge it is super important to use the data from the analysis request
            # and *not* the current data

            for _ in range(100):  # safer way to do while True

                # apply any modifications to the root
                target_root.apply_diff_merge(ar.original_root, ar.modified_root)

                # and apply any modifications to the observable
                target_observable = target_root.get_observable(ar.observable)
                if not target_observable:
                    logging.error(f"cannot find {ar.observable} in target root {target_root}")
                    raise UnknownObservableError(ar.observable)

                original_observable = ar.original_root.get_observable(ar.observable)
                if not original_observable:
                    logging.error(f"cannot find {ar.observable} in original root {ar.original_root}")
                    raise UnknownObservableError(ar.observable)

                modified_observable = ar.modified_root.get_observable(ar.observable)
                if not modified_observable:
                    logging.error(f"cannot find {ar.observable} in modified root {ar.modified_root}")
                    raise UnknownObservableError(ar.observable)

                target_observable.apply_diff_merge(original_observable, modified_observable, ar.type)
                if target_root.save():
                    break

                # if the save failed it means (assuming everything is working
                # correctly) that the root was modified by another process
                # in this case we get the latest version and try again
                updated_root = get_root_analysis(target_root)
                if not updated_root:
                    raise UnknownRootAnalysisError(ar)

                # if the reason that it failed is NOT because of a version difference
                # then that means something else is wrong, no need to keep trying
                if updated_root.version == target_root.version:
                    raise RuntimeError("RootAnalysis.save() failed but version matches -- check logs for issues")

                # otherwise we try again with an updated version of the root analysis
                # TODO metrics
                logging.debug("version mismatch for {target_root} during processing")
                target_root = updated_root

            else:
                # something is wrong with the system or logic
                raise RuntimeError("loop iterations exceeded")

            fire_event(EVENT_PROCESSING_REQUEST_RESULT, ar)
            # TODO fire event if analysis failed

            # process any analysis request links
            for linked_request in get_linked_analysis_requests(ar):
                linked_request.initialize_result()
                linked_request.original_root = ar.original_root
                linked_request.modified_root = ar.modified_root
                logging.debug(f"processing linked analysis request {linked_request} from {ar}")
                process_analysis_request(linked_request)

        elif ar.is_root_analysis_request:
            for _ in range(100):  # safer way to do while True
                # are we updating an existing root analysis?
                target_root = get_root_analysis(ar.root)
                if target_root:
                    target_root.apply_merge(ar.root)
                else:
                    # otherwise we just save the new one
                    target_root = ar.root

                if not target_root.save():
                    logging.debug("version mismatch for {target_root} during processing")
                    continue

                fire_event(EVENT_PROCESSING_REQUEST_ROOT, ar)
                break
            else:
                # something is wrong with the system or logic
                raise RuntimeError("loop iterations exceeded")

        # this should never fire
        if target_root is None:
            logging.critical("hit unexpected code branch")
            raise RuntimeError("target_root is None")

        # did we generate an alert?
        if not target_root.analysis_cancelled and target_root.has_detections():
            track_alert(target_root)

        # for each observable that needs to be analyzed
        if not target_root.analysis_cancelled:
            logging.debug(f"processing {target_root}")
            for observable in ar.observables:
                for amt in get_all_analysis_module_types():
                    # does this analysis module accept this observable?
                    if not amt.accepts(observable):
                        continue

                    # is this analysis request already completed?
                    if target_root.analysis_completed(observable, amt):
                        continue

                    # is this analysis request for this RootAnalysis already being tracked?
                    if target_root.analysis_tracked(observable, amt):
                        continue

                    # is this observable being analyzed by another root analysis?
                    # NOTE if the analysis module does not support caching
                    # then get_analysis_request_by_observable always returns None
                    tracked_ar = get_analysis_request_by_observable(observable, amt)
                    if tracked_ar and tracked_ar != ar:
                        try:
                            # see if we can lock the other request
                            with tracked_ar.lock():
                                if get_analysis_request(tracked_ar.id):
                                    #
                                    # Analysis Request Linking
                                    #
                                    # if we can get the AR and lock it it means it's still in a queue waiting
                                    # so we can tell that AR to update the details of this analysis as well when it's done

                                    # we create a new analysis request
                                    new_ar = observable.create_analysis_request(amt)
                                    track_analysis_request(new_ar)
                                    observable.track_analysis_request(new_ar)
                                    link_analysis_requests(tracked_ar, new_ar)
                                    track_analysis_request(new_ar)
                                    target_root.save()
                                    # and then that's it for this request
                                    # it waits for tracked_ar to complete
                                    continue

                            # the AR was completed before we could lock it
                            # oh well -- it could be in the cache

                        except Exception as e:  # TODO what can be thrown here?
                            raise e
                            # logging.fatal(f"unknown error: {e}")
                            # breakpoint()  # XXX if debug
                            # continue

                    # is this analysis in the cache?
                    cached_result = get_cached_analysis_result(observable, amt)
                    if cached_result:
                        logging.debug(
                            f"using cached result {cached_result} for {observable} type {amt} in {target_root}"
                        )

                        new_ar = observable.create_analysis_request(amt)
                        new_ar.original_root = cached_result.original_root
                        new_ar.modified_root = cached_result.modified_root
                        new_ar.cache_hit = True
                        track_analysis_request(new_ar)
                        observable.track_analysis_request(new_ar)
                        target_root.save()
                        fire_event(EVENT_CACHE_HIT, target_root, observable, new_ar)
                        process_analysis_request(new_ar)
                        continue

                    # otherwise we need to request it
                    logging.info(
                        f"creating new analysis request for observable {observable} amt {amt} root {target_root}"
                    )
                    new_ar = observable.create_analysis_request(amt)
                    # (we also track the request inside the RootAnalysis object)
                    observable.track_analysis_request(new_ar)
                    track_analysis_request(new_ar)
                    target_root.save()
                    fire_event(EVENT_PROCESSING_REQUEST_OBSERVABLE, new_ar)
                    submit_analysis_request(new_ar)
                    continue

    # at this point this AnalysisRequest is no longer needed
    delete_analysis_request(ar)

    # should this root expire now?
    if ar.root.is_expired():
        logging.debug(f"deleting expired root analysis {ar.root}")
        fire_event(EVENT_ANALYSIS_ROOT_EXPIRED, ar.root)
        delete_root_analysis(ar.root)
