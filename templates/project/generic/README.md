# Generic project template

This is the default project-type template. It does not add project-specific
overrides; the base `templates/extension/` scaffold is used as-is, and
`pipa-init-project.sh` fills in detected project facts.

For specialized projects, add a new directory under `templates/project/`
(e.g., `templates/project/node/`, `templates/project/python/`) and include
only the files that should override or extend the base scaffold.
