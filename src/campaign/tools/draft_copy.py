"""Advertising copy drafting and compliance validation tool."""

from __future__ import annotations

import json
from typing import Any

from langchain_core.tools import tool
from pydantic import ValidationError

from campaign.compliance import check_copy_compliance
from campaign.models import (
    ChannelType,
    DraftCopyArgs,
    EmailCopy,
    GoogleAdsCopy,
    InstagramCopy,
)


@tool(args_schema=DraftCopyArgs)
def draft_copy(
    channel: ChannelType,
    fields: dict[str, Any],
) -> str:
    """Validate, normalize, and check compliance for channel advertising copy."""
    # Step 1: Validate against channel model
    try:
        if channel == "google_ads":
            model = GoogleAdsCopy.model_validate(fields)
        elif channel == "instagram":
            model = InstagramCopy.model_validate(fields)
        elif channel == "email":
            model = EmailCopy.model_validate(fields)
        else:
            return json.dumps(
                {"ok": False, "errors": [f"Unsupported channel '{channel}'"]},
                ensure_ascii=True,
            )
    except ValidationError as e:
        errors = [f"{err['loc']}: {err['msg']}" for err in e.errors()]
        return json.dumps({"ok": False, "errors": errors}, ensure_ascii=True)
    except (TypeError, ValueError, KeyError) as e:
        return json.dumps({"ok": False, "errors": [str(e)]}, ensure_ascii=True)

    # Step 2: Check compliance rules across all string fields
    compliance_errors: list[str] = []
    copy_dict = model.model_dump()
    for value in copy_dict.values():
        if isinstance(value, str):
            errs = check_copy_compliance(value)
            compliance_errors.extend(errs)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, str):
                    errs = check_copy_compliance(item)
                    compliance_errors.extend(errs)

    if compliance_errors:
        return json.dumps({"ok": False, "errors": compliance_errors}, ensure_ascii=True)

    return json.dumps({"ok": True, "copy": copy_dict}, ensure_ascii=True)


def _handle_error(e: Exception) -> str:
    return json.dumps({"ok": False, "errors": [f"INVALID_ARG: {e}"]}, ensure_ascii=True)


draft_copy.handle_validation_error = _handle_error
draft_copy.handle_tool_error = _handle_error
