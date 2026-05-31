# command_tool.py, provide the tool to run command in a container

import asyncio
import logging

import docker

from ..instance import mcp

logger = logging.getLogger(__name__)

# Initialize Docker client
try:
    docker_client = docker.from_env()
except Exception as e:
    logger.error(f"Error connecting to Docker: {e}")
    logger.error("If Docker is not available, please disable it in the config file.")
    exit(1)


@mcp.tool()
async def execute_python_script(code: str) -> str:
    """
    Executes the given Python code in a secure Docker container.
    Also, this function could be used to calculate expressions,
    but the result has to be printed in the code.
    Please note that the user could not see the results of this tool directly,
    so the caller should surface it in the final answer.

    NOTE: In the container, you are `nobody` user, and the current working directory is `/tmp`.
        Network access is disabled, and the resources are limited to 128M to prevent abuse.
        Each time this tool is called, it will start a new container, so the state will not be preserved across calls.
        Thus, you should not expect to read/write files across different calls of this tool, and the code should be self-contained.
        Also, any create/delete operations are safe to be executed.

    Some usage examples:
    - To calculate a simple expression:
        `print(1 + 2 * 3)`
    - To read a file named "data.txt" in the current working directory:
        ```
        with open("data.txt", "r") as f:
            print(f.read())
        ```
    - To calculate the factorial of 5:
        ```
        def factorial(n):
            if n == 0:
                return 1
            else:
                return n * factorial(n - 1)
        print(factorial(5))
        ```
    - To check if a string matches a pattern using regex:
        ```
        import re
        pattern = r'^[a-zA-Z0-9_]+$'
        test_string = 'valid_string123'
        print(bool(re.match(pattern, test_string)))
        ```

    Args:
        code: Python script as a string.

    Returns:
        Standard output (stdout) or error message from the script execution.
    """

    # Security configurations for the Docker container
    CONFIG = {
        "image": "python:3.12-slim",
        "mem_limit": "128m",  # Limit memory to 128MB to prevent OOM attacks
        "memswap_limit": "128m",  # Limit swap to 128MB
        "cpu_quota": 50000,  # Limit CPU to 50% of a single core
        "network_disabled": True,  # Disable network access
        "user": "nobody",  # Avoid running as root (requires image support, nobody is usually available in base images)
        "working_dir": "/tmp",
        "timeout": 10,  # Execution timeout (seconds)
    }

    container = None
    try:
        # 1. Start the container and run the code
        container = docker_client.containers.run(
            image=CONFIG["image"],
            command=["python", "-c", code],
            detach=True,
            mem_limit=CONFIG["mem_limit"],
            memswap_limit=CONFIG["memswap_limit"],
            cpu_quota=CONFIG["cpu_quota"],
            network_disabled=CONFIG["network_disabled"],
        )

        # Wait for the result (with timeout)
        # Docker SDK's wait may block indefinitely, so implement timeout in Python
        # Use asyncio for non-blocking wait

        loop = asyncio.get_event_loop()
        wait_result = await loop.run_in_executor(None, container.wait)

        exit_code = wait_result.get("StatusCode", 0)
        logs = await loop.run_in_executor(None, container.logs)
        output = logs.decode("utf-8").strip()[:512]

        if exit_code != 0:
            return f"Execution Failed (Exit Code {exit_code}):\n{output}"

        return output

    except docker.errors.ContainerError as e:
        return f"Container Error: {str(e)}"
    except docker.errors.ImageNotFound:
        return "Error: Python runtime image not found. Please run 'docker pull python:3.12-slim'"
    except Exception as e:
        return f"System Error: {str(e)}"
    finally:
        # Ensure container is removed
        if container:
            try:
                container.remove(force=True)
            except:
                pass


@mcp.tool()
async def execute_bash_command(command: str) -> str:
    """
    Executes the given Bash command inside a constrained Docker container.
    The output is captured from stdout/stderr.
    Note that the caller should surface it in the final answer.

    NOTE: In the container, you are `nobody` user, and the current working directory is `/tmp`.
        Network access is disabled, and the resources are limited to 128M to prevent abuse.
        Each time this tool is called, it will start a new container, so the state will not be preserved across calls.
        Thus, you should not expect to read/write files across different calls of this tool, and the code should be self-contained.
        Also, any create/delete operations are safe to be executed.

    Some usage examples:
    - To get the current time (we are in Shanghai timezone):
        `date +"%Y-%m-%d %H:%M:%S" -d "TZ=\"Asia/Shanghai\" now"`
    - To list files in the current directory:
        `ls -la`
    - To check disk usage:
        `df -h`
    - To list all running processes:
        `ps aux`
    - To remove a directory named "temp" in the current working directory:
        `rm -rf temp`

    Args:
        command: Bash command to run.

    Returns:
        Standard output (stdout) or error message from the execution.
    """

    CONFIG = {
        "image": "ubuntu:latest",
        "mem_limit": "128m",
        "memswap_limit": "128m",
        "cpu_quota": 50000,
        "network_disabled": True,
        "user": "nobody",
        "working_dir": "/tmp",
        "timeout": 10,
    }

    container = None
    try:
        container = docker_client.containers.run(
            image=CONFIG["image"],
            command=["bash", "-lc", command],
            detach=True,
            mem_limit=CONFIG["mem_limit"],
            memswap_limit=CONFIG["memswap_limit"],
            cpu_quota=CONFIG["cpu_quota"],
            network_disabled=CONFIG["network_disabled"],
        )

        loop = asyncio.get_event_loop()
        wait_future = loop.run_in_executor(None, container.wait)

        try:
            wait_result = await asyncio.wait_for(wait_future, timeout=CONFIG["timeout"])
        except asyncio.TimeoutError:
            await loop.run_in_executor(None, container.kill)
            logs = await loop.run_in_executor(None, container.logs)
            output = logs.decode("utf-8").strip()
            return f"Execution timed out after {CONFIG['timeout']}s:\n{output}"

        exit_code = wait_result.get("StatusCode", 0)
        logs = await loop.run_in_executor(None, container.logs)
        output = logs.decode("utf-8").strip()[:512]

        if exit_code != 0:
            return f"Execution Failed (Exit Code {exit_code}):\n{output}"

        return output

    except docker.errors.ContainerError as e:
        return f"Container Error: {str(e)}"
    except docker.errors.ImageNotFound:
        return "Error: Bash runtime image not found. Please run 'docker pull ubuntu:latest'"
    except Exception as e:
        return f"System Error: {str(e)}"
    finally:
        if container:
            try:
                container.remove(force=True)
            except:
                pass
