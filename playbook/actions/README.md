# Action Playbook Template

# Release Notes

### 1.0.0 (2021-04-22)

* Initial Release


# Description

Takes a String or StringArrays and perform operations to each value returning the update value. All operations are performed on the individual strings and not the array.
# Actions

___
## Capitalize
### Inputs

### *Configure*

  **Strings** *(String)*
  The input String or StringArray.
  > **Allows:** String, StringArray

### Outputs

  - string.action *(String)*
  - string.outputs.0 *(String)*
  - string.outputs.count *(String)*
  - string.outputs *(StringArray)*

___
## Lowercase
### Inputs

### *Configure*

  **Strings** *(String)*
  The input String or StringArray.
  > **Allows:** String, StringArray

### Outputs

  - string.action *(String)*
  - string.outputs.0 *(String)*
  - string.outputs.count *(String)*
  - string.outputs *(StringArray)*

___
## Prepend
### Inputs

### *Configure*

  **Strings** *(String)*
  The input String or StringArray.
  > **Allows:** String, StringArray

  **Prepend Character(s)** *(String)*
  The character(s) to get prepended to the provided string(s) (e.g., **pre-**).

### Outputs

  - string.action *(String)*
  - string.outputs.0 *(String)*
  - string.outputs.count *(String)*
  - string.outputs *(StringArray)*

___
## Reverse
### Inputs

### *Configure*

  **Strings** *(String)*
  The input String or StringArray.
  > **Allows:** String, StringArray

### Outputs

  - string.action *(String)*
  - string.outputs.0 *(String)*
  - string.outputs.count *(String)*
  - string.outputs *(StringArray)*

___
## Starts With
### Inputs

### *Configure*

  **Strings** *(String)*
  The input String or StringArray.
  > **Allows:** String, StringArray

  **Starts With Character(s)** *(String)*
  The character(s) to check for in the provided string(s) (e.g., **https**).

  _**Starts With Start**_ *(String, Optional, Default: 0)*
  The 0-based index position at which to start the **Starts With** search. The start position can be used to skip the first *n* characters before starting the search.

  _**Starts With Stop**_ *(String, Optional)*
  The 0-based index position at which to stop the **Starts With** search. The stop position can be used to stop the search after *n* characters.

### Outputs

  - string.action *(String)*
  - string.outputs.0 *(String)*
  - string.outputs.count *(String)*
  - string.outputs *(StringArray)*

___
## Strip
### Inputs

### *Configure*

  **Strings** *(String)*
  The input String or StringArray.
  > **Allows:** String, StringArray

### Outputs

  - string.action *(String)*
  - string.outputs.0 *(String)*
  - string.outputs.count *(String)*
  - string.outputs *(StringArray)*

___
## Swap Case
### Inputs

### *Configure*

  **Strings** *(String)*
  The input String or StringArray.
  > **Allows:** String, StringArray

### Outputs

  - string.action *(String)*
  - string.outputs.0 *(String)*
  - string.outputs.count *(String)*
  - string.outputs *(StringArray)*

___
## Title Case
### Inputs

### *Configure*

  **Strings** *(String)*
  The input String or StringArray.
  > **Allows:** String, StringArray

### Outputs

  - string.action *(String)*
  - string.outputs.0 *(String)*
  - string.outputs.count *(String)*
  - string.outputs *(StringArray)*

___
## Uppercase
### Inputs

### *Configure*

  **Strings** *(String)*
  The input String or StringArray.
  > **Allows:** String, StringArray

### Outputs

  - string.action *(String)*
  - string.outputs.0 *(String)*
  - string.outputs.count *(String)*
  - string.outputs *(StringArray)*

# Category

Utility
