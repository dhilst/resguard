"""
resguard
========

This module provides function for parsing response data, based on
dataclass defined schemas.

The user define arbitrary schema using dataclass. One dataclass
can refer to others to represent nested structures.

```python
>>> @dataclass
... class Foo:
...     pass

>>> @dataclass
... class Bar:
...     foo: Foo

```

While made with parsing json decoded data from REST responses in mind, the
approach is pretty generic and may work for other use cases.

So suppose that you're in charging to do another API client.. if you started
doing this once you know that you'll gonna work with JSON and that JSON become
plain dicts and lists in python, it's easy to lose the track of these objects
and start to spread KeyError and IndexError handlers all over the codebase.

It became usual to me to write representation of the response data as objects
and instantiating these objects, and with objects I can have some type
checking, mutch better than with dicts... and can track what the fields

But writing ad-hoc classes and parsers from dict -> myobject became boring
too.. so I created this! Much more declarative and type checking friendly

So let's write an API to cat facts, we can find the docs here
https://alexwohlbruck.github.io/cat-facts/docs/endpoints/facts.html

We're implementing the /facts/random endpoint. The documentation said that it
will respond like this:

```json
	{
		"_id": "591f9894d369931519ce358f",
		"__v": 0,
		"text": "A female cat will be pregnant for approximately 9 weeks - between 62 and 65 days from conception to delivery.",
		"updatedAt": "2018-01-04T01:10:54.673Z",
		"deleted": false,
		"source": "api",
		"used": false
	}
```

So is a list of facts, a fact can be defined like this

```python
>>> from datetime import datetime
>>> @dataclass
... class Fact:
...     _id: str
...     __v: int
...     text: str
...     updatedAt: datetime
...     deleted: bool
...     source: str
...     used: bool
...     user: Optional[str]

```

To parse a respone you call `parse_dc`, where `dc` stands for dataclass. You
call it with the dataclass and the response data:

```python
>>> import requests as r
>>> url = "https://cat-fact.herokuapp.com"
>>> res = r.get(f"{url}/facts/random")
>>> parse_dc(Fact, res.json())
Traceback (most recent call last):
...
TypeError: Unknow field type for Fact(_id,_Fact__v,text,updatedAt,deleted,source,used,user)

```

You may notice that I put a `user: Optional[str]` on the `Fact` definition too.
This is how you express optional fields, that may or may not be present on
response. Missing optinal fields become `None` in dataclass

What happens here is that the documentation is outdated, there are a type field
that was not expected in response. `parse_dc` raise a TypeError if anything
goes out of rails. Let's see in response what we have in `type` field
```python
>>> type_ = res.json()['type']
>>> type_, type(type_)
('cat', <class 'str'>)

```

We do not want that our software breaks because the API put a brand new
field in the response. You can ignore unknow fields by passing `strict=False`
to `parse_dc`. If you want this by default you can memoise the parse_dc like
below:

```python
>>> from functools import partial
>>> parse_dc = partial(parse_dc, strict=False)

```

So let's update our `Fact` definition

```python
>>> @dataclass
... class Fact:
...     _id: str
...     __v: int
...     text: str
...     updatedAt: datetime
...     deleted: bool
...     source: str
...     used: bool
...     user: Optional[str]
...     type: str # <- we added this

```

And parse again. This time it works, but it's doesn't properly initialize the
dataclasses fields. Well, dataclass don't do runtime type checking. 
```python
>>> dc = parse_dc(Fact, res.json())
>>> dc  
Fact(...)
>>> type(dc.updatedAt)
<class 'str'>

```

If you pass it a string, it doens't matter if the field type says datetime,
constructor will put the string there and it's done. But the standard library
provides a way to handle this. You need to provide an `__post_init__` method.
It will not receive any arguments and it.s called by constructor after
initializing self.

```python
>>> @dataclass
... class Fact:
...     _id: str
...     __v: int
...     text: str
...     updatedAt: datetime
...     deleted: bool
...     source: str
...     used: bool
...     user: Optional[str]
...     type: str
...
...     def __post_init__(self):
...         if isinstance(self.updatedAt, str):
...             self.updatedAt = datetime.strptime(self.updatedAt, "%Y-%m-%dT%H:%M:%S.%fZ")

>>> dc = parse_dc(Fact, res.json())
>>> dc 
Fact(...)
>>> type(dc.updatedAt)
<class 'datetime.datetime'>

```
Now what if we want go to the oposite direction, given somejson, construct
a dataclass. Well resguard can be invoked as `curl something | python -m resguard fromjson`
and it will output a dataclass definition for that JSON.

The type inference is pretty simple, but it is already better than writing all
that dataclasses by hand. Let's see it in action

```python
>>> print(print_dc(fromjson("Root", '{"foo": "foo", "bar": { "bar": "bar" }}')))
@dataclass
class bar:
   bar: str
<BLANKLINE>
<BLANKLINE>
@dataclass
class Root:
   foo: str
   bar: bar
<BLANKLINE>

```

To use it from command line (much simpler)
```shell
curl -s https://cat-fact.herokuapp.com/facts/random | python -m resguard fromjson
@dataclass
class status:
   verified: bool
   sentCount: int


@dataclass
class Root:
   used: bool
   source: str
   type: str
   deleted: bool
   _id: str
   __v: int
   text: str
   updatedAt: str
   createdAt: str
   status: status
   user: str


```

That's it, check below for function docs
"""

