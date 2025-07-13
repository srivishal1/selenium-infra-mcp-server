from mcp_config import mcp
import subprocess, os, uuid
import platform

@mcp.tool()
def run_selenium_tests(repo_path: str) -> str:
    """
    Runs Selenium tests from the specified repository.
    
    Args:
        repo_path (str): The path where the repo was cloned.
    
    Returns:
        str: Output of the test command or error message.
    """
    try:
        if not os.path.isdir(repo_path):
            return f" Invalid repo path: {repo_path}"

        # Go to the repo directory
        os.chdir(repo_path)

        # Optional: DEBUG mvn path
        mvn_path = subprocess.run(["which", "mvn"], capture_output=True, text=True).stdout.strip()

        # Step 2: Try common fallback locations
        fallback_paths = ["/usr/local/bin/mvn", "/opt/homebrew/bin/mvn", "/usr/bin/mvn"]
        if not mvn_path:
            for path in fallback_paths:
                if os.path.exists(path):
                    mvn_path = path
                    break

        # Step 3: Try install if still not found
        if not mvn_path:
            system = platform.system()
            if system == "Linux":
                print("[DEBUG] Installing Maven via apt")
                install_cmd = "sudo apt-get update && sudo apt-get install -y maven"
            elif system == "Darwin":  # macOS
                print("[DEBUG] Installing Maven via brew")
                install_cmd = "/opt/homebrew/bin/brew install maven || brew install maven"
            else:
                return f" Unsupported OS: {system}"

            install = subprocess.run(
                install_cmd,
                shell=True,
                capture_output=True,
                text=True
            )

            if install.returncode != 0:
                return f" Maven installation failed:\n{install.stderr}"

            # Retry which after install
            mvn_path = subprocess.run(["which", "mvn"], capture_output=True, text=True).stdout.strip()

        if not mvn_path:
            return " 'mvn' not found after attempted installation."

        # Determine the type of project
        if os.path.exists("testng.xml"):
            test_cmd = [mvn_path, "test", "-DsuiteXmlFile=testng.xml"]
        elif os.path.exists("pom.xml"):
            test_cmd = [mvn_path, "test"]   
        elif os.path.exists("build.gradle"):
            test_cmd = ["./gradlew", "test"]
        elif os.path.exists("package.json"):
            test_cmd = ["npm", "test"]
        elif os.path.exists("requirements.txt"):
            test_cmd = ["python", "-m", "pytest"]
        else:
            return " No recognizable test config found (pom.xml, package.json, etc.)"

        # Run the test command
        result = subprocess.run(
            test_cmd,
            capture_output=True,
            text=True,
            timeout=180
        )

        if result.returncode != 0:
            return f" Test run failed:\n{result.stderr}"

        return f" Test run succeeded:\n{result.stdout}"

    except Exception as e:
        return f" Error running tests: {str(e)}"
    