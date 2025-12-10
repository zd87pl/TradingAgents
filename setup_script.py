import typer
import questionary
import subprocess
import os
from rich.console import Console
from rich.panel import Panel

console = Console()

def check_docker():
    """Check if Docker is installed and running."""
    try:
        subprocess.run(["docker", "info"], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

def setup_api_keys():
    """Prompt the user for API keys and save them to a .env file."""
    console.print(Panel("API Key Configuration", title="[bold blue]Step 1[/bold blue]", expand=False))
    
    openai_api_key = questionary.password("Enter your OpenAI API key:").ask()
    alpha_vantage_api_key = questionary.password("Enter your Alpha Vantage API key:").ask()
    
    with open(".env", "w") as f:
        f.write(f"OPENAI_API_KEY={openai_api_key}\n")
        f.write(f"ALPHA_VANTAGE_API_KEY={alpha_vantage_api_key}\n")
        f.write(f"LLM_PROVIDER=openai\n")
        
    console.print("[green]Successfully saved API keys to .env file.[/green]")

def build_docker_image():
    """Build the Docker image."""
    console.print(Panel("Building Docker Image", title="[bold blue]Step 2[/bold blue]", expand=False))
    try:
        subprocess.run(["docker-compose", "build"], check=True)
        console.print("[green]Docker image built successfully.[/green]")
        return True
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Error building Docker image: {e}[/red]")
        return False

def run_docker_container():
    """Run the Docker container."""
    console.print(Panel("Running Docker Container", title="[bold blue]Step 3[/bold blue]", expand=False))
    try:
        subprocess.run(["docker-compose", "up", "-d"], check=True)
        console.print("[green]Docker container started successfully.[/green]")
        return True
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Error running Docker container: {e}[/red]")
        return False

def local_setup_instructions():
    """Provide instructions for local setup."""
    console.print(Panel("Local Setup Instructions", title="[bold blue]Alternative[/bold blue]", expand=False))
    console.print("To set up the project locally, please follow these steps:")
    console.print("1. Install Python 3.10 or higher.")
    console.print("2. Create a virtual environment: `python -m venv venv`")
    console.print("3. Activate the virtual environment: `source venv/bin/activate` (on Linux/macOS) or `venv\\Scripts\\activate` (on Windows)")
    console.print("4. Install the required dependencies: `pip install -r requirements.txt`")
    console.print("5. Run the application: `python -m cli.main analyze`")

def main():
    """Main function to run the setup script."""
    console.print(Panel("Welcome to the TradingAgents Setup Script!", title="[bold green]TradingAgents[/bold green]", expand=False))
    
    setup_choice = questionary.select(
        "Choose your setup method:",
        choices=["Docker (recommended)", "Local Setup"]
    ).ask()

    if setup_choice == "Docker (recommended)":
        if not check_docker():
            console.print("[red]Docker is not installed or not running. Please install and start Docker to proceed.[/red]")
            return

        setup_api_keys()
        
        if build_docker_image():
            run_choice = questionary.confirm("Do you want to run the Docker container now?").ask()
            if run_choice:
                if run_docker_container():
                    console.print("\n[bold green]Setup complete![/bold green]")
                    console.print("You can now interact with the TradingAgents CLI by running:")
                    console.print("`docker-compose exec tradingagents python -m cli.main analyze`")
                else:
                    console.print("\n[bold red]Setup failed.[/bold red]")
            else:
                console.print("\n[bold yellow]Setup partially complete.[/bold yellow]")
                console.print("You can run the container later with `docker-compose up -d`.")
        else:
            console.print("\n[bold red]Setup failed.[/bold red]")

    elif setup_choice == "Local Setup":
        setup_api_keys()
        local_setup_instructions()
        console.print("\n[bold green]Setup complete![/bold green]")
        console.print("You can now run the application with:")
        console.print("`python -m cli.main analyze`")