from io import StringIO
import logging
import json
import re
from typing import *
from ast import literal_eval
from dataclasses import dataclass, fields, is_dataclass, make_dataclass

try:
    from typing_extensions import Protocol, Literal
except ImportError:
    pass

T = TypeVar("T")

log = logging.getLogger(__name__)
if __debug__:
    log.setLevel(logging.DEBUG)


class Dataclass(Protocol):
    """
    Dataclass static type
    https://stackoverflow.com/a/55240861/652528
    """

    __dataclass_fields__: Dict


def create_base(base):
    """
    A function decorator. It replace the function by a class
    which call the decorated function in its new method, for
    example

    ```python
    >>> from datetime import datetime
    >>> @create_base(datetime)
    ... def date_br(s):
    ...     return datetime.strptime(s, r"%d/%m/%Y")
    >>> issubclass(date_br, datetime)
    True
    >>> date_br("01/01/2001")
    datetime.datetime(2001, 1, 1, 0, 0)

    ```
    """

    def dec(func):
        class _TypeHelper(base):
            def __new__(cls, *args, **kwargs):
                return func(*args, **kwargs)

        _TypeHelper.__name__ = func.__name__
        return _TypeHelper

    return dec


def unpack_union(union: Union[T, Any, None]) -> T:
    """
    Takes an Unin and return another union with the same arguments
    as input, but with None and Any filtered

    ```python
    >>> unpack_union(Optional[str])
    <class 'str'>

    >>> unpack_union(List[str])
    <class 'str'>

    ```

    It respect concrete types
    ```python
    >>> unpack_union(int)
    <class 'int'>

    ```

    If the input is a literal, it returns itself. Literals are types
    and values at same time, like enums
    ```python
    >>> unpack_union(1)
    1
    >>> unpack_union([1,2])
    [1, 2]
    
    ```
    """
    try:
        return Union[
            tuple(t for t in union.__args__ if t not in (type(None), Any))  # type: ignore
        ]
    except AttributeError:  # no __args__
        return union


