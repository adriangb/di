from __future__ import annotations

from typing import Any, Callable

from textual.app import App as TextualApp  # type: ignore
from textual.events import Event  # type: ignore
from textual.message import Message  # type: ignore
from textual.message_pump import log  # type: ignore

from di import Container
from di.dependant import Dependant


class App(TextualApp):
    def __init__(self, container: Container | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.container = container or Container()

    async def process_messages(self) -> None:
        async with self.container.enter_scope("app"):
            return await super().process_messages()

    async def on_event(self, event: Event) -> None:
        for method in self._get_dispatch_methods(f"on_{event.name}", event):  # type: ignore
            log(event, ">>>", self, verbosity=event.verbosity)
            await self.invoke(method, event=event)  # type: ignore

    async def invoke(
        self,
        callback: Callable[..., Any],
        *,
        event: Event | None = None,
        message: Message | None = None,
    ) -> None:
        with self.container.bind(Dependant(lambda: event), type(event)):
            with self.container.bind(Dependant(lambda: message), type(message)):
                await self.container.execute_async(
                    self.container.solve(Dependant(callback))
                )
