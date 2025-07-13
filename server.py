from mcp_config import mcp
import uvicorn

# Import the tools to register them with MCP
import controllers.git as git
import controllers.selenium as selenium
import controllers.aws as aws
import controllers.grid as grid

# Optional: add a wrapper tool to chain clone + test
@mcp.tool()
def clone_and_test(repo_url: str, run_on_aws: bool = False, ami_id: str = "", key_name: str = "your-key") -> str:

    """
    Runs tests locally or on AWS depending on the flag.
    
    Args:
        repo_url (str): GitHub repo URL
        run_on_aws (bool): If True, launches EC2 and runs test remotely
    
    Returns:
        str: Test result or instance details
    """
    if not run_on_aws:
        repo_path = git.clone_repo(repo_url)
        if "❌" in repo_path:
            return repo_path
        return selenium.run_selenium_tests(repo_path)
    
    
    result = aws.launch_ec2_with_ami(
        ami_id=ami_id,
        key_name=key_name,
        repo_url=repo_url,  # still needed for later
        security_group_ids=["sg-0abad17ad83da200b"]
    )

    if "error" in result:
        return result["error"]

    instance_id = result["instance_id"]

    # NEW: run test via SSM
    test_output = aws.run_selenium_test_on_aws(instance_id=instance_id, repo_url=repo_url)

    return f"✅ EC2 Test Run Complete on {instance_id}:\n{test_output}"

# @mcp.prompt
# def prompt_run_tests(repo_url: str, run_on_aws: bool = False) -> str:
#     if run_on_aws:
#         return f"Please launch an EC2 instance and run the tests from {repo_url}."
#     else:
#         return f"Please run the tests from {repo_url} locally."

# Run the server
# if __name__ == "__main__":
#     import uvicorn 
#     uvicorn.run("mcp_config:mcp.app", host="127.0.0.1", port=7890, reload=True)
# #    mcp.run()

if __name__ == "__main__":
    mcp.run(transport="http", port=8000)