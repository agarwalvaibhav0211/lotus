def sort_schema_deterministically(endpoints):
    """Sort endpoints and parameters for deterministic schema generation"""
    # Sort endpoints by path
    sorted_endpoints = sorted(endpoints, key=lambda x: str(x[0]))
    return sorted_endpoints


def remove_invalid_subscription_methods(endpoints):
    # your modifications to the list of operations that are exposed in the schema
    to_remove = []
    for path, path_regex, method, callback in endpoints:
        if (path == r"/api/subscriptions/" and method == "POST") or (
            path == r"/api/subscriptions/{subscription_id}/"
        ):
            to_remove.append((path, path_regex, method, callback))
    for item in to_remove:
        endpoints.remove(item)
    return endpoints


def remove_required_parent_plan_and_target_customer(result, **kwargs):
    schemas = result.get("components", {}).get("schemas", {})
    schemas["Plan"]["required"] = [
        x
        for x in schemas["Plan"]["required"]
        if x not in ["parent_plan", "target_customer"]
    ]
    return result


def remove_required_address_from_lw_cust_invoice(result, **kwargs):
    schemas = result.get("components", {}).get("schemas", {})
    schemas["LightweightCustomerSerializerForInvoice"]["required"] = [
        x
        for x in schemas["LightweightCustomerSerializerForInvoice"]["required"]
        if x not in ["address"]
    ]
    schemas["Seller"]["required"] = [
        x for x in schemas["Seller"]["required"] if x not in ["address"]
    ]
    schemas["Customer"]["required"] = [
        x for x in schemas["Customer"]["required"] if x not in ["address"]
    ]
    return result


def remove_required_external_payment_obj_type(result, **kwargs):
    schemas = result.get("components", {}).get("schemas", {})
    schemas["LightweightInvoice"]["required"] = [
        x
        for x in schemas["LightweightInvoice"]["required"]
        if x not in ["external_payment_obj_type"]
    ]
    return result


def add_external_payment_obj_type_to_required(result, **kwargs):
    schemas = result.get("components", {}).get("schemas", {})
    if "external_payment_obj_type" not in schemas["LightweightInvoice"]["required"]:
        schemas["LightweightInvoice"]["required"].append("external_payment_obj_type")
    return result


def add_plan_id_parent_plan_target_customer_to_required(result, **kwargs):
    schemas = result.get("components", {}).get("schemas", {})
    if "plan_id" not in schemas["Plan"]["required"]:
        schemas["Plan"]["required"].append("plan_id")
    if "parent_plan" not in schemas["Plan"]["required"]:
        schemas["Plan"]["required"].append("parent_plan")
    if "target_customer" not in schemas["Plan"]["required"]:
        schemas["Plan"]["required"].append("target_customer")
    return result


def sort_enums_and_required_fields(result, **kwargs):
    """Sort all enum arrays and required fields lists for deterministic output"""

    def sort_recursive(obj):
        if isinstance(obj, dict):
            for key, value in obj.items():
                if (
                    key == "enum"
                    and isinstance(value, list)
                    and all(isinstance(v, str) for v in value)
                ):
                    obj[key] = sorted(value)
                elif key == "required" and isinstance(value, list):
                    obj[key] = sorted(value)
                else:
                    sort_recursive(value)
        elif isinstance(obj, list):
            for item in obj:
                sort_recursive(item)

    sort_recursive(result)
    return result
