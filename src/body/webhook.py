"""
Webhook Receiver - Webhook 事件接收器

统一接收和处理各种外部 Webhook 事件：
- GitHub Webhooks
- Google Calendar 事件
- 文件变化事件
- 定时触发器
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import logging
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)


class WebhookEvent:
    """Webhook 事件"""

    def __init__(
        self,
        source: str,           # 来源：github, gcal, file, cron
        event_type: str,       # 事件类型
        payload: dict[str, Any], # 事件数据
        headers: dict[str, str] | None = None,
    ):
        self.source = source
        self.event_type = event_type
        self.payload = payload
        self.headers = headers or {}


class WebhookReceiver:
    """
    Webhook 事件接收器

    统一接收和处理各种 Webhook 事件。
    """

    def __init__(self, secret: str = ""):
        self._secret = secret
        self._handlers: dict[str, Callable[[WebhookEvent], Any]] = {}

    def register_handler(self, source: str, event_type: str, handler: Callable[[WebhookEvent], Any]) -> None:
        """
        注册事件处理器。

        Args:
            source: 事件来源（github, gcal, file, cron）
            event_type: 事件类型
            handler: 处理函数
        """
        key = f"{source}:{event_type}"
        self._handlers[key] = handler
        logger.debug(f"注册 Webhook 处理器: {key}")

    def register_source_handler(self, source: str, handler: Callable[[WebhookEvent], Any]) -> None:
        """
        注册源级别的处理器（处理该源的所有事件）。

        Args:
            source: 事件来源
            handler: 处理函数
        """
        self._handlers[source] = handler
        logger.debug(f"注册 Webhook 源处理器: {source}")

    async def handle(self, event: WebhookEvent) -> Any:
        """
        处理 Webhook 事件。

        Args:
            event: Webhook 事件

        Returns:
            处理器返回结果
        """
        # 优先查找精确匹配
        key = f"{event.source}:{event.event_type}"
        if key in self._handlers:
            handler = self._handlers[key]
            result = handler(event)
            if asyncio.iscoroutine(result):
                result = await result
            return result

        # 其次查找源级别处理器
        if event.source in self._handlers:
            handler = self._handlers[event.source]
            result = handler(event)
            if asyncio.iscoroutine(result):
                result = await result
            return result

        logger.debug(f"未找到处理器: {event.source}:{event.event_type}")
        return None

    def verify_signature(self, payload_bytes: bytes, signature: str, algorithm: str = "sha256") -> bool:
        """
        验证 Webhook 签名。

        Args:
            payload_bytes: 请求体
            signature: 签名（通常在 header 中）
            algorithm: 哈希算法

        Returns:
            bool: 签名是否有效
        """
        if not self._secret:
            return True  # 没有配置 secret 时跳过验证

        if algorithm == "sha256":
            expected = "sha256=" + hmac.new(
                self._secret.encode(),
                payload_bytes,
                hashlib.sha256
            ).hexdigest()
        elif algorithm == "sha1":
            expected = "sha1=" + hmac.new(
                self._secret.encode(),
                payload_bytes,
                hashlib.sha1
            ).hexdigest()
        else:
            return False

        return hmac.compare_digest(expected, signature)


# ──────────────────────────────────────────────
# GitHub Webhook 处理器
# ──────────────────────────────────────────────

class GitHubWebhookHandler:
    """
    GitHub Webhook 事件处理器

    支持的事件：
    - push: 代码推送
    - pull_request: PR 事件
    - issues: Issue 事件
    - release: 发布事件
    - workflow_run: CI/CD 工作流
    """

    def __init__(self, receiver: WebhookReceiver):
        self.receiver = receiver
        self._event_handlers: dict[str, Callable] = {}

        # 注册到 receiver
        receiver.register_source_handler("github", self._handle_github_event)

    def register_event_handler(self, event_type: str, handler: Callable[[dict[str, Any]], Any]) -> None:
        """注册特定事件类型的处理器"""
        self._event_handlers[event_type] = handler

    async def _handle_github_event(self, event: WebhookEvent) -> Any:
        """处理 GitHub 事件"""
        event_type = event.event_type
        payload = event.payload

        logger.info(f"GitHub Webhook: {event_type}")

        # 调用注册的处理器
        if event_type in self._event_handlers:
            handler = self._event_handlers[event_type]
            result = handler(payload)
            if asyncio.iscoroutine(result):
                result = await result
            return result

        # 内置处理
        if event_type == "push":
            return await self._handle_push(payload)
        elif event_type == "pull_request":
            return await self._handle_pull_request(payload)
        elif event_type == "issues":
            return await self._handle_issues(payload)
        elif event_type == "release":
            return await self._handle_release(payload)
        elif event_type == "workflow_run":
            return await self._handle_workflow_run(payload)

        return None

    async def _handle_push(self, payload: dict[str, Any]) -> dict[str, Any]:
        """处理代码推送"""
        repository = payload.get("repository", {}).get("full_name", "")
        ref = payload.get("ref", "")
        commits = payload.get("commits", [])
        pusher = payload.get("pusher", {}).get("name", "")

        result = {
            "type": "push",
            "repository": repository,
            "ref": ref,
            "commits_count": len(commits),
            "pusher": pusher,
            "message": f"{pusher} 推送了 {len(commits)} 个提交到 {repository} ({ref})",
        }

        logger.info(result["message"])
        return result

    async def _handle_pull_request(self, payload: dict[str, Any]) -> dict[str, Any]:
        """处理 PR 事件"""
        action = payload.get("action", "")
        pr = payload.get("pull_request", {})
        repository = payload.get("repository", {}).get("full_name", "")
        pr_number = pr.get("number", "")
        title = pr.get("title", "")

        result = {
            "type": "pull_request",
            "action": action,
            "repository": repository,
            "pr_number": pr_number,
            "title": title,
            "message": f"PR #{pr_number} {action}: {title} ({repository})",
        }

        logger.info(result["message"])
        return result

    async def _handle_issues(self, payload: dict[str, Any]) -> dict[str, Any]:
        """处理 Issue 事件"""
        action = payload.get("action", "")
        issue = payload.get("issue", {})
        repository = payload.get("repository", {}).get("full_name", "")
        issue_number = issue.get("number", "")
        title = issue.get("title", "")

        result = {
            "type": "issues",
            "action": action,
            "repository": repository,
            "issue_number": issue_number,
            "title": title,
            "message": f"Issue #{issue_number} {action}: {title} ({repository})",
        }

        logger.info(result["message"])
        return result

    async def _handle_release(self, payload: dict[str, Any]) -> dict[str, Any]:
        """处理发布事件"""
        action = payload.get("action", "")
        release = payload.get("release", {})
        repository = payload.get("repository", {}).get("full_name", "")
        tag = release.get("tag_name", "")
        name = release.get("name", "")

        result = {
            "type": "release",
            "action": action,
            "repository": repository,
            "tag": tag,
            "name": name,
            "message": f"Release {action}: {name or tag} ({repository})",
        }

        logger.info(result["message"])
        return result

    async def _handle_workflow_run(self, payload: dict[str, Any]) -> dict[str, Any]:
        """处理工作流运行事件"""
        action = payload.get("action", "")
        workflow_run = payload.get("workflow_run", {})
        repository = payload.get("repository", {}).get("full_name", "")
        workflow = workflow_run.get("name", "")
        conclusion = workflow_run.get("conclusion", "")
        html_url = workflow_run.get("html_url", "")

        result = {
            "type": "workflow_run",
            "action": action,
            "repository": repository,
            "workflow": workflow,
            "conclusion": conclusion,
            "url": html_url,
            "message": f"Workflow {workflow} {action}: {conclusion} ({repository})",
        }

        logger.info(result["message"])
        return result


# ──────────────────────────────────────────────
# FastAPI 路由集成
# ──────────────────────────────────────────────

def create_webhook_routes(receiver: WebhookReceiver) -> Any:
    """
    创建 Webhook FastAPI 路由。

    Args:
        receiver: WebhookReceiver 实例

    Returns:
        FastAPI Router
    """
    from fastapi import APIRouter, Request, HTTPException, Header
    from typing import Optional

    router = APIRouter(prefix="/webhook")

    @router.post("/github")
    async def github_webhook(
        request: Request,
        x_github_event: str = Header(None, alias="X-GitHub-Event"),
        x_github_delivery: str = Header(None, alias="X-GitHub-Delivery"),
        x_hub_signature_256: Optional[str] = Header(None, alias="X-Hub-Signature-256"),
        x_hub_signature: Optional[str] = Header(None, alias="X-Hub-Signature"),
    ):
        """GitHub Webhook 端点"""
        body = await request.body()

        # 验证签名
        signature = x_hub_signature_256 or x_hub_signature or ""
        if signature and not receiver.verify_signature(body, signature):
            raise HTTPException(status_code=401, detail="Invalid signature")

        payload = await request.json()

        event = WebhookEvent(
            source="github",
            event_type=x_github_event or "unknown",
            payload=payload,
            headers={
                "x-github-event": x_github_event or "",
                "x-github-delivery": x_github_delivery or "",
            },
        )

        result = await receiver.handle(event)
        return {"status": "ok", "result": result}

    @router.post("/gcal")
    async def gcal_webhook(request: Request):
        """Google Calendar Webhook 端点"""
        payload = await request.json()

        event = WebhookEvent(
            source="gcal",
            event_type="calendar_event",
            payload=payload,
        )

        result = await receiver.handle(event)
        return {"status": "ok", "result": result}

    @router.post("/file")
    async def file_webhook(request: Request):
        """文件变化 Webhook 端点"""
        payload = await request.json()

        event = WebhookEvent(
            source="file",
            event_type=payload.get("event_type", "change"),
            payload=payload,
        )

        result = await receiver.handle(event)
        return {"status": "ok", "result": result}

    @router.get("/health")
    async def webhook_health():
        """健康检查"""
        return {"status": "ok"}

    return router
