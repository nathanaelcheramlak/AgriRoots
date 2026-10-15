"""Operator-reviewed public sources; no task text, crop IDs or household data in URLs."""
SOURCES = ({"id": "nrcs-soil-health", "url": "https://www.nrcs.usda.gov/conservation-basics/natural-resource-concerns/soil/soil-health",
            "name": "USDA NRCS soil health background", "license": "US government work; retain attribution",
            "scope": "General soil-health background only; local guidance controls action applicability"},)
ALLOWED_HOSTS = frozenset({"www.nrcs.usda.gov", "nrcs.usda.gov"})
FETCH_VERSION = "2026.10.10"
