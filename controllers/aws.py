from mcp_config import mcp
from datetime import datetime, timedelta
import boto3
import time

@mcp.tool()
def launch_ec2_with_ami(
    ami_id: str,
    key_name: str,
    instance_type: str = "t3.micro",
    max_count: int = 1,
    region_name: str = "us-east-1",
    security_group_ids: list[str] = None
) -> dict:
    """
    Launches an EC2 instance with SSM-enabled IAM role.
    """
    try:
        ec2 = boto3.client("ec2", region_name=region_name)

        response = ec2.run_instances(
            ImageId=ami_id,
            InstanceType=instance_type,
            MinCount=1,
            MaxCount=max_count,
            KeyName=key_name,
            SecurityGroupIds=security_group_ids or [],
            IamInstanceProfile={"Name": "MCP-EC2-SSM-Role"},
            TagSpecifications=[{
                "ResourceType": "instance",
                "Tags": [{"Key": "Name", "Value": "MCP-Test-Runner"}]
            }]
        )

        instance = response["Instances"][0]
        instance_id = instance["InstanceId"]

        ec2_resource = boto3.resource("ec2", region_name=region_name)
        ec2_instance = ec2_resource.Instance(instance_id)
        ec2_instance.wait_until_running()
        ec2_instance.reload()

        return {
            "instance_id": instance_id,
            "public_ip": ec2_instance.public_ip_address
        }

    except Exception as e:
        return {"error": str(e)}

@mcp.tool()
def run_selenium_test_on_aws(instance_id: str, repo_url: str) -> str:
   
    """
    Run Selenium Test on Aws EC2 Instance.

    Args:
        instance_id : The ID of the EC2 instance to run the tests on.
        repo_url : The URL of the GitHub repository containing the tests.

    Returns:
        str: Status message or test result.

    """
    
    ec2 = boto3.client("ec2", region_name="us-east-1")
    ssm = boto3.client("ssm", region_name="us-east-1")

    instance_desc = ec2.describe_instances(InstanceIds=[instance_id])
    platform = instance_desc["Reservations"][0]["Instances"][0].get("Platform", "Linux")
    is_windows = platform.lower() == "windows"

    document = "AWS-RunPowerShellScript" if is_windows else "AWS-RunShellScript"

    if is_windows:
        command = f"""
        $log = "C:\\mcp-log.txt"
        "=== MCP Windows Test Run ===" | Out-File -FilePath $log

        try {{
            "Using preinstalled Git at C:\\Program Files\\Git\\bin\\git.exe" | Out-File -Append $log
            $gitPath = "C:\\Program Files\\Git\\bin\\git.exe"

            # Clean old repo if it exists
            if (Test-Path "C:\\repo") {{
                "⚠️ Repo already exists. Deleting..." | Out-File -FilePath $log -Append
                Remove-Item "C:\\repo" -Recurse -Force
            }}

            # Clone fresh
            " Cloning repository..." | Out-File -Append $log
            & "$gitPath" clone {repo_url} C:\\repo 2>&1 | Out-File -Append $log
            Set-Location C:\\repo
            
            $MavenPath = "C:\\apache-maven-3.9.10\\bin\\mvn.cmd"

           if (Test-Path 'testng.xml') {{
                " Running mvn with testng.xml..." | Out-File -Append $log
                 $arguments = @("test", "-DsuiteXmlFile=testng.xml")
                 & "$MavenPath" @arguments | Out-File -Append $log
            }} elseif (Test-Path 'pom.xml') {{
                " Running Maven test..." | Out-File -Append $log
                & "$MavenPath" test | Out-File -Append $log
            }} else {{
                " No test config found. Files:" | Out-File -Append $log
                  Get-ChildItem -Recurse | Out-File -Append $log
            }}

        }} catch {{
            $_ | Out-File -Append $log
        }}
        
        Get-Content $log
        """
    else:
        command = f"""
        mkdir -p /home/ec2-user/repo &&
        cd /home/ec2-user &&
        yum install -y git || apt-get install -y git &&
        git clone {repo_url} repo &&
        cd repo &&
        if [ -f testng.xml ]; then
            mvn test -DsuiteXmlFile=testng.xml
        elif [ -f pom.xml ]; then
            mvn test
        elif [ -f package.json ]; then
            npm install && npm test
        elif [ -f requirements.txt ]; then
            pip install -r requirements.txt && pytest
        else
             echo "No recognizable test config."
        ls -la
        fi
        """

    try:
        send_response = ssm.send_command(
            InstanceIds=[instance_id],
            DocumentName=document,
            Parameters={"commands": [command]},
        )

        command_id = send_response["Command"]["CommandId"]

        for _ in range(60):  # wait up to 5 minutes
            result = ssm.get_command_invocation(
                CommandId=command_id,
                InstanceId=instance_id
            )
            if result["Status"] in ["Success", "Failed", "Cancelled", "TimedOut"]:
                return (
                    f" Test Output:\n{result.get('StandardOutputContent', '')}\n\n"
                    f" Errors:\n{result.get('StandardErrorContent', '')}"
                )
            time.sleep(5)

        return " Test run timed out after SSM execution."

    except Exception as e:
        return f" Failed to run test via SSM: {str(e)}"

