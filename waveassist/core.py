# packagetest/core.py
_parameters = {}

def setparameters(key: str, value: any):
    """Sets a parameter."""
    _parameters[key] = value

def getparameters(key: str):
    """Gets a parameter."""
    return _parameters.get(key, None)
