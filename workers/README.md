# workers/

The only runtime code in the project.

`suggest/` is an anonymous suggestion bridge: a submitter with no GitHub
account gets a GitHub Issue. It handles contributions and nothing else. Every
reader-facing feature degrades to a `mailto:` link, so deleting this directory
breaks contributions but not reading.
