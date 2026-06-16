"""REST API tool adapter.

Builds a LangChain StructuredTool from a DB `tools` row whose `spec` describes an
HTTP endpoint. Secrets are resolved from a referenced Credential (env var), never
stored in the spec. A per-tool domain allowlist is enforced as egress control.

spec = {
  "base_url": "https://api.example.com",
  "method": "POST",
  "path": "/v1/things/{id}",
  "headers": {"Accept": "application/json"},
  "params": {"id": {"type": "string", "required": true, "in": "path"},
             "q":  {"type": "string", "in": "query"},
             "body": {"type": "object", "in": "body"}},
  "allowlist": ["api.example.com"]
}
"""

import os
from urllib.parse import urlparse

import httpx
from langchain_core.tools import StructuredTool
from pydantic import create_model

from .base import ToolAdapter

_PY_TYPES = {"string": str, "integer": int, "number": float, "boolean": bool, "object": dict, "array": list}


class RestApiToolAdapter(ToolAdapter):
    def __init__(self, slug: str, description: str, spec: dict, secret: str | None) -> None:
        self.slug = slug
        self.description = description
        self.spec = spec
        self._secret = secret

    @classmethod
    def from_row(cls, row) -> "RestApiToolAdapter":
        secret = None
        cred_ref = (row.spec or {}).get("credential_ref")
        if cred_ref:
            secret = os.environ.get(cred_ref)
        return cls(row.slug, row.description or "", row.spec or {}, secret)

    def _args_model(self):
        fields = {}
        for name, meta in (self.spec.get("params") or {}).items():
            py = _PY_TYPES.get(meta.get("type", "string"), str)
            default = ... if meta.get("required") else None
            fields[name] = (py if meta.get("required") else (py | None), default)
        return create_model(f"{self.slug}_Args", **fields) if fields else create_model(f"{self.slug}_Args")

    def _check_allowlist(self, url: str) -> None:
        allow = self.spec.get("allowlist")
        if allow and urlparse(url).hostname not in allow:
            raise ValueError(f"Egress to {urlparse(url).hostname} not in allowlist")

    def to_langchain_tool(self) -> StructuredTool:
        spec = self.spec
        method = spec.get("method", "GET").upper()
        base = spec.get("base_url", "").rstrip("/")
        path_tmpl = spec.get("path", "")
        headers = dict(spec.get("headers") or {})
        if self._secret:
            headers.setdefault("Authorization", f"Bearer {self._secret}")
        params_meta = spec.get("params") or {}

        def _call(**kwargs) -> str:
            path = path_tmpl
            query, body = {}, {}
            for name, meta in params_meta.items():
                if name not in kwargs or kwargs[name] is None:
                    continue
                where = meta.get("in", "query")
                if where == "path":
                    path = path.replace("{" + name + "}", str(kwargs[name]))
                elif where == "body":
                    body = kwargs[name] if isinstance(kwargs[name], dict) else {name: kwargs[name]}
                else:
                    query[name] = kwargs[name]
            url = base + path
            self._check_allowlist(url)
            try:
                resp = httpx.request(method, url, headers=headers, params=query or None,
                                     json=body or None, timeout=60)
                return f"{resp.status_code}\n{resp.text[:4000]}"
            except Exception as e:
                return f"REST tool error: {e}"

        return StructuredTool.from_function(
            func=_call, name=self.slug, description=self.description,
            args_schema=self._args_model(),
        )
