from mcp_config import mcp
import subprocess, os, uuid

@mcp.tool()
def clone_repo(repo_url: str) -> str:
    return clone_repo_fn(repo_url=repo_url)

def clone_repo_fn(repo_url: str) -> str:
    """
    Clones a GitHub repository to a temporary folder.
    
    Args:
        repo_url (str): The GitHub repository URL.
    
    Returns:
        str: Path to the cloned repo or error message starting with ❌.
    """
    try:
        if not repo_url.startswith("https://github.com/"):
            return "❌ Only GitHub HTTPS URLs are supported."

        # Create a unique directory to avoid collisions
        folder_name = f"repo_{uuid.uuid4().hex[:8]}"
        output_dir = os.path.join("/tmp", folder_name)

        # Run git clone
        result = subprocess.run(
            ["git", "clone", repo_url, output_dir],
            capture_output=True,
            text=True,
            timeout=60
        )

        if result.returncode != 0:
            return f"❌ Git clone failed: {result.stderr.strip()}"
        
        print(f"📦 Repo Cloned at {output_dir}.")

        return output_dir  # ✅ return actual path
    
    except Exception as e:
        return f"❌ Error: {str(e)}"
    

    