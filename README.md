
# Introduction

The python `oxtie` package is a system for saving and loading data
to various backends (especially backends in the cloud). It fits
somewhere above low-level serialization/deserialization tools like
pickle, json, msgpack, etc., but below a full fledged database like
postgres or MongoDB.

## Installation

You can install in the usual way via something like

```sh
$ pip install oxtie
```

## Example Usage

The main question `oxtie` tries to answer is "which backend should I
use to store my python objects in an easy and efficient way?". The
answer is "You don't have to choose; use oxtie and you can easily
change the backend when you like."

To illustrate, imagine you want to save your Pandas DataFrame
somehow. First, you would do the usual thing to import pandas and
create a DataFrame:

```python

>>> import pandas  # So we can make a dataframe.
>>> data = {'estimate': [.17, None]}, # Make example data
>>> frame = pandas.DataFrame(data, index=['2017-07-01', '2017-10-01'])
```

Next, you can create an instance of the `SimpleFrame` class from
`oxtie` to store your DataFrame as a temporary file via something like:
```python

>>> from oxtie.fronts import specials  # Illustrate special example
>>> backend=specials.TempFileBackend() # Choose a temp file backend
>>> f = specials.nums.SimpleFrame(name='test', backend=backend, frame=frame)
>>> f.arbitrary = 'You can also save arbitrary data in SimpleFrame'
>>> f.save()  # Now save the frame.
```

You could instead have done something
like `from oxtie.backs import aws` to get a different backend and
use `backend = aws.S3Backend('prefix', 'bucket')` to save to Amazon
S3. Or if you prefer DynamoDB, you could
use `backend = aws.DynamoBackend(table_name, key_name)` to
have you data saved to the table `table_name` with primary key
`key_name` instead. The key idea is that `oxtie` handles dealing
with the different backends so you don't have to worry about it or
change your code (apart from choosing the backend of course).

Continuing our example, once you want to load your data you can do the
following (possibly in another python session):
``` python
>>> g = backend.load('test', allow_load=True)
>>> g.__class__.__name__
'SimpleFrame'
>>> g.frame.to_csv() == f.frame.to_csv()  # Compare CSVs to handle Nones
True
>>> g.arbitrary == f.arbitrary  # Aribitrary properties also match
True
```

Note that in the above example we provide `allow_load=True` indicating
that the backend can dynamically figure out which of your python
classes to load the data into. If you don't like dynamically loading,
there are various ways to specify the class to load into.

## Why Frontends?

You may wonder why we need a special front-end class like
`SimpleFrame`. If you really wanted to, you could just use the
backends by themselves as a more flexible version of `pickle` or a
more limited version of a database object relational manager (ORM). In
general, though, it is nice to have both a back-end protocol and a
front-end class so that you can more intelligently do things like
control serialization/deserialization, deal with headers, and so on.

As a very simple example of this, you could modify the previous
example via

```python

>>> attr = f.get_attr_dict()
>>> attr['timezone'] = 'US/Eastern'
>>> f.save()
```

The dictionary returned by `f.get_attr_dict()` functions as a header
to store simple attributes. One advantage these special attributes
have over the usual python properties is that you can do something like.

```python

>>> h = backend.load('test', only_hdr=True)
>>> print('name:tz = %s:%s' % (h['_name'], h['_attributes']['timezone']))
name:tz = test:US/Eastern
```

In the above, we use the `only_hdr=True` option to `backend.load` to
first load only the header. This is generally a much cheaper and
faster operation than de-serializing and loading the full
object. Among other things, this header dictionary contains a `'_name'`
key with the name of the object we are loading/saving and an
`'_attributes_` key containing the dictionary provided by
`get_attr_dict()`. As a result, we can look at the header to see the
timezone and do things like:

  1. Skip the full load for objects with the wrong timezone.
  2. Deserialize differently depending on things in the attributes
     such as the timezone.
	 
 Indeed, the `SimpleFrame` class does just that. If you load the full
 object and print the frame, you will see that although we saved a
 pandas DataFrame with no timezone information, the `SimpleFrame`
 class looks for the `'timezone'` in the attributes and localize
 appropriately on loading:
 
```python
>>>  print(backend.load('test', allow_load=True).frame.index)
2017-07-01 00:00:00-04:00
```

## Key Features

The `oxtie` package is designed to simplify loading and
saving data into different backends with the following key features:

  1. Built-in `oxtie` backends can easily store data out to
     local databases, local files, Amazon S3, Amazon DynamoDB, and other
	 cloud providers.
  2. Support for serializing and storing Pandas DataFrame objects.
  3. Ability to easily implement your own backend storage to save/load
     to/from.
  4. Ability to separate backend from serialization.
	 - You may want to *serialize* in a format like JSON, BSON,
       msgpack, CSV, pickle, etc., but *store* on backends like local
       files, S3, and so on. With `oxtie` you can mix and match these
       as you like.
  5. Ability to quickly load/scan header information before loading
     the full object so you can cheaply scan through stored data
     deciding what/how to load.
  6. Ability to build intelligent front ends to do validation or other
     actions on loading or saving.

These features may seem somewhat standard and generic so it may be
worth emphasizing the one which most influenced creation of `oxtie`:
quickly load/scan header information. In the model of a modern major
data system used by many organizations you generally want to do 3
things well:

  1. Save data.
  2. Get data for which you know the key.
  3. Look for a key based on some simple search criteria.
  
In the early days, SQL databases implemented #3 very well. You can
could write arbitrarily complicated queries which let you use all
kinds of conditions to find which data to load. Later, people realized
that you often have binary large objects (BLOBs) which you don't need
to search plus header information which you do want to search. This
led to NoSQL databases which greatly improved performance at the cost
of more limited search criteria. Since NoSQL was successful, cloud
storage moved things even further providing even more limited search
capability (e.g., Amazon S3).

In many cloud storage systems, you effectively divide your data into
some simple header information or attributes such as a name, or last
update time, or region along with your non-searchable data. Your
storage and search operations essentially only involve the header so
that everything can be efficient.

Assuming you subscribe to this small header + big body paradigm, you
may start to realize that the simple save/load/scan methodology works
on lots of different systems so why should you hard-code your
application to depend on a particular backend? The answer is you
shouldn't! Use `oxtie`!

Ideally, one could even go a step further and define a simple language
independent protocol for search-load-scan (SLS) operations similar to
the SQL standard which could be implemented in various languages. With
an SLS standard, you could flexibly save something like a Pandas
DataFrame from python to S3 (or some other backend) and then load into
into the appropriate structure in some other language. The `oxtie`
package is the first step on that path.

# Frequently Asked Questions (FAQ)

## Do We Need Yet Another Serialization System?

Unfortunately, yes. If you try to naively store things like pandas
DataFrames its easy to run into multiple issues:

  1. JSON doesn't support certain types (even simple things like
     datetime let alone DataFrames). 
  2. JSON is not so efficient in terms of storage.
  3. You could use BSON but that has similar issues in type support.
  4. You could use msgpack but you need a little help to support
     things like pandas DataFrames. Even with msgpack, though, you
     probably may want additional features as described below.
  5. Most existing serialization formats don't provide support for
     automatic validation on deserialization.
  6. Often you want to serialize a time series or data table (e.g., a
     pandas DataFrame) but also include additional attributes such as
     when the data was collected, the source of the data, and so
     on). This generally means you want a class that holds your time
     series along with some other attributes.
  7. Sometimes you want to mix and match your serialization
     formats. For example, you may want to serialize an object in both
	 msgpack and CSV formats or you may want the option to sometimes
	 serializes/deserialize to/from one or the other.

For these reasons and more, it seems useful to have a lightweight
"cloud serialization" system like `oxtie` to manage persisting data in
a flexible way.

	 