@mcp.tool()
def terminate_ec2_instance(instance_id: str, region_name = "us-east-1") -> str:
    """
    Terminates an EC2 instance by ID.
    """
    try:
        ec2 = boto3.client("ec2", region_name=region_name)
        response = ec2.terminate_instances(InstanceIds=[instance_id])
        state = response["TerminatingInstances"][0]["CurrentState"]["Name"]
        return f" Instance {instance_id} is now in state: {state}"
    except Exception as e:
        return f" Failed to terminate instance {instance_id}: {str(e)}"
    
@mcp.tool()
def get_ec2_cost(
    instance_type: str = "t3.micro",
    start_date: str = None,
    end_date: str = None,
    granularity: str = "DAILY",
    output_format: str = "text"  # text or csv
) -> str:
    """
    Retrieves EC2 cost for a specific instance type using AWS Cost Explorer.

    Args:
        instance_type (str): e.g. t3.micro
        start_date (str): Format YYYY-MM-DD. Defaults to 3 days ago.
        end_date (str): Format YYYY-MM-DD. Defaults to today.
        granularity (str): DAILY or MONTHLY
        output_format (str): 'text' (default) or 'csv'

    Returns:
        str: Cost breakdown
    """
    try:
        ce = boto3.client("ce", region_name="us-east-1")

        # Default dates
        if not end_date:
            end_date = datetime.utcnow().date().isoformat()
        if not start_date:
            start_date = (datetime.utcnow() - timedelta(days=3)).date().isoformat()

        response = ce.get_cost_and_usage(
            TimePeriod={
                "Start": start_date,
                "End": end_date
            },
            Granularity=granularity,
            Metrics=["UnblendedCost"],
            Filter={
                "And": [
                    {
                        "Dimensions": {
                            "Key": "SERVICE",
                            "Values": ["Amazon Elastic Compute Cloud - Compute"]
                        }
                    },
                    {
                        "Dimensions": {
                            "Key": "INSTANCE_TYPE",
                            "Values": [instance_type]
                        }
                    }
                ]
            }
        )

        results = response["ResultsByTime"]
        total = 0.0

        if output_format.lower() == "csv":
            lines = ["Date,Cost"]
            for r in results:
                date = r["TimePeriod"]["Start"]
                amount = float(r["Total"]["UnblendedCost"]["Amount"])
                total += amount
                lines.append(f"{date},{amount:.4f}")
            lines.append(f"Total,${total:.4f}")
            return "\n".join(lines)
        else:
            # Default text output
            message = f" EC2 cost for `{instance_type}` from {start_date} to {end_date}:\n\n"
            for r in results:
                date = r["TimePeriod"]["Start"]
                amount = float(r["Total"]["UnblendedCost"]["Amount"])
                total += amount
                message += f"• {date}: ${amount:.4f}\n"
            message += f"\n💰 Total cost: ${total:.4f}"
            return message

    except Exception as e:
        return f" Failed to retrieve EC2 cost: {str(e)}"

def wait_for_ssm_ready(instance_id: str, timeout_seconds: int = 300) -> bool:
    ssm = boto3.client("ssm", region_name="us-east-1")
    deadline = time.time() + timeout_seconds

    print(f"[INFO] Waiting for SSM to be ready for instance {instance_id}...")

    while time.time() < deadline:
        try:
            info = ssm.describe_instance_information()
            instances = [i["InstanceId"] for i in info["InstanceInformationList"]]
            if instance_id in instances:
                print(" SSM is ready.")
                return True
        except Exception as e:
            print(f"[WARN] Waiting for SSM: {str(e)}")

        time.sleep(10)

    print(" Timeout: SSM agent did not register in time.")
    return False