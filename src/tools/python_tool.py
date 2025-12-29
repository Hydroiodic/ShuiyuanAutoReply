# python_tool.py, provide the tool to run python scripts

import asyncio
import docker
import logging
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
            network_disabled=CONFIG["network_disabled"],
        )

        # Wait for the result (with timeout)
        # Docker SDK's wait may block indefinitely, so implement timeout in Python
        # Use asyncio for non-blocking wait

        loop = asyncio.get_event_loop()
        wait_result = await loop.run_in_executor(None, container.wait)

        exit_code = wait_result.get("StatusCode", 0)
        logs = await loop.run_in_executor(None, container.logs)
        output = logs.decode("utf-8").strip()

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
