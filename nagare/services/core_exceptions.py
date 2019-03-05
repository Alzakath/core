# --
# Copyright (c) 2008-2019 Net-ng.
# All rights reserved.
#
# This software is licensed under the BSD License, as described in
# the file LICENSE.txt, which you should have received as part of
# this distribution.
# --


from webob import exc
from nagare.services import http_exceptions

from nagare.services.callbacks import CallbackLookupError


def default_handler(exception, exceptions_service, request, response, **params):

    if isinstance(exception, CallbackLookupError):
        # As the XHR requests use the same continuation, a callback
        # can be not found (i.e deleted by a previous XHR)
        # In this case, do nothing
        exceptions_service.log_exception('nagare.callbacks')
        exception = exc.HTTPOk() if request.is_xhr else exc.HTTPInternalServerError()

    elif not isinstance(exception, exc.HTTPException):
        exceptions_service.log_exception()
        exception = exc.HTTPInternalServerError()

    return exception


class ExceptionsService(http_exceptions.ExceptionService):
    LOAD_PRIORITY = http_exceptions.ExceptionService.LOAD_PRIORITY + 2
    CONFIG_SPEC = dict(
        http_exceptions.ExceptionService.CONFIG_SPEC,
        handler='string(default="nagare.services.core_exceptions:default_handler")'
    )