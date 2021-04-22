# Playbook Utility

# Release Notes

### 1.0.0 (2021-04-22)

* Initial Release


# Description

Take raw JSON string and output "pretty" with provide indent level.

### Inputs

  **JSON Data** *(String)*
  The JSON data to be formatted.
  > **Allows:** KeyValue, KeyValueArray, String, StringArray, TCEntity, TCEntityArray

  _**Indent**_ *(String, Optional, Default: 4)*
  The number of spaces to use for indention (default: 4).

  **Sort Keys** *(Boolean, Default: Unselected)*
  Indicates whether keys should be sorted.

### Outputs

  - json.pretty *(String)*

# Category

Utility
