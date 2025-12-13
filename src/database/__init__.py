import os

if not os.getenv("MYSQL_DB_URL"):
    raise ValueError("Please set the MYSQL_DB_URL environment variable.")

if not os.getenv("NEO4J_DB_URL"):
    raise ValueError("Please set the NEO4J_DB_URL environment variable.")
