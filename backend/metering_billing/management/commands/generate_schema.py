import copy
import json

from django.core import management
from django.core.management.base import BaseCommand
from metering_billing.openapi_hooks import camelize_operation_ids
from ruamel.yaml import YAML


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
                    return sorted(obj)
                except TypeError:
                    # If items aren't comparable, return as-is
                    return obj
            else:
                # For mixed-type arrays, recursively sort contents but preserve order
                return [self._sort_dict_recursively(item) for item in obj]
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
            data_public = yaml.load(fp)
        data_private = copy.deepcopy(data_public)

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

        # Sort dictionaries recursively for deterministic output
        data_public = self._sort_dict_recursively(data_public)
        data_private = self._sort_dict_recursively(data_private)

        with open("../docs/openapi.yaml", "w") as fp:
            yaml.dump(data_public, fp)
        with open("../docs/openapi_private.yaml", "w") as fp:
            yaml.dump(data_private, fp)

        # Also generate JSON versions with sorted output
        with open("../docs/openapi.json", "w") as fp:
            json.dump(data_public, fp, indent=2, sort_keys=True)
        with open("../docs/openapi_private.json", "w") as fp:
            json.dump(data_private, fp, indent=2, sort_keys=True)
