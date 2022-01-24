from collections import OrderedDict


class Template:
    """Representation of Mediawiki templates.

    Attributes
    ----------
    _name : str
        The name of the template.
    _subst : bool
        Whether the template should be substituted or not. If True,
        add "subst:" after the initial "{{" in the template string.
    _parameters : list or OrderedDict
        The parameters to pass to the template.

    """

    def __init__(self, name, subst=False, parameters=None):
        self._name = name
        self._subst = subst
        if parameters is None:
            self._parameters = OrderedDict()
        elif type(parameters) == list:
            self._parameters = {i: p for i, p in enumerate(parameters, 1)}
        else:
            self._parameters = parameters

    def __str__(self):
        output = "{{" + "{}{}".format("subst:" * self._subst, self._name)
        if self._parameters:
            for name, value in self._parameters.items():
                if isinstance(value, Template):
                    output += "\n| {} = {}".format(name, value.oneline_string())
                else:
                    output += "\n| {} = {}".format(name, value)
            output += "\n}}"
        else:
            output += "}}"
        return output

    def add_parameter(self, name, value):
        """Add a template parameter.

        Parameters
        ----------
        name : str
            Name of the parameter.
        value : str
            Value of the parameter.

        """
        self._parameters[name] = value

    def multiline_string(self, nesting_level=0):
        output = "{{" + "{}{}".format("subst:" * self._subst, self._name)
        if self._parameters:
            indentation = "  " * nesting_level
            for name, value in self._parameters.items():
                if isinstance(value, Template):
                    value_string = value.multiline_string(nesting_level + 1)
                else:
                    value_string = value
                output += "\n{}| {} = {}".format(indentation * 2, name, value_string)
            output += "\n{}".format(indentation) + "}}"
        else:
            output += "}}"
        return output

    def oneline_string(self):
        output = "{{" + "{}{}".format("subst:" * self._subst, self._name)
        if self._parameters:
            for name, value in self._parameters.items():
                output += "|{}={}".format(name, value)
            output += "}}"
        else:
            output += "}}"
        return output
