"""Synchronous, read-only calls into an explicitly selected Golem C library."""
from __future__ import annotations

import ctypes
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal, TypedDict, cast

__all__ = ["Engine", "GolemError", "ValidationResult", "ReplayResult", "Stage", "Autonomy"]
Stage = Literal["planning", "ux", "publishing", "development", "qa", "audit"]
Autonomy = Literal["DENY", "AUTO_LOCAL", "ASK_ON_EXTERNAL_EFFECT", "ASK_ALWAYS"]


class ValidationResult(TypedDict):
    schema_version: Literal[1]
    valid: Literal[True]
    id: str
    stages: list[Stage]


class ReplayResult(TypedDict):
    schema_version: Literal[1]
    run_id: str
    state: Literal["READY", "RUNNING", "FAILED", "BLOCKED", "SUCCEEDED", "CANCELLED"]
    passed_stages: str
    stage_count: str
    bundle_verified: Literal[False]
    simulation: Literal["unknown"]
    acceptance_verified: Literal[False]
    recovery_action: Literal["NONE", "CHECK_POLICY", "RECONCILE_ATTEMPT", "EVALUATE_REENTRY", "RESOLVE_BLOCK"]
    journal_records: str
    journal_bytes: str


class GolemError(Exception):
    """C engine failure. status is the stable numeric golem_status value."""
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


class Engine:
    """Load trusted native code from an explicit absolute path; no auto-download.

    Independent calls are thread-safe; results are detached Python values.
    This object retains the library. It never owns live WorkRun handles.
    Replay is inspection only, not authorization or proof of task completion.
    """
    def __init__(self, library: str | Path):
        path = Path(library)
        if not path.is_absolute():
            raise ValueError("library must be an explicit absolute path")
        self._library = ctypes.CDLL(str(path.resolve(strict=True)))
        lib = self._library
        lib.golem_binding_abi_version.argtypes = []
        lib.golem_binding_abi_version.restype = ctypes.c_uint32
        if lib.golem_binding_abi_version() != 1:
            raise RuntimeError("unsupported Golem binding ABI")
        lib.golem_binding_call.argtypes = [ctypes.c_uint32, ctypes.c_void_p, ctypes.c_size_t,
                                           ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_size_t)]
        lib.golem_binding_call.restype = ctypes.c_int32
        lib.golem_binding_free.argtypes = [ctypes.c_void_p]
        lib.golem_binding_free.restype = None
        lib.golem_binding_status_message.argtypes = [ctypes.c_int32]
        lib.golem_binding_status_message.restype = ctypes.c_char_p

    def _call(self, operation: int, data: bytes) -> dict[str, Any]:
        limit = {1: 131072, 2: 16777216, 3: 16384}[operation]
        if not data or len(data) > limit:
            raise GolemError(1, "empty or oversized input")
        # A private buffer remains alive while ctypes releases the GIL. No
        # mutable caller buffer can race the native parser.
        buffer = ctypes.create_string_buffer(data)
        pointer, length = ctypes.c_void_p(), ctypes.c_size_t()
        status = self._library.golem_binding_call(operation, buffer, len(data), ctypes.byref(pointer), ctypes.byref(length))
        if status:
            message = self._library.golem_binding_status_message(status)
            raise GolemError(status, message.decode("utf-8"))
        try:
            value = json.loads(ctypes.string_at(pointer, length.value))
            if not isinstance(value, dict) or value.get("schema_version") != 1:
                raise RuntimeError("unsupported Golem result schema")
            return value
        finally:
            self._library.golem_binding_free(pointer)

    def validate(self, capsule: Mapping[str, Any] | str | bytes) -> ValidationResult:
        """Validate the same capsule JSON schema as the C CLI; raises GolemError."""
        if isinstance(capsule, Mapping):
            capsule = json.dumps(dict(capsule), ensure_ascii=False, allow_nan=False)
        if isinstance(capsule, str):
            capsule = capsule.encode("utf-8")
        if not isinstance(capsule, bytes):
            raise TypeError("capsule must be a mapping, JSON string or UTF-8 bytes")
        return cast(ValidationResult, self._call(1, capsule))

    def replay(self, journal: bytes | bytearray | memoryview) -> ReplayResult:
        """Strict journal replay. Valid unfinished prefixes remain unfinished."""
        if not isinstance(journal, (bytes, bytearray, memoryview)):
            raise TypeError("journal must be bytes, bytearray or memoryview")
        size = journal.nbytes if isinstance(journal, memoryview) else len(journal)
        if size > 16777216:
            raise GolemError(1, "oversized journal")
        return cast(ReplayResult, self._call(2, bytes(journal)))

    def describe_adapter(self, descriptor: Mapping[str, Any] | str | bytes) -> dict[str, Any]:
        """Validate/canonicalize a descriptor. Never probe or authorize execution."""
        if isinstance(descriptor, Mapping):
            descriptor = json.dumps(dict(descriptor), ensure_ascii=False, allow_nan=False)
        if isinstance(descriptor, str):
            descriptor = descriptor.encode("utf-8")
        if not isinstance(descriptor, bytes):
            raise TypeError("descriptor must be a mapping, JSON string or UTF-8 bytes")
        return self._call(3, descriptor)
