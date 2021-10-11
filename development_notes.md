# Development Notes

## Why is there a coupling between the RemoteAPI and ACESystem?

Originally there was just one global system reference. This makes sense most of the time. But when testing the client/server system, there are actually two systems: the local stub system and the remote system. So it was impossible to run both at the same time for testing because they both changed what the global reference pointed to.

## Why not just use the api directly? Why have a RemoteACESystem that uses the api?

This system can also be used locally for manual (command line) analysis. I want it to work the same no matter what system is actually being used.

## Why are there three different classes for most objects?

There are three different data models that we use.

- The pydantic model classes defined in `ace/data_model.py` (used by FastAPI)
- The SQLAlchemy model classes defined in `ace/system/database/schema.py` (used by ace/system/database)
- The basic classes defined in various classes.

It would have been nice to just use one to solve all use cases. Here are the reasons there are three.

First, using a database back-end is optional. There are various other technical reasons why it would not be a good idea to try to merge the SQLAlchemy data models into the rest of the data models, but I believe that this reason is enough to not do that.

It would have made more sense to combine the pydantic models with the basic python classes. I did try this, and what I found was that pydantic introduces a lot of hidden magic behind the scenes that makes it do what it does. The one specific issue I saw was in implementing @property fields, such as the details property of an Analysis object, which might dynamically load the details if it's not loaded yet. Pydantic's implementation prevents you from doing something simple like that.

Consider this piece of code.

```python
from pydantic import BaseModel
  
class User(BaseModel):
    id: int
    name = "John Doe"
    _details = "blah"

    @property
    def details(self):
        return self._details

    @details.setter
    def details(self, value):
        self._details = value


externa_data = {
    'id': '123',
    'name': 'test',
}

user = User(**externa_data)
print(user.details)
user.details = "heya"
```

Attempting to set the `details` properties results in the following error.

```
ValueError: "User" object has no field "details"
```

Then you have to look at using what it calls [private model attributes](https://pydantic-docs.helpmanual.io/usage/models/#private-model-attributes) which has the following constraint:

```
Private attribute names must start with underscore to prevent conflicts with model fields
```

Which would mean that we would always have to use Analysis._details instead of Analysis.details. But that would also means that **every other class property and variable would also have to start with underscore**. Once I got to this point I bailed on the idea.

If we did merge them together we would always have to be dealing with pydantic in every part of the system. The pydantic data models are used to model the data for FastAPI. They are not needed for any other purpose.

Every class that is used at the FastAPI layer has translation routines that convert the class into raw json, dicts and pydantic data models in both directions. We immediately convert the pydantic model into the basic class, use the basic class to implement program logic, then convert back into the pydantic model when we send a result back to the FastAPI layer.
