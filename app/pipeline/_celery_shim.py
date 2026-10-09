"""Celery kurulu olmayan ortamda (test) pipeline'i calistirmak icin
minimum uyumlu shim. Uretimde gercek celery kullanilir."""
import functools


class _Task:
    def __init__(self, fn, bound=False):
        self.fn = fn
        self.bound = bound
        functools.update_wrapper(self, fn)

    def run(self, *a, **k):
        if self.bound:
            return self.fn(self, *a, **k)
        return self.fn(*a, **k)

    __call__ = run

    def s(self, *a, **k):
        return lambda: self.run(*a, **k)

    def retry(self, exc=None, countdown=0):
        raise (exc or RuntimeError("retry"))


class Celery:
    def __init__(self, *a, **k):
        pass

    def task(self, *dargs, **dkw):
        if dargs and callable(dargs[0]):
            return _Task(dargs[0])
        def deco(fn):
            return _Task(fn, bound=dkw.get("bind", False))
        return deco


def group(items):
    fns = list(items)

    class _Result:
        def apply_async(self):
            return self

        def get(self):
            return [f() for f in fns]

    return _Result()
