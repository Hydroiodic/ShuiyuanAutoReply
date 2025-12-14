# Some URLs used in the application
base_url = "https://shuiyuan.sjtu.edu.cn"
get_topic_url = f"{base_url}/t"
get_user_url = f"{base_url}/u"
get_cookies_url = f"{base_url}/auth/jaccount"
reply_url = f"{base_url}/posts"
upload_url = f"{base_url}/uploads.json"
action_url = f"{base_url}/user_actions.json"

# We should use a suitable User-Agent for the requests
default_user_agent = (
    "Mozilla/5.0 (Linux; Android 15; K) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/114.0.0.0 Mobile Safari/537.36"
)