def parse_dc_typecheck(cls: Dataclass, data: dict, ignore_unknows=False) -> Dataclass:
    """
    Given an arbitrary dataclass and a dict this function will
    recursively parse the data, checking data types against cls
    dataclass.

    It raises TypeError if something goes wrong. It tries to improve
    the common errors by reraising then with better messages.

    First declare some dataclasses that define the data that you want
    to parse.
    ```python
    >>> @dataclass
    ... class Foo:
    ...     name: Literal[0, 1]
    ...
    >>> @dataclass
    ... class Bar:
    ...     l: List[int]
    ...     foo: Dict[str, int]
    ...     Foo: Foo
    ...     age: Optional[int] = None

    ```

    Now suppose that you get this data from a network response. I'm
    expecting it to be plain json parsed to dicts, lists and so on,
    but no objects, just decoded json:

    ```python
    >>> data = {"foo": {"bar": 1}, "l": [], "Foo": {"name": 1}}

    ```

    Hmm, it seems to match, lets try to parse this
    ```python
    >>> parse_dc_typecheck(Bar, data)
    Bar(l=[], foo={'bar': 1}, Foo=Foo(name=1), age=None)

    ```

    You can see that it creates nested dataclasses too, cool. But this
    was easy, this was the happy path, what about the not so happy path.
    Let's change data, and see how parse_dc handle errors
    ```python
    >>> data["badkey"] = "bad things"
    >>> parse_dc_typecheck(Bar, data)
    Traceback (most recent call last):                                           
    ...
    TypeError: Unknow field badkey for Bar. Expected one of (l,foo,Foo,age)

    ```

    Hmm... interesting... It knows that badkey is not in Bar dataclass
    definition and it shows what are the expected keys. Let's try another thing

    ```python
    >>> @dataclass
    ... class Foo:
    ...     foo: int
    >>> parse_dc_typecheck(Foo, {"foo": "an string"})
    Traceback (most recent call last):
    ...
    TypeError: in dataclass Foo, 'an string' is not int: invalid literal for int() with base 10: 'an string'

    ```

    So I passed a bad (by little margin) value in "foo" key. It expects an int
    and received an string. The "invalid literal ..." part is from an error that
    raises when parce_dc tries to pass "an string" to int(), it handles the error
    and reraise as TypeError. The idea is that calle should catch TypeError.

    Now if it uses the dataclass field type as constructor, this works
    ```python
    >>> @dataclass
    ... class Foo:
    ...     foo: str 
    >>> parse_dc_typecheck(Foo, {"foo": 1}).foo
    '1'
   
    ```

    It works because str(1) just .. works .. So think about str as the Any type
    from typing module. Almost anything can be encoded as string, so take care
    of yours, since they point to holes on type checking, but provide a nice
    generic system
    """
    res = {}
    fields_ = {f.name: f.type for f in fields(cls)}
    for k, v in data.items():
        # avoid python mangling
        k = re.sub(r"^__", f"_{cls.__name__}__", k)
        if k not in fields_:
            msg = "Unknow field {} for {}. Expected one of ({})".format(
                k, cls.__name__, ",".join(fields_.keys())
            )
            if not __debug__:
                log.warning("%s", msg)
            if ignore_unknows:
                continue
            raise TypeError(msg)
        if v is None:
            continue
        typev = fields_[k]
        is_literal = False
        # @FIXME
        # This code is bad, lift this to another
        # function that returns the concrete_type
        if hasattr(typev, "__origin__"):
            if typev.__origin__ in (list, List):
                concrete_typev = list
                list_subtype = unpack_union(typev)
            elif typev.__origin__ in (dict, Dict):
                concrete_typev = dict
                dict_subtype_key = typev.__args__[0]
                dict_subtype_val = typev.__args__[1]
            elif typev.__origin__ in (Union,):
                concrete_typev = unpack_union(fields_[k])
            elif typev.__origin__ is Literal:
                is_literal = True
                literals = typev.__args__
            else:
                raise NotImplementedError(
                    f"Can't find a way to determine concrete type for {v}"
                )
        else:
            # typing_extensions.Literal has no __origin__
            if str(typev).startswith("typing_extensions.Literal"):
                is_literal = True
                literals = literal_eval(
                    str(typev).replace("typing_extensions.Literal", "")
                )
            else:
                concrete_typev = typev
        scalar = (float, int, bool, str)
        if is_literal:
            if v not in literals:
                raise TypeError(
                    f"while creating Literal for dataclass {cls.__name__}, it seems that {v} is not in literal values {literals}"
                )
            res[k] = v
        elif is_dataclass(concrete_typev):
            res[k] = parse_dc(concrete_typev, v)
        elif issubclass(concrete_typev, scalar):
            try:
                res[k] = concrete_typev(v)
            except ValueError as e:
                raise TypeError(
                    f"in dataclass {cls.__name__}, {repr(v)} is not {concrete_typev.__name__}: {e}"
                ) from e
        elif concrete_typev is list:
            try:
                res[k] = [list_subtype(x) for x in v]
            except ValueError as e:
                raise TypeError(
                    f"in dataclass {cls.__name__} while trying to construct a list of type {list_subtype} with values [{', '.join(v)}]: {e}"
                ) from e
        elif concrete_typev is dict:
            res[k] = {dict_subtype_key(k): dict_subtype_val(v) for k, v in v.items()}
        elif callable(concrete_typev):
            try:
                res[k] = concrete_typev(v)
            except TypeError as e:
                raise TypeError(
                    f" in dataclass {cls.__name__} while trying to construct value from {concrete_typev.__name__}({repr(v)}): {e}"
                ) from e
        else:
            raise NotImplementedError(
                "This should never happen, please open an issue with an stack trace"
            )
    try:
        return cls(**res)
    except TypeError as e:
        raise TypeError(
            f"while calling {cls.__name__}(**data) with this data {data}: {e}"
        ) from e


_created_dataclasses = {}


def create_dc(dcname: str, fields):
    """
    >>> from dataclasses import is_dataclass, fields, asdict
    >>> Foo = create_dc("Foo", (("foo", str),) )
    >>> Foo.__name__
    'Foo'
    >>> is_dataclass(Foo)
    True
    >>> asdict(Foo(foo="foo"))
    {'foo': 'foo'}
    """
    dc = make_dataclass(dcname, fields)
    _created_dataclasses[dcname] = dc
    return dc


