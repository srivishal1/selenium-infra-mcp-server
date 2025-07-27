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
        print(f"📦 Cloning {repo_url} locally...")
        repo_path = git.clone_repo_fn(repo_url)
        if "❌" in repo_path:
            return repo_path
        return selenium.run_tests(repo_path)
    
    print(f"🔧 Launching EC2 instance with AMI: {ami_id} and key: {key_name}...")
    result = aws.launch_ec2_with_ami(
        ami_id=ami_id,
        key_name=key_name,
        instance_type = "t3.micro",
        max_count   = 1,
        region_name = "us-east-1",
        security_group_ids=["sg-0abad17ad83da200b"]
    )

    if "error" in result:
        return result["error"]

    instance_id = result["instance_id"]
    print(f"✅ EC2 instance launched: {instance_id}")

    if aws.wait_for_ssm_ready(instance_id=instance_id):
        print("✅ SSM is ready.")
        test_output = aws.run_selenium_test_on_aws(instance_id=instance_id, repo_url=repo_url)
        aws.terminate_ec2_instance(instance_id=instance_id)
        return f"✅ EC2 Test Run Complete on {instance_id}:\n{test_output}"
    else:
        aws.terminate_ec2_instance(instance_id=instance_id)
        return f"❌ Timeout: SSM agent not ready on EC2 instance {instance_id}"

@mcp.prompt
def prompt_run_tests(repo_url: str, run_on_aws: bool = False, ami_id: str = "", key_name: str = "your-key") -> str:
    """
    Prompt to instruct when to call clone_and_test tool.
    """
    if run_on_aws:
        return (
            f"Launch an EC2 instance using AMI ID {ami_id} and key {key_name}, "
            f"then clone the repository {repo_url} and run the tests using SSM."
        )
    else:
        return f"Clone the repository {repo_url} locally and run the tests."

# Run the server
# if __name__ == "__main__":
#     import uvicorn 
#     uvicorn.run("mcp_config:mcp.app", host="127.0.0.1", port=7890, reload=True)
# #    mcp.run()

if __name__ == "__main__":
    #mcp.run(transport="streamable-http")
     mcp.run()