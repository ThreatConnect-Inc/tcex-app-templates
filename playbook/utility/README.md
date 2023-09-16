# JSON Pretty

## Release Notes

### 1.0.0

-   Initial Release

# Category

-   Utility

# Description

Take raw JSON string and output "pretty" version with provide indent level. Optionally sort the keys.

# Inputs

### *Inputs*

**JSON Data** *(TypeEnum.String)*

The JSON data to be formatted.

> **Allows:** KeyValue, KeyValueArray, String, StringArray, TCEntity, TCEntityArray

_**Indent**_ *(TypeEnum.String, Optional, Default: 4)*

The number of spaces to use for indention (default: 4).

**Sort Keys** *(Boolean, Default: Unselected)*

Indicates whether keys should be sorted.

# Outputs

-   json.pretty *(String)*
