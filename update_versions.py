"""This script is run from docs_deploy.yml

It writes JSON like this:

    {"latest": "refs/heads/main"}

To a file called versions.json at the root
of the docs branch.

It will also update index.html to point to the
latest stable (released) version, or if no released versions
exist, the the main branch's version.
"""

from json import dumps
import os
from packaging.version import parse

base = "refs"
branch_names = {"master": "latest"}  # rename branches here
permalink = ["latest", "stable"]  # create permalinks at root level
stable = None

versions = dict()

if os.path.exists(os.path.join(base, "heads")):
    for branch in sorted(os.listdir(os.path.join(base, "heads"))):
        if branch not in branch_names:
            continue
        bname = branch_names[branch]
        versions[bname] = "/".join((base, "heads", branch))
if os.path.exists(os.path.join(base, "tags")):
    tags = []
    for tag in os.listdir(os.path.join(base, "tags")):
        if os.path.isdir(os.path.join(base, "tags", tag)):
            tags.append(tag)
    tags.sort(key=lambda v: parse(v))
    for tag in tags[:-1]:
        versions[tag] = "/".join((base, "tags", tag))
    stable = "/".join((base, "tags", tags[-1]))
    versions["stable"] = stable

# Create a versions.json that can be used to display versions
with open("versions.json", "w") as f:
    f.write(dumps(versions))

# Create symlinks to latest and stable versions to enable
# permalinks
for f in os.listdir("."):
    if os.path.islink(f):
        os.remove(f)
for target in permalink:
    source = versions[target]
    os.symlink(source, target)

# Create an index.html to redirect to the stable version
# or latest if stable does not exist
if stable:
    redirect = "stable/"
elif "latest" in branch_names.values():
    redirect = "latest/"
else:
    raise ValueError(
        "You must specify a `latest` branch or have at least one tagged version (`stable`)."
    )
with open("index.html", "w") as f:
    data = """<meta http-equiv="refresh" content="0; URL='""" + redirect + """'" />"""
    f.write(data)
