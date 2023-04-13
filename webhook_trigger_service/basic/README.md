# Release Notes

## 1.0.0 (2021-05-31)
* Initial Release

# Description
The files in this parent template are common for all App types and is intended to be used as the base parent for most other templates.


## Template files
├── .pre-commit-config.yaml.py
├── app_lib.py
├── coveragerc
├── gitignore
├── pyproject.toml
├── requirements.txt
└── setup.cfg

### .pre-commit-config.yaml.py (Optional)
This template file contains a default configuration for the

### app_lib.py (Required)
This template file allows for support of multiple versions of Python in one App.

### coveragerc (Optional)
his template file has a basic configuration for pytest coverage reporting.

### gitignore (Required)
This template file tries to cover the most common use cases for ignoring files in an App Project.

### pyproject.toml  (Optional)
This template file provides standard configuration for Python tools/linter (e.g. black, pylint).

### requirements.txt (Required)
The requirements file for App dependencies. This file is used by the "tcex deps" CLI command.

### setup.cfg (Optional)
This template file provides standard configuration for Python tools/linter (e.g. flake8, isort).
