[![Build Status](https://travis-ci.org/dhilst/resguard.svg?branch=master)](https://travis-ci.org/dhilst/resguard)

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


# parse_dc(dc, data, strict=True)

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

# create_base(base)

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

# unpack_union(union: Union[~T, Any, NoneType]) -> ~T

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

# Dataclass(*args, **kwds)

Dataclass static type
https://stackoverflow.com/a/55240861/652528

