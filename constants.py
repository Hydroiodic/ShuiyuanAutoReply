# Some URLs used in the application
base_url = "https://shuiyuan.sjtu.edu.cn"
get_cookies_url = f"{base_url}/auth/jaccount"
reply_url = f"{base_url}/posts"
get_topic_url = f"{base_url}/t"
upload_url = f"{base_url}/uploads.json"

# We should use a suitable User-Agent for the requests
default_user_agent = (
    "Mozilla/5.0 (Linux; Android 15; K) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/114.0.0.0 Mobile Safari/537.36"
)
