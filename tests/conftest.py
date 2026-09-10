

# NEXUS UNDERSTANDING TEST ISOLATION
#
# Normal deterministic unit tests must never load the real
# 7B Understanding Model. Dedicated live-model tests opt in
# explicitly when required.
import os

os.environ.setdefault(
    "NEXUS_UNDERSTANDING_MODE",
    "OFF",
)
