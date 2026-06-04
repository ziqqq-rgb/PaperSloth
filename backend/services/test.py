# Run this once in a Python shell to check your format
from core.database import execute_query
row = execute_query("SELECT image_urls FROM parent_chunks WHERE image_urls != '{}' LIMIT 1", fetch="one")
print(row)