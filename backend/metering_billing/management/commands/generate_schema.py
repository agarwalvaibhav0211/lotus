import copy
import json

from django.core import management
from django.core.management.base import BaseCommand
from metering_billing.openapi_hooks import camelize_operation_ids
from ruamel.yaml import YAML
from ruamel.yaml.scalarstring import SingleQuotedScalarString

# Strings that a YAML 1.1 parser resolves to a bool or null when unquoted.
# ruamel emits YAML 1.2, where these are plain strings and need no quoting, so
# it writes them bare — and then PyYAML (1.1) reads them back as non-strings.
# The country enum contains "NO" (Norway), which round-trips to False that way.
YAML_1_1_AMBIGUOUS = frozenset(
    "y Y yes Yes YES n N no No NO true True TRUE false False FALSE "
    "on On ON off Off OFF null Null NULL ~".split()
)


class Command(BaseCommand):
    "Django command to execute calculate invoice"

    def _sort_dict_recursively(self, obj):
        """Recursively sort all dictionaries and enum arrays for deterministic output"""
        if isinstance(obj, dict):
            return {k: self._sort_dict_recursively(obj[k]) for k in sorted(obj.keys())}
        elif isinstance(obj, list):
            # Sort string-only arrays (enum values, required fields)
            if obj and all(isinstance(item, str) for item in obj):
                try:
                    return [self._sort_dict_recursively(item) for item in sorted(obj)]
                except TypeError:
                    # If items aren't comparable, return as-is
                    return obj
            else:
                # For mixed-type arrays, recursively sort contents but preserve order
                return [self._sort_dict_recursively(item) for item in obj]
        elif isinstance(obj, str) and obj in YAML_1_1_AMBIGUOUS:
            # Force quoting so 1.1 parsers still read these back as strings.
            return SingleQuotedScalarString(obj)
        return obj

    def handle(self, *args, **options):
        management.call_command(
            "spectacular",
            "--file",
            "../docs/openapi_full.yaml",
            "--color",
            "--validate",
        )

        yaml = YAML()  # default, if not specfied, is 'rt' (round-trip)
        yaml.sort_base_mapping_type_on_output = True  # Enable sorted output
        with open("../docs/openapi_full.yaml") as fp:
            data_full = yaml.load(fp)
        data_public = copy.deepcopy(data_full)
        data_private = copy.deepcopy(data_full)

        lst = list(data_public["paths"].keys())
        for x in lst:
            if x.startswith("/api/"):
                del data_private["paths"][x]
            else:
                del data_public["paths"][x]

        # Public spec (the actual Lotus API) gets camelCase operationIds;
        # private spec feeds frontend/src/gen-types.ts and must keep the
        # snake_case operationIds that `operations["..."]` lookups rely on.
        data_public = camelize_operation_ids(data_public)

        # Sort dictionaries recursively for deterministic output. This matters
        # beyond tidiness: several serializers build Meta.fields via set
        # arithmetic (e.g. tuple(set(Parent.Meta.fields) - {...})), so field
        # order varies with PYTHONHASHSEED and the raw spectacular output
        # differs on every run. Sorting pins the ordering regardless.
        data_full = self._sort_dict_recursively(data_full)
        data_public = self._sort_dict_recursively(data_public)
        data_private = self._sort_dict_recursively(data_private)

        # Rewrite the full spec from the sorted copy — spectacular wrote it
        # unsorted above.
        with open("../docs/openapi_full.yaml", "w") as fp:
            yaml.dump(data_full, fp)

        with open("../docs/openapi.yaml", "w") as fp:
            yaml.dump(data_public, fp)
        with open("../docs/openapi_private.yaml", "w") as fp:
            yaml.dump(data_private, fp)

        # Also generate JSON versions with sorted output
        with open("../docs/openapi.json", "w") as fp:
            json.dump(data_public, fp, indent=2, sort_keys=True)
        with open("../docs/openapi_private.json", "w") as fp:
            json.dump(data_private, fp, indent=2, sort_keys=True)
