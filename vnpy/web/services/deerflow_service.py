from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests
from fastapi import UploadFile


@dataclass
class DeerFlowChatResult:
    ok: bool
    content: str
    backend: str
    thread_id: str | None = None
    error: str | None = None


class DeerFlowService:
    """Thin adapter around the local DeerFlow HTTP Gateway."""

    def __init__(self) -> None:
        raw_enabled = os.getenv("TENX_DEERFLOW_ENABLED", "").strip().lower()
        self.enabled = raw_enabled not in {"0", "false", "no", "off"}
        self.assistant_id = (
            os.getenv("TENX_DEERFLOW_ASSISTANT_ID")
            or os.getenv("DEERFLOW_ASSISTANT_ID")
            or "tenx-hunter-agent"
        ).strip()
        self.base_url = (
            os.getenv("TENX_DEERFLOW_URL")
            or os.getenv("DEERFLOW_URL")
            or "http://127.0.0.1:2026"
        ).rstrip("/")
        self.host_state_dir = Path(
            os.getenv("TENX_DEERFLOW_HOST_STATE_DIR")
            or (
                Path(__file__).resolve().parents[4]
                / "deer-flow"
                / "backend"
                / ".deer-flow"
            )
        )
        self.timeout = float(os.getenv("TENX_DEERFLOW_TIMEOUT_SECONDS", "180"))
        self.stream_mode = os.getenv("TENX_DEERFLOW_STREAM_MODE", "values,messages,updates")
        self._ocr_script_path = Path(__file__).resolve().parents[1] / "scripts" / "macos_vision_ocr.swift"

    @staticmethod
    def _normalize_thread_id(thread_id: str | None) -> str | None:
        if thread_id is None:
            return None

        normalized = re.sub(r"[^a-zA-Z0-9_-]+", "-", thread_id.strip().lower())
        normalized = re.sub(r"-{2,}", "-", normalized).strip("-.")
        if not normalized:
            return None

        return normalized[:120]

    def _resolve_local_upload_path(self, thread_id: str, file: dict[str, Any]) -> Path | None:
        host_path = file.get("path")
        filename = str(file.get("filename") or "")
        if not filename:
            return None

        if isinstance(host_path, str) and host_path:
            candidate = Path(host_path)
            if candidate.exists():
                return candidate

        inferred = self.host_state_dir / "threads" / thread_id / "user-data" / "uploads" / filename
        if inferred.exists():
            return inferred

        return None

    def _extract_image_ocr(self, thread_id: str, file: dict[str, Any]) -> list[str]:
        filename = str(file.get("filename") or "")
        if not filename.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
            return []
        if os.uname().sysname != "Darwin":
            return []
        if not self._ocr_script_path.exists():
            return []

        local_path = self._resolve_local_upload_path(thread_id, file)
        if local_path is None:
            return []

        try:
            result = subprocess.run(
                ["/usr/bin/swift", str(self._ocr_script_path), str(local_path)],
                capture_output=True,
                text=True,
                check=True,
                timeout=20,
            )
            payload = json.loads(result.stdout)
            lines = payload.get("lines")
            if not isinstance(lines, list):
                return []
            return [str(line).strip() for line in lines if str(line).strip()]
        except Exception:
            return []

    def _build_uploaded_files_context(self, thread_id: str, files: list[dict[str, Any]]) -> str:
        if not files:
            return ""

        image_files = [
            str(file.get("filename") or "unnamed-file")
            for file in files
            if str(file.get("filename") or "").lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".gif"))
        ]
        lines = ["<uploaded_files>", "The following files were uploaded in this message:", ""]
        for file in files:
            filename = str(file.get("filename") or "unnamed-file")
            size = str(file.get("size") or "unknown-size")
            virtual_path = str(file.get("virtual_path") or file.get("path") or "")
            ocr_lines = self._extract_image_ocr(thread_id, file)
            lines.append(f"- {filename} ({size} bytes)")
            if virtual_path:
                lines.append(f"  Path: {virtual_path}")
            markdown_virtual_path = file.get("markdown_virtual_path")
            if isinstance(markdown_virtual_path, str) and markdown_virtual_path:
                lines.append(f"  Markdown Path: {markdown_virtual_path}")
            if ocr_lines:
                lines.append("  OCR Text (authoritative for this turn):")
                for line in ocr_lines[:80]:
                    lines.append(f"    {line}")
            elif filename.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".gif")) and virtual_path:
                lines.append(f"  For image understanding, use view_image on: {virtual_path}")
            lines.append("")

        if image_files:
            joined = ", ".join(image_files)
            lines.append("IMPORTANT FOR THIS TURN:")
            lines.append(f"- Analyze ONLY the newly uploaded image file(s) from this message: {joined}")
            if any(self._extract_image_ocr(thread_id, file) for file in files):
                lines.append("- OCR text is present above. Treat it as the primary source of truth for the uploaded screenshot.")
                lines.append("- Do NOT call `view_image`, `read_file`, `glob`, `grep`, `bash`, or any other tools if the OCR text is sufficient.")
                lines.append("- Produce your final answer directly from the OCR text and the current TenX context.")
            else:
                lines.append("- Call `view_image` at most once per newly uploaded image file.")
                lines.append("- After `view_image` succeeds, do NOT call `view_image`, `read_file`, `glob`, `grep`, `bash`, or any other tools again for the same image.")
                lines.append("- Use the injected image content from `ViewImageMiddleware` to produce your final answer immediately.")
            lines.append("- Ignore images from previous turns unless the user explicitly asks you to compare them.")
            lines.append("")

        lines.append("Uploaded files are available in the current DeerFlow thread workspace.")
        lines.append("</uploaded_files>")
        return "\n".join(lines)

    def _build_input(self, thread_id: str, prompt: str, files: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        uploaded_files_context = self._build_uploaded_files_context(thread_id, files or [])
        content_parts: list[dict[str, Any]] = []
        if uploaded_files_context:
            content_parts.append({"type": "text", "text": uploaded_files_context})
        content_parts.append({"type": "text", "text": prompt})

        return {
            "messages": [
                {
                    "type": "human",
                    "content": content_parts,
                    "additional_kwargs": {
                        "files": files or [],
                    },
                }
            ]
        }

    def chat(self, prompt: str, *, thread_id: str | None = None, files: list[dict[str, Any]] | None = None) -> DeerFlowChatResult:
        if not self.enabled:
            return DeerFlowChatResult(
                ok=False,
                content="",
                backend="disabled",
                thread_id=thread_id,
                error="DeerFlow integration is disabled.",
            )

        try:
            resolved_thread_id = self._normalize_thread_id(thread_id) or "vnpy-default-thread"
            self._ensure_thread(resolved_thread_id)
            response = self._wait_run(resolved_thread_id, prompt, files=files)
        except Exception as exc:  # pragma: no cover - depends on external runtime
            return DeerFlowChatResult(
                ok=False,
                content="",
                backend="error",
                thread_id=thread_id,
                error=f"DeerFlow request failed: {exc}",
            )

        content = self._extract_content(response)

        if not content:
            return DeerFlowChatResult(
                ok=False,
                content="",
                backend="empty",
                thread_id=resolved_thread_id,
                error="DeerFlow returned an empty response.",
            )

        return DeerFlowChatResult(
            ok=True,
            content=content,
            backend="deerflow",
            thread_id=resolved_thread_id,
        )

    def _ensure_thread(self, thread_id: str) -> None:
        response = requests.post(
            f"{self.base_url}/api/threads",
            json={
                "thread_id": thread_id,
                "metadata": {
                    "source": "vnpy",
                },
            },
            timeout=self.timeout,
        )
        response.raise_for_status()

    def _wait_run(self, thread_id: str, prompt: str, files: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        response = requests.post(
            f"{self.base_url}/api/threads/{thread_id}/runs/wait",
            json={
                "assistant_id": self.assistant_id,
                "input": self._build_input(thread_id, prompt, files=files),
                "context": {
                    "thinking_enabled": True,
                },
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("DeerFlow returned a non-object response.")
        return payload

    def get_state(self, thread_id: str) -> dict[str, Any]:
        resolved_thread_id = self._normalize_thread_id(thread_id) or thread_id
        response = requests.get(
            f"{self.base_url}/api/threads/{resolved_thread_id}/state",
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("DeerFlow state returned a non-object response.")
        return payload

    def get_history(self, thread_id: str, *, limit: int = 10) -> list[dict[str, Any]]:
        resolved_thread_id = self._normalize_thread_id(thread_id) or thread_id
        response = requests.post(
            f"{self.base_url}/api/threads/{resolved_thread_id}/history",
            json={"limit": limit},
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list):
            raise ValueError("DeerFlow history returned a non-list response.")
        return [item for item in payload if isinstance(item, dict)]

    def search_threads(self, *, limit: int = 20, metadata: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        response = requests.post(
            f"{self.base_url}/api/threads/search",
            json={
                "limit": limit,
                "metadata": metadata or {},
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list):
            raise ValueError("DeerFlow thread search returned a non-list response.")
        return [item for item in payload if isinstance(item, dict)]

    def list_uploads(self, thread_id: str) -> dict[str, Any]:
        resolved_thread_id = self._normalize_thread_id(thread_id) or thread_id
        response = requests.get(
            f"{self.base_url}/api/threads/{resolved_thread_id}/uploads/list",
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("DeerFlow uploads returned a non-object response.")
        return payload

    def upload_files(self, thread_id: str, files: list[UploadFile]) -> dict[str, Any]:
        resolved_thread_id = self._normalize_thread_id(thread_id) or thread_id
        multipart: list[tuple[str, tuple[str, Any, str]]] = []
        opened_files: list[Any] = []
        try:
            for file in files:
                file.file.seek(0)
                opened_files.append(file.file)
                multipart.append(
                    (
                        "files",
                        (
                            file.filename or "upload.bin",
                            file.file,
                            file.content_type or "application/octet-stream",
                        ),
                    )
                )

            response = requests.post(
                f"{self.base_url}/api/threads/{resolved_thread_id}/uploads",
                files=multipart,
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                raise ValueError("DeerFlow upload returned a non-object response.")
            return payload
        finally:
            for file in opened_files:
                try:
                    file.close()
                except Exception:
                    pass

    def get_artifact(self, thread_id: str, path: str, *, download: bool = False) -> requests.Response:
        resolved_thread_id = self._normalize_thread_id(thread_id) or thread_id
        response = requests.get(
            f"{self.base_url}/api/threads/{resolved_thread_id}/artifacts/{path}",
            params={"download": str(download).lower()},
            timeout=self.timeout,
            stream=True,
        )
        response.raise_for_status()
        return response

    def stream(self, prompt: str, *, thread_id: str | None = None, files: list[dict[str, Any]] | None = None):
        if not self.enabled:
            raise RuntimeError("DeerFlow integration is disabled.")

        resolved_thread_id = self._normalize_thread_id(thread_id) or "vnpy-default-thread"
        self._ensure_thread(resolved_thread_id)

        response = requests.post(
            f"{self.base_url}/api/threads/{resolved_thread_id}/runs/stream",
            json={
                "assistant_id": self.assistant_id,
                "input": self._build_input(resolved_thread_id, prompt, files=files),
                "context": {
                    "thinking_enabled": True,
                },
                "stream_mode": [item.strip() for item in self.stream_mode.split(",") if item.strip()],
            },
            timeout=(10, self.timeout),
            stream=True,
        )
        response.raise_for_status()
        return resolved_thread_id, response.iter_lines(decode_unicode=True)

    @staticmethod
    def _extract_content(response: dict[str, Any]) -> str:
        messages = response.get("messages")
        if isinstance(messages, list):
            for message in reversed(messages):
                if not isinstance(message, dict):
                    continue
                if message.get("type") != "ai":
                    continue
                content = message.get("content")
                if isinstance(content, str) and content.strip():
                    return content.strip()
        return ""