def fromdict(dcname: str, data: dict):
    """
    >>> from dataclasses import fields
    >>> Foo = fromdict("Foo", {"foo": "foo", "bar": {"bar": "bar"}})
    >>> [f.type.__name__ for f in fields(Foo)]
    ['str', 'bar']
    """
    dc_fields = []
    scalar = (int, float, bool, str)
    for k, v in data.items():
        if isinstance(v, dict):
            dc_fields.append((k, fromdict(k, v)))
        elif isinstance(v, list):
            if len(v) == 0:
                dc_fields.append((k, List[Any]))
            elif len(set(map(type, v))) == 1:
                dc_fields.append((k, List[type(v[0])]))
            else:
                dc_fields.append((k, Tuple[tuple(map(type, v))]))
        elif isinstance(v, scalar):
            dc_fields.append((k, type(v)))
    return create_dc(dcname, dc_fields)


def print_dc(dcroot) -> str:
    """
    from dataclasses import dataclass
    >>> @dataclass
    ... class Bar:
    ...     bar: str
    >>> @dataclass
    ... class Foo:
    ...     foo: str
    ...     bar: Bar
    >>> print(print_dc(Foo))
    @dataclass
    class Bar:
       bar: str
    <BLANKLINE>
    <BLANKLINE>
    @dataclass
    class Foo:
       foo: str
       bar: Bar
    <BLANKLINE>
    """
    s = StringIO()
    s.write("@dataclass\n")
    s.write(f"class {dcroot.__name__}:\n")
    fields_ = {f.name: f.type for f in fields(dcroot)}
    for name, type_ in fields_.items():
        if is_dataclass(type_):
            new_dc = print_dc(type_)
            new_s = StringIO()
            new_s.write(new_dc)
            new_s.write("\n\n")
            new_s.write(s.getvalue())
            s = new_s
        s.write(f"   {name}: {type_.__name__}\n")
    return s.getvalue()


def fromjson(dcname: str, jsondata: str):
    """
    Just a helper, it calls json.loads on jsondata
    before calling fromdict
    """
    return fromdict(dcname, json.loads(jsondata))


def parse_dc(dc, data, strict=True):
    """
    Build tree of dataclasses initialized with data

    It don't type checks, just instantiate the dataclasses recursively. Just
    note that dataclass don't check at runtime too, so, this doesn't typecheck
    but it works at runtime

    >>> from dataclasses import dataclass, asdict
    >>> @dataclass
    ... class Foo:
    ...     foo: str
    ...     __bar: str
    >>> asdict(Foo(foo=1, _Foo__bar=1))
    {'foo': 1, '_Foo__bar': 1}
    
    But mypy will detect the `foo=1` there.

    Let's parse something :-)
    ```python
    >>> from enum import Enum
    >>> FooEnum = Enum("FooEnum", "foo bar")
    >>> 
    >>> @dataclass
    ... class Bar:
    ...     bar: str
    >>> 
    >>> @dataclass
    ... class Foo:
    ...     foo: str
    ...     bar: Bar
    >>> parse_dc(Foo, {"foo": "foo", "num": 1, "bar": {"bar": "bar"}})
    Foo(foo='foo', bar=Bar(bar='bar'))

    >>> from datetime import datetime
    >>> @dataclass
    ... class Date:
    ...     d: datetime
    >>> Date(d="20010101T00:00Z").d
    20010101T00:00Z
    >>> @dataclass
    ... class Date:
    ...     d: datetime
    ...     def __post_init__(self):
    ...         if isinstance(self.d, str):
    ...             self.d = datetime.strptime("%Y%m%dT%H%MZ")
    >>> Date(d="20010101T00:00Z").d


    ```
    """
    flds = {f.name: f.type for f in fields(dc)}
    cpy = data.copy()
    for k, v in data.items():
        if k not in flds.keys():
            if k.startswith("__"):
                new_k = f"_{dc.__name__}{k}"
                cpy[new_k] = v
                del cpy[k]
                k = new_k
            else:
                log.warn(f"Unknow field {k}={v} for {dc.__name__}")
                if strict:
                    fields_ = ",".join([
                        f"{t.name}" for t in fields(dc)
                    ])
                    raise TypeError(f"Unknow field {k} for {dc.__name__}({fields_})")
                del cpy[k]
                continue
        if is_dataclass(flds[k]):
            cpy[k] = parse_dc(flds[k], v)
    return dc(**cpy)


if __name__ == "__main__":
    import doctest
    import sys

    try:
        arg1 = sys.argv[1]
    except IndexError:
        print(f"Usage: python -m resguard {{fromjson [dcname]|test}}", file=sys.stderr)
        sys.exit(1)
    if arg1 == "test":
        doctest.testmod(optionflags=doctest.ELLIPSIS)
    elif arg1 == "fromjson":
        try:
            arg2 = sys.argv[2]
        except IndexError:
            arg2 = "Root"
        print(print_dc(fromjson(arg2, sys.stdin.read())))
