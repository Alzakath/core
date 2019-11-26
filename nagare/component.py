# --
# Copyright (c) 2008-2019 Net-ng.
# All rights reserved.
#
# This software is licensed under the BSD License, as described in
# the file LICENSE.txt, which you should have received as part of
# this distribution.
# --

"""This module implements the component model of the framework.

This model is inspired by the Seaside one. With the possibility to embed,
replace and call a component. It's described in `ComponentModel`
"""

from nagare.renderers import xml
from nagare.services import router
from nagare.partial import Partial
from nagare import presentation, continuation

_marker = object()


class AnswerWithoutCall(Exception):
    pass


class Component(xml.Component):
    """This class transforms any Python object into a component

    A component has views, can be embedded, replaced, called and can answer a value.
    """
    def __init__(self, o=None, view=0, url=None):
        """Initialisation

        In:
          - ``o`` -- the python object (or component) to transform into a component
          - ``view`` -- the name of the view to use (``None`` for the default view)
          - ``url`` -- the url fragment to add before all the links generated by
            views of this component
        """
        self._becomes(o, view, url)

        self._cont = None
        self._on_answer = None
        self._actions = {}
        self._new_actions = {}

    def __call__(self):
        """Return the inner object
        """
        return self.o

    def register_action(self, action_id, view, action, with_request, render, args, kw):
        """Register a action for this component

        In:
          - ``view`` -- name of the view which registers this action (``None`` for the default view)
          - ``priority`` -- type and priority of the action
          - ``action`` -- the action function or method
          - ``with_request`` -- will the request and response objects be passed to the action?
          - ``render`` -- the render function or method
          - ``actions`` -- the actions manager
        """
        return self._new_actions.setdefault(action_id, (view, action, with_request, render, args, kw))[1]

    def serialize_actions(self, clear_actions):
        """Return the actions to serialize

        In:
          - ``clean_actions`` -- do we have to forget all the old actions?

        Return:
          - the actions of this component
        """
        '''
        old = self._actions
        new = self._new_actions.copy()
        self._new_actions.clear()

        if not clear_actions:
            views = {action[0] for action in new.values()}

            # Keep only the old actions of a view if no new actions were registered
            old = {k: v for k, v in old.items() if v[0] not in views}

            new.update(old)

        self._actions = new

        return new
        '''
        old, self._actions, self._new_actions = self._actions, self._new_actions, {}

        if not clear_actions:
            views = {action[0] for action in self._actions.values()}

            # Keep only the old actions of a view if no new actions were registered
            old = {k: v for k, v in old.items() if v[0] not in views}

            self._actions.update(old)

        return self._actions

    def reduce(self, clean_callbacks, callbacks):
        callbacks.update(self.serialize_actions(clean_callbacks))

        return super(Component, self).__reduce__()

    def render(self, renderer, view=0, *args, **kw):
        """Rendering method of a component

        Forward the call to the generic method of the ``presentation`` service
        """
        # Create a new renderer of the same class than the current renderer
        renderer = renderer.new(parent=renderer, component=self, view=view)
        renderer.start_rendering()

        output = presentation.render(self.o, renderer, self, self.view if view == 0 else view, *args, **kw)
        return renderer.end_rendering(output)

    def _becomes(self, o, view, url):
        """Replace a component by an object or an other componentw
        In:
          - ``o`` -- object to be replaced by
          - ``view`` -- the name of the view to use (``None`` for the default view)
          - ``url`` -- the url fragment to add before all the links generated by
            views of this component

        Return:
          - ``self``
        """
        o = self if type(o) is object else o
        if isinstance(o, Component):
            o = o()

        self.o = o

        self.view = view
        self.url = url

    def becomes(self, o=_marker, view=0, url=None):
        """Replace a component by an object or an other component

        In:
          - ``o`` -- object to be replaced by
          - ``view`` -- the name of the view to use (``None`` for the default view)
          - ``url`` -- the url fragment to add before all the links generated by
            views of this component

        Return:
          - ``self``
        """
        self._becomes(o, view, url or self.url)
        self._cont = None

        return self

    def _call1(self, o, view, url):
        if not continuation.has_continuation:
            raise NotImplementedError('Stackless Python or PyPy is needed for `comp.call()`')

        # Keep my configuration
        previous_o = self.o
        previous_view = self.view
        previous_url = self.url
        previous_cont = self._cont
        previous_on_answer = self._on_answer

        # Set the new configuration
        self._on_answer = None

        # Replace me by the object and wait its answer
        self.becomes(o, view, url)

        self._cont = continuation.get_current()

        return (
            previous_o,
            previous_view,
            previous_url,
            previous_cont,
            previous_on_answer
        )

    def _call2(self, previous_o, previous_view, previous_url, previous_cont, previous_on_answer):
        self._on_answer = previous_on_answer
        self._cont = previous_cont

        self._becomes(previous_o, previous_view, previous_url)

    def call(self, o=_marker, view=0, url=None):
        # Call an other object or component

        # The current component is replaced and will be back when the object
        # will do an ``answer()``

        # In:
        #   - ``o`` -- the object to call
        #   - ``view`` -- the name of the view to use (``None`` for the default view)
        #   - ``url`` -- the url fragment to add before all the links generated by
        #     views of this component

        # Return:
        #   - the answer of the called object
        #
        # .. note:
        #   - the code of this function will be serialized.
        #     Keep it to a minimal (no docstring ...)

        p = self._call1(o, view, url)
        r = self._cont.switch()
        self._call2(*p)

        return r

    def answer(self, r=None):
        """Answer to a call

        In:
          - the value to answer
        """
        # If a function is listening to my answer, calls it
        if self._on_answer is not None:
            return self._on_answer(r)

        # Else, check if I was called by a component
        if self._cont is None:
            raise AnswerWithoutCall(self)

        # Returns my answer to the calling component
        self._cont.switch(r)

    def on_answer(self, f, *args, **kw):
        """
        Register a function to listen to my answer

        In:
          - ``f`` -- function to call with my answer
          - ``args``, ``kw`` -- ``f`` parameters
        """
        self._on_answer = Partial(f, *args, **kw) if args or kw else f
        return self

    def __repr__(self):
        return '<%s with %s at 0x%x on object %r>' % (
            self.__class__.__name__.lower(),
            "view '%s'" % self.view if self.view else 'default view',
            id(self),
            self.o
        )


@router.route_for(Component, '{url2:.*}', ())
def route(self, url, http_method, request, response, url2):
    """Initialisation from an url

    In:
      - ``url`` -- rest of the url to process
      - ``http_method`` -- the HTTP method
      - ``request`` -- the WebOb Request object
      - ``request`` -- the WebOb Response object
    """
    return self(), url, http_method, request, response, self

# -----------------------------------------------------------------------------------------------------


class Task(object):
    """A ``Task`` encapsulated a simple method. A ``task`` is typically used to
    manage other components by calling them.

    .. warning::

       A ``Task`` is an object, not a component: you must wrap it into a ``Component()`` to use it.
    """

    def _go(self, comp):
        # If I was not called by an other component and nobody is listening to
        # my answer,  I'm the root component. So I call my ``go()`` method forever
        if comp._cont is comp._on_answer is None:
            while True:
                self.go(comp)

        # Else, answer with the return of the ``go`` method
        comp.answer(self.go(comp))

    def go(self, comp):
        raise NotImplementedError()

    def render_(self, renderer, comp, view):
        continuation.Continuation(self._go, comp)

        return comp.render(renderer.parent)
