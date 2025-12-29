# Add the parent directory to the system path
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import dotenv
from src.instance import mcp

# Load environment variables from .env file
dotenv.load_dotenv()

# Configure tools based on environment variables
from src import tools

if __name__ == "__main__":
    mcp.run(transport="streamable-http")
