# Generic project template

This is the default project-type template. It does not add project-specific
overrides on top of the thin scaffold in `templates/project_scaffold/`;
and `pipa init` fills in detected project facts.

For specialized projects, add a new directory under `templates/project/`
(e.g., `templates/project/node/`, `templates/project/python/`) and include
only the files that should override or extend the base scaffold.
