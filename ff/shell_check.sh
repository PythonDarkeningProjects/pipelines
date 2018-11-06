#!/usr/bin/env bash

# Running static analysis for Shell
# ---------------------------------

# This script runs the shellcheck tool with the same options
# it is run in the Jenkins CI server.
# Developers can use it to validate their code locally before
# pushing the code for review.

set -o pipefail
find . -type f -name "*.sh" -print0 | xargs -0 shellcheck -f checkstyle | tee shellcheck-output.xml
set +o pipefail
