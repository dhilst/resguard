This module provides function for parsing requests based on
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
While made with parsing json decoded data from REST requests, the approach
is pretty generic and may work for other use cases.

So suppose that you're in charging to do another API client, yeah, yeah, ..
I know, again, one more time ... do requests, get data, transform in something
manageable and the save on database, or, whatever .. if you started doing this
once you know that you'll gona work with JSON and that JSON become plain dicts
and lists in python, and many people work just with dicts and lists and everything
is okay, up to when you lose the track of these objects and start to spread KeyError
and IndexError all over the codebase.

It became usual to me to write representation of the responses as objects and
instantiating these objects, and with objects I can have some type checking, mutch
better than with dicts...

But writing ad-hoc classes and parsers from dict -> myobject became boring
too.. but I got some generic way of doing this based on dataclasses!! This is
much more declarative and type checking friendly

So let's write an API to cat facts, we can find the docs here
https://alexwohlbruck.github.io/cat-facts/docs/endpoints/facts.html

Now the have this response:

{'used': False, 'source': 'user', 'type': 'cat', 'deleted': False, '_id': '5a4bfc91b0810f0021748b92', 'updatedAt': '2020-01-02T02:02:48.612Z', 'createdAt':
'2018-01-21T21:20:02.814Z', 'user': '5a9ac18c7478810ea6c06381', 'text': 'Blackie became the richest cat in history when he inherited 15 million British Pounds
.', '__v': 0, 'status': {'verified': True, 'sentCount': 1}}

So is a list of facts, a fact can be defined like this

```python
>>> from datetime import datetime
>>> @dataclass
... class Status:
...     verified: bool
...     sentCount: int
>>>
>>> @dataclass
... class Fact:
...     _id: str
...     __v: int
...     updatedAt: datetime
...     createdAt: datetime
...     deleted: bool
...     source: str
...     used: bool
...     type: str
...     user: str
...     text: str
...     status: Status


>>> import requests as r
>>> url = "https://cat-fact.herokuapp.com"
>>> res = r.get(f"{url}/facts/random")
>>> parse_dc(Fact, res.json())
Traceback (most recent call last):
...
TypeError:  in dataclass Fact while trying to construct value from datetime...
```

Well, for a dataclass field `F: T` and value `V`, parse_dc will call `T(V)` at
somepoint. So is important that construtors can work with data that came from request,
but also we don't want to not lose typechecking. The solution here
is to wrap the problematic object in a class and override its constructor

```python
>>> class datetimestr(datetime):
...     def __new__(cls, datestr):
...         return datetime.strptime(datestr, "%Y-%m-%dT%H:%M:%S.%fZ")

>>> @dataclass
... class Fact2:
...     _id: str
...     __v: int
...     updatedAt: datetimestr2
...     createdAt: datetimestr
...     deleted: bool
...     source: str
...     used: bool
...     type: str
...     user: str
...     text: str
...     status: Status
...
>>> parse_dc(Fact2, res.json())
Fact2(...)
```
And it works!

To avoid the class ... __new__ boilerplate is possible to use the create_base
decorator, it takes a function and replaces it by a class which is subclass of
the sole argument

So you can replace this

```python
>>> class datetimestr(datetime):
...     def __new__(cls, datestr):
...         return datetime.strptime(datestr, "%Y-%m-%dT%H:%M:%S.%fZ")
```

by this
```python
>>> @create_base(datetime)
... def date_br(s):
...     return datetime.strptime(s, r"%d/%m/%Y")
```

Since date_br is a subtype of datetime it typechecks for datetime

# parse_dc

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
>>> parse_dc(Bar, data)
Bar(l=[], foo={'bar': 1}, Foo=Foo(name=1), age=None)
```

You can see that it creates nested dataclasses too, cool. But this
was easy, this was the happy path, what about the not so happy path.
Let's change data, and see how parse_dc handle errors
```python
>>> data["badkey"] = "bad things"
>>> parse_dc(Bar, data)
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
>>> parse_dc(Foo, {"foo": "an string"})
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
>>> parse_dc(Foo, {"foo": 1}).foo
'1'
```

It works because str(1) just .. works .. So think about str as the Any type
from typing module. Almost anything can be encoded as string, so take care
of yours, since they point to holes on type checking, but provide a nice
generic system

# @create_base

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

# unpack_union

Takes an Union and return another union with the same arguments
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
