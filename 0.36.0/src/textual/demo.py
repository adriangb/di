from dataclasses import dataclass

from httpx import AsyncClient
from rich.markdown import Markdown
from textual.widgets import Footer, Header, ScrollView  # type: ignore

from di import Depends
from docs.src.textual.src import App  # type: ignore


@dataclass
class Config:
    url: str = "https://raw.githubusercontent.com/willmcgugan/textual/main/examples/richreadme.md"


async def get_readme(
    config: Config, client: AsyncClient = Depends(scope="app", wire=False)
) -> Markdown:
    # URL could be loaded from config
    response = await client.get(config.url)
    response.raise_for_status()
    return Markdown(response.text, hyperlinks=True)


class GridTest(App):
    async def on_load(self) -> None:
        """Bind keys with the app loads (but before entering application mode)"""
        await self.bind("b", "view.toggle('sidebar')", "Toggle sidebar")
        await self.bind("q", "quit", "Quit")

    async def on_mount(self, readme: Markdown = Depends(get_readme)) -> None:
        """Create and dock the widgets."""

        # A scrollview to contain the markdown file
        body = ScrollView(gutter=1)

        # Header / footer / dock
        await self.view.dock(Header(), edge="top")
        await self.view.dock(Footer(), edge="bottom")

        # Dock the body in the remaining space
        await self.view.dock(body, edge="right")

        await self.call_later(body.update, readme)  # type: ignore


def main() -> None:
    GridTest.run(title="Grid Test", log="textual.log")  # type: ignore
