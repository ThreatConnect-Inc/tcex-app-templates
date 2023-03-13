# String Operation

## Release Notes

### 1.0.0

-   Initial Release

# Category

-   Utility

# Description

Takes a String or StringArrays and perform operations to each value returning the update value. All operations are performed on the individual strings and not the array.

# Actions

---

## Capitalize

### Inputs

### *Configure*

**Strings** *(TypeEnum.String)*

The input String or StringArray.

> **Allows:** String, StringArray

### Outputs

-   string.action *(String)*
-   string.outputs *(StringArray)*
-   string.outputs.0 *(String)*
-   string.outputs.count *(String)*

---

## Lowercase

### Inputs

### *Configure*

**Strings** *(TypeEnum.String)*

The input String or StringArray.

> **Allows:** String, StringArray

### Outputs

-   string.action *(String)*
-   string.outputs *(StringArray)*
-   string.outputs.0 *(String)*
-   string.outputs.count *(String)*

---

## Prepend

### Inputs

### *Configure*

**Strings** *(TypeEnum.String)*

The input String or StringArray.

> **Allows:** String, StringArray

**Prepend Character(s)** *(TypeEnum.String)*

The character(s) to get prepended to the provided string(s) (e.g., **pre-**).

### Outputs

-   string.action *(String)*
-   string.outputs *(StringArray)*
-   string.outputs.0 *(String)*
-   string.outputs.count *(String)*

---

## Reverse

### Inputs

### *Configure*

**Strings** *(TypeEnum.String)*

The input String or StringArray.

> **Allows:** String, StringArray

### Outputs

-   string.action *(String)*
-   string.outputs *(StringArray)*
-   string.outputs.0 *(String)*
-   string.outputs.count *(String)*

---

## Starts With

### Inputs

### *Configure*

**Strings** *(TypeEnum.String)*

The input String or StringArray.

> **Allows:** String, StringArray

**Starts With Character(s)** *(TypeEnum.String)*

The character(s) to check for in the provided string(s) (e.g., **https**).

_**Starts With Start**_ *(TypeEnum.String, Optional, Default: 0)*

The 0-based index position at which to start the **Starts With** search. The start position can be used to skip the first *n* characters before starting the search.

_**Starts With Stop**_ *(TypeEnum.String, Optional)*

The 0-based index position at which to stop the **Starts With** search. The stop position can be used to stop the search after *n* characters.

### Outputs

-   string.action *(String)*
-   string.outputs *(StringArray)*
-   string.outputs.0 *(String)*
-   string.outputs.count *(String)*

---

## Strip

### Inputs

### *Configure*

**Strings** *(TypeEnum.String)*

The input String or StringArray.

> **Allows:** String, StringArray

### Outputs

-   string.action *(String)*
-   string.outputs *(StringArray)*
-   string.outputs.0 *(String)*
-   string.outputs.count *(String)*

---

## Swap Case

### Inputs

### *Configure*

**Strings** *(TypeEnum.String)*

The input String or StringArray.

> **Allows:** String, StringArray

### Outputs

-   string.action *(String)*
-   string.outputs *(StringArray)*
-   string.outputs.0 *(String)*
-   string.outputs.count *(String)*

---

## Title Case

### Inputs

### *Configure*

**Strings** *(TypeEnum.String)*

The input String or StringArray.

> **Allows:** String, StringArray

### Outputs

-   string.action *(String)*
-   string.outputs *(StringArray)*
-   string.outputs.0 *(String)*
-   string.outputs.count *(String)*

---

## Uppercase

### Inputs

### *Configure*

**Strings** *(TypeEnum.String)*

The input String or StringArray.

> **Allows:** String, StringArray

### Outputs

-   string.action *(String)*
-   string.outputs *(StringArray)*
-   string.outputs.0 *(String)*
-   string.outputs.count *(String)*

---
