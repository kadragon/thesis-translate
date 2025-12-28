"""Rich-based interactive prompts for better UX."""

from rich.panel import Panel
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.text import Text

from src.utils.rich_logging import get_console

# Use shared console for consistency with logging and progress bars
console = get_console()


def confirm_clear_file(file_path: str) -> bool:
    """Ask user to confirm clearing a non-empty file.

    Args:
        file_path: Path to the file to be cleared

    Returns:
        True if user confirms, False otherwise
    """
    message = Text()
    message.append("📄 ", style="bold yellow")
    message.append(file_path, style="bold cyan")
    message.append(" 파일이 비어있지 않습니다.", style="yellow")

    console.print(Panel(message, border_style="yellow", expand=False))

    return Confirm.ask(
        "[bold yellow]❓ 파일을 비우시겠습니까?[/bold yellow]",
        default=False,
        console=console,
    )


def ask_start_page() -> int:
    """Ask user for the starting page number.

    Returns:
        The starting page number entered by user
    """
    console.print(
        Panel(
            "[bold cyan]📖 번역 시작 설정[/bold cyan]",
            border_style="cyan",
            expand=False,
        )
    )

    return IntPrompt.ask(
        "[bold cyan]🔢 시작 페이지 번호를 입력하세요[/bold cyan]",
        console=console,
    )


def ask_menu_action() -> str:
    """Ask user for next action in text preprocessing menu.

    Returns:
        User's choice (uppercase): 'A', 'B', 'E', or '' (Enter)
    """
    # Display menu with rich formatting
    menu_text = Text()
    menu_text.append("\n📋 다음 작업을 선택하세요:\n", style="bold cyan")
    menu_text.append("  [", style="dim")
    menu_text.append("A", style="bold green")
    menu_text.append("] 텍스트 추가\n", style="dim")
    menu_text.append("  [", style="dim")
    menu_text.append("Enter", style="bold yellow")
    menu_text.append("] 번역 진행\n", style="dim")
    menu_text.append("  [", style="dim")
    menu_text.append("E", style="bold blue")
    menu_text.append("] 페이지 번호 추가\n", style="dim")
    menu_text.append("  [", style="dim")
    menu_text.append("B", style="bold red")
    menu_text.append("] 종료", style="dim")

    console.print(menu_text)

    choice = Prompt.ask(
        "[bold cyan]👉 선택[/bold cyan]",
        choices=["A", "B", "E", ""],
        default="",
        show_choices=False,
        show_default=False,
        console=console,
    )

    return choice.upper()
