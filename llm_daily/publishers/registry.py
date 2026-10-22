"""Choose and run publishers named in LLMDAILY_PUBLISHERS."""

import logging
import os
from typing import Any, Callable, Dict, List, Optional

from .base import Issue, Publisher

logger = logging.getLogger(__name__)

DEFAULT_PUBLISHERS = "archive"
LOCAL_PUBLISHERS = {"archive"}


class _ButtondownAdapter:
    name = "buttondown"

    def __init__(self):
        from .buttondown_publisher import ButtondownPublisher

        self._publisher = ButtondownPublisher()

    def publish(self, issue: Issue) -> Dict[str, Any]:
        result = self._publisher.publish(issue.markdown, subject=issue.subject)
        if "error" in result:
            raise RuntimeError(f"Buttondown error {result.get('status_code')}: {result['error']}")
        return {"id": result.get("id")}


def _archive() -> Publisher:
    from .archive import ArchivePublisher

    return ArchivePublisher()


def _kit() -> Publisher:
    from .kit import KitPublisher

    return KitPublisher()


def _telegram() -> Publisher:
    from .telegram import TelegramPublisher

    return TelegramPublisher()


def _webhook() -> Publisher:
    from .webhook import WebhookPublisher

    return WebhookPublisher()


FACTORIES: Dict[str, Callable[[], Publisher]] = {
    "archive": _archive,
    "buttondown": _ButtondownAdapter,
    "kit": _kit,
    "telegram": _telegram,
    "webhook": _webhook,
}


def selected_names(value: Optional[str] = None, no_publish: bool = False) -> List[str]:
    """
    Publisher names from the argument or LLMDAILY_PUBLISHERS (comma separated).

    With no_publish, only local publishers (the archive) are kept.
    """
    raw = value if value is not None else os.environ.get("LLMDAILY_PUBLISHERS", DEFAULT_PUBLISHERS)
    names = [n.strip().lower() for n in raw.split(",") if n.strip()]
    unknown = [n for n in names if n not in FACTORIES]
    if unknown:
        raise ValueError(f"Unknown publisher(s): {', '.join(unknown)}. Choose from: {', '.join(FACTORIES)}")
    if no_publish:
        names = [n for n in names if n in LOCAL_PUBLISHERS]
    return list(dict.fromkeys(names))


def publish_all(issue: Issue, names: List[str],
                overrides: Optional[Dict[str, Publisher]] = None) -> Dict[str, Dict[str, Any]]:
    """
    Run each publisher; one failing does not stop the others.

    Returns {name: {"ok": bool, ...result or "error"}}.
    """
    results: Dict[str, Dict[str, Any]] = {}
    for name in names:
        try:
            publisher = (overrides or {}).get(name) or FACTORIES[name]()
            result = publisher.publish(issue)
            results[name] = {"ok": True, **(result or {})}
            logger.info(f"Published with {name}: {result}")
        except Exception as e:
            results[name] = {"ok": False, "error": str(e)}
            logger.error(f"Publisher {name} failed: {e}")
    return results
