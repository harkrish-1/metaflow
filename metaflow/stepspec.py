"""
StepSpec -- a FlowSpec subclass for single-computation specs.

StepSpec provides a simplified lifecycle: ``init()`` + ``call()``.
Users define ``call()`` (required) and optionally ``init()``, and the
metaclass synthesizes a single ``@step(start=True, end=True)`` method
that wraps both.
"""

import linecache

from .decorators import step as _step_decorator
from .exception import MetaflowException
from .flowspec import FlowSpec, FlowSpecMeta

# Counter for unique pseudo-filenames so each StepSpec subclass gets its own.
_synth_counter = 0


class StepSpecMeta(FlowSpecMeta):
    """Metaclass for StepSpec.

    For user subclasses it:
      1. Validates that ``call()`` exists and no ``@step`` methods are present.
      2. Synthesizes a single ``@step(start=True, end=True)`` method that
         calls ``init()`` then ``call()``.
      3. Delegates to ``FlowSpecMeta`` for registration and graph building.

    The synthetic step is injected in ``__new__`` (before the class object is
    created) so that the class body already contains the ``@step`` method when
    ``FlowSpecMeta.__init__`` builds the graph.
    """

    _base_class_names = FlowSpecMeta._base_class_names | frozenset({"StepSpec"})

    def __new__(mcs, name, bases, attrs):
        # For the StepSpec base class itself, skip validation / synthesis.
        if name == "StepSpec":
            return super().__new__(mcs, name, bases, attrs)

        # ------------------------------------------------------------------
        # User subclass validation
        # ------------------------------------------------------------------
        if "call" not in attrs:
            raise MetaflowException(
                "StepSpec subclass '%s' must define a call() method." % name
            )

        # Reject @step-decorated methods.
        # Use `is True` (not just truthiness) because Config.__getattr__
        # returns a DelayEvaluator for any unknown attribute, which is truthy.
        for attr_name, attr_val in attrs.items():
            if getattr(attr_val, "is_step", False) is True:
                raise MetaflowException(
                    "StepSpec subclass '%s' must not contain @step methods "
                    "(found '%s'). Use call() instead." % (name, attr_name)
                )

        # Reject class names starting with underscore
        if name.startswith("_"):
            raise MetaflowException(
                "StepSpec subclass name '%s' must not start with an underscore." % name
            )

        # ------------------------------------------------------------------
        # Synthesize the @step(start=True, end=True) method and inject into
        # attrs *before* the class is created so FlowSpecMeta.__init__ sees it.
        #
        # FlowGraph inspects source code via inspect.getsourcelines and
        # parses it with the AST.  For a dynamically-created function we
        # need (a) the def-name to match step_name and (b)
        # inspect.getsourcelines to succeed.  We satisfy both by compiling
        # the function from a source string and registering that source in
        # linecache so inspect can find it.
        # ------------------------------------------------------------------
        step_name = name.lower()
        user_init = attrs.get("init", lambda self: None)
        user_call = attrs["call"]

        exec_source = (
            "def %s(self):\n    _user_init(self)\n    _user_call(self)\n" % step_name
        )
        inspect_source = (
            "    def %s(self):\n        _user_init(self)\n        _user_call(self)\n"
            % step_name
        )

        global _synth_counter
        _synth_counter += 1
        pseudo_file = "<stepspec-%s-%d>" % (step_name, _synth_counter)

        linecache.cache[pseudo_file] = (
            len(inspect_source),
            None,
            inspect_source.splitlines(True),
            pseudo_file,
        )

        code = compile(exec_source, pseudo_file, "exec")
        _ns = {"_user_init": user_init, "_user_call": user_call}
        exec(code, _ns)
        _synthetic_fn = _ns[step_name]
        _synthetic_fn.__qualname__ = "%s.%s" % (name, step_name)
        attrs[step_name] = _step_decorator(_synthetic_fn, start=True, end=True)

        return super().__new__(mcs, name, bases, attrs)

    def __init__(cls, name, bases, attrs):
        # Handle the StepSpec base class itself -- we need _flow_state
        # initialised so subclasses can access it during MRO traversal,
        # but we must NOT register it or create synthetic steps.
        if name == "StepSpec":
            type.__init__(cls, name, bases, attrs)
            cls._init_attrs()
            return

        # Store which step name was synthesised
        cls._step_spec_step_name = name.lower()

        # Delegate to FlowSpecMeta for registration + graph building
        super().__init__(name, bases, attrs)


class StepSpec(FlowSpec, metaclass=StepSpecMeta):
    """
    A FlowSpec subclass for single-computation specs.

    Subclasses must define ``call()`` and may optionally define ``init()``.

    Example
    -------
    ::

        class Upper(StepSpec):
            text = Parameter("text", type=str, default="hello")

            def call(self):
                self.output = self.text.upper()

    CLI usage::

        python my_spec.py run --text "hello"
    """

    _NON_PARAMETERS = FlowSpec._NON_PARAMETERS | {"init", "call"}

    def init(self):
        """Override to perform initialisation before ``call()``."""
        pass

    def call(self):
        """Override to define the main computation."""
        raise NotImplementedError("Subclasses must implement call()")
