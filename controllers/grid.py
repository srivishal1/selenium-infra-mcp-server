from mcp_config import mcp
import subprocess
import platform


@mcp.tool()
def setup_selenium_with_docker(
    num_nodes: int = 1,
    selenium_version: str = "4.21.0"
) -> str:
    """
    Sets up a Selenium 4 Grid using Docker.
    
    Args:
        num_nodes (int): Number of Chrome nodes to start
        selenium_version (str): Version of Selenium Docker image

    Returns:
        str: Setup status message
    """
    try:
        use_amd64 = is_apple_silicon()
        # Step 1: Pull Docker images
        pull_docker_image("selenium/hub", selenium_version, force_amd64=use_amd64)
        pull_docker_image("selenium/node-chrome", selenium_version, force_amd64=use_amd64)

        # Step 2: Start Hub
        subprocess.run([
            "docker", "run", "-d",
            "--name", "selenium-hub",
            "-p", "4442:4442", "-p", "4443:4443", "-p", "4444:4444",
            f"selenium/hub:{selenium_version}"
        ], check=True)

        # Step 3: Start Chrome Nodes
        for i in range(num_nodes):
            subprocess.run([
                "docker", "run", "-d",
                "--name", f"chrome-node-{i+1}",
                "--link", "selenium-hub",
                "-e", "SE_EVENT_BUS_HOST=selenium-hub",
                "-e", "SE_EVENT_BUS_PUBLISH_PORT=4442",
                "-e", "SE_EVENT_BUS_SUBSCRIBE_PORT=4443",
                f"selenium/node-chrome:{selenium_version}"
            ], check=True)

        return (
            f"  Selenium Grid {selenium_version} launched.\n"
            f"   Hub: http://localhost:4444\n"
            f" Nodes: {num_nodes} Chrome nodes running"
        )

    except subprocess.CalledProcessError as e:
        return f" Docker command failed: {e}"
    except Exception as ex:
        return f" Unexpected error: {str(ex)}"
    

@mcp.tool()
def terminate_selenium_grid(num_nodes: int = 1) -> str:
    """
    Stops and removes the Selenium Grid hub and node containers.

    Args:
        num_nodes (int): Number of nodes to stop (default: 1)

    Returns:
        str: Termination summary
    """
    try:
        log = []

        # Stop and remove Chrome nodes
        for i in range(num_nodes):
            name = f"chrome-node-{i+1}"
            subprocess.run(["docker", "rm", "-f", name], check=False)
            log.append(f"🗑️ Removed container: {name}")

        # Stop and remove the hub
        subprocess.run(["docker", "rm", "-f", "selenium-hub"], check=False)
        log.append("🗑️ Removed container: selenium-hub")

        return " Selenium Grid terminated:\n" + "\n".join(log)

    except Exception as e:
        return f"Failed to terminate grid: {str(e)}"
    
def is_apple_silicon() -> bool:
        # On Apple M1/M2, machine is 'arm64' and system is 'Darwin'
    return platform.system() == "Darwin" and platform.machine() == "arm64"

def pull_docker_image(image: str, tag: str, force_amd64: bool = False):
    full_image = f"{image}:{tag}"
    base_cmd = ["docker", "pull"]
    if force_amd64:
        base_cmd += ["--platform=linux/amd64"]
    base_cmd += [full_image]
    subprocess.run(base_cmd, check=True)
    