def func_property(**kwargs):
    def decorate(func):
        for k in kwargs:
            setattr(func, k, kwargs[k])
        return func

    return decorate


def singleton(cls):
    """
    Use this if the class itself do not need to be referenced in the future.
    This will convert the class to a function that returns the singleton instance
    Syntax is as follows:
    ```
    @decorator.singleton
    class MySingletonClass():
        ...
    ```
    Reference: https://divyakhatnar.medium.com/singleton-in-python-be59f7698a51
    """
    instances = {}

    def getinstance(*args, **kwargs):
        if cls not in instances:
            instances[cls] = cls(*args, **kwargs)
        return instances[cls]

    return getinstance


class Singleton(type):
    """
    Use this if the class itself is still needed.
    Syntax is as follows:
    ```
    class MySingletonClass(metaclass=Singleton):
        ...
    ```
    REVIEW: this is not a decorator, it is put here for now
    Reference: https://divyakhatnar.medium.com/singleton-in-python-be59f7698a51
    """

    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]
