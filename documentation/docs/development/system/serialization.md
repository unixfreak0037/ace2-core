# Serialization

Data is tracked by the core system in JSON format. The schema of the JSON data is defined in [ace/data_model.py](https://github.com/ace-ecosystem/ace2-core/blob/main/ace/data_model.py) by using the pydantic library.

The data model is separate from the classes that use them. Each classes defined here has a corresponding class. For example, `ace.data_model.DetectionPointModel` is the data model for `ace.analysis.DetectionPoint`.

The models are used to translate between Python objects and JSON strings, and vice versa. Every Python class that has a corresponding data model defines a `to_dict()` and `to_json()` function, as well as class methods for `from_dict()` and `from_json()`.

The JSON encoder defined for the pydantic library is used to encode and decode complex data types such as dates. Therefor always use the `to_json()` and `from_json()` functions to translate rather than using `import json`.
