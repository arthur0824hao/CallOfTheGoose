"""
存儲 YouTube cookies 配置

使用方法:
1. 登入 YouTube
2. 使用 Cookie-Editor 擴展導出 cookies (JSON 格式)
3. 將 JSON 粘貼到 YOUTUBE_COOKIES_JSON 變量中
"""

import os
import json
import tempfile
from pathlib import Path

# 將從 Cookie-Editor 導出的 JSON 粘貼在這裡
YOUTUBE_COOKIES_JSON = """
[
    {
        "domain": ".youtube.com",
        "expirationDate": 1774207801.898528,
        "hostOnly": false,
        "httpOnly": true,
        "name": "__Secure-3PSID",
        "path": "/",
        "sameSite": "no_restriction",
        "secure": true,
        "session": false,
        "storeId": null,
        "value": "g.a000tAgMeyPY0dGRhnehc69g5ItvAgJlv_Aew4JMn8p2A26qLGWKNq3nzwXCs9HjVOIuRB1v5gACgYKAcISARcSFQHGX2MieEKzs6_Z2BHxYI1Qsc3AEhoVAUF8yKpSr9J7y6TFb_RHvRATmyCa0076"
    },
    {
        "domain": ".youtube.com",
        "expirationDate": 1772337213.350765,
        "hostOnly": false,
        "httpOnly": true,
        "name": "__Secure-1PSIDTS",
        "path": "/",
        "sameSite": null,
        "secure": true,
        "session": false,
        "storeId": null,
        "value": "sidts-CjEBEJ3XV0Nh1U_ZCMPN2u6sMWFCY2s27oiyLWYp3MfPk9_BTyirDSUEm_QNLDHxCp3zEAA"
    },
    {
        "domain": ".youtube.com",
        "expirationDate": 1772849558.534639,
        "hostOnly": false,
        "httpOnly": false,
        "name": "SAPISID",
        "path": "/",
        "sameSite": null,
        "secure": true,
        "session": false,
        "storeId": null,
        "value": "1d4Kl3Ga2h6McEKS/AZa_iyN3CNB7BvVF0"
    },
    {
        "domain": ".youtube.com",
        "expirationDate": 1772337619.498369,
        "hostOnly": false,
        "httpOnly": true,
        "name": "__Secure-1PSIDCC",
        "path": "/",
        "sameSite": null,
        "secure": true,
        "session": false,
        "storeId": null,
        "value": "AKEyXzVS-EP89yQoPkEojMh9BKyjUcUoUDYfqEnulJcE4qx9cRMmnf0vvkv3l4FsX_-zMkl8xfe_"
    },
    {
        "domain": ".youtube.com",
        "expirationDate": 1772849558.534626,
        "hostOnly": false,
        "httpOnly": true,
        "name": "SSID",
        "path": "/",
        "sameSite": null,
        "secure": true,
        "session": false,
        "storeId": null,
        "value": "AgTbhirXvHyVghsu-"
    },
    {
        "domain": ".youtube.com",
        "expirationDate": 1772849558.534652,
        "hostOnly": false,
        "httpOnly": false,
        "name": "__Secure-1PAPISID",
        "path": "/",
        "sameSite": null,
        "secure": true,
        "session": false,
        "storeId": null,
        "value": "1d4Kl3Ga2h6McEKS/AZa_iyN3CNB7BvVF0"
    },
    {
        "domain": ".youtube.com",
        "expirationDate": 1772849558.534764,
        "hostOnly": false,
        "httpOnly": true,
        "name": "__Secure-1PSID",
        "path": "/",
        "sameSite": null,
        "secure": true,
        "session": false,
        "storeId": null,
        "value": "g.a000tAgMeyPY0dGRhnehc69g5ItvAgJlv_Aew4JMn8p2A26qLGWKB0RGhlGfKcjhccRwN5MA5wACgYKAaMSARcSFQHGX2MiVPs1B9wrbJqhkKlC6uchlRoVAUF8yKpme75cB3TUWTr0HrEySaf30076"
    },
    {
        "domain": ".youtube.com",
        "expirationDate": 1774207801.898414,
        "hostOnly": false,
        "httpOnly": false,
        "name": "__Secure-3PAPISID",
        "path": "/",
        "sameSite": "no_restriction",
        "secure": true,
        "session": false,
        "storeId": null,
        "value": "1d4Kl3Ga2h6McEKS/AZa_iyN3CNB7BvVF0"
    },
    {
        "domain": ".youtube.com",
        "expirationDate": 1772337619.498387,
        "hostOnly": false,
        "httpOnly": true,
        "name": "__Secure-3PSIDCC",
        "path": "/",
        "sameSite": "no_restriction",
        "secure": true,
        "session": false,
        "storeId": null,
        "value": "AKEyXzXGFrZXZtZ3HwHkkr_vQhDUsRZR6LUKGcKEEI6L9amr97jR6txrDG7GaCrmxMXx0v_nxso"
    },
    {
        "domain": ".youtube.com",
        "expirationDate": 1772337213.350864,
        "hostOnly": false,
        "httpOnly": true,
        "name": "__Secure-3PSIDTS",
        "path": "/",
        "sameSite": "no_restriction",
        "secure": true,
        "session": false,
        "storeId": null,
        "value": "sidts-CjEBEJ3XV0Nh1U_ZCMPN2u6sMWFCY2s27oiyLWYp3MfPk9_BTyirDSUEm_QNLDHxCp3zEAA"
    },
    {
        "domain": ".youtube.com",
        "expirationDate": 1757348214.365618,
        "hostOnly": false,
        "httpOnly": true,
        "name": "LOGIN_INFO",
        "path": "/",
        "sameSite": "no_restriction",
        "secure": true,
        "session": false,
        "storeId": null,
        "value": "AFmmF2swRgIhANvSRzG_LOB7vMAjCX1TCxdj2gXlnJ784wlgQGTm_heHAiEA9Xeq8ND2IQEHEhpywF3BSopR5nB9dACI9Eulsh0gqVQ:QUQ3MjNmd2FLOU9KbXN5NEVMX2xtc1FqUkpnaXBOeHlibl8yekM3aWNoZmI0RG5xYXA2dzZfM3NqbDhsbVUtYlJjUnhwam9iaTlYLTZ0S2dLUjhTME5uRkhNTG01aFVxRGQwSHh0ZHdKTXdpbjBneWJ5UEltZU5vaDdSekZ1czRIYWJ2aFdlYTVrUW15Ul9XbFhfcFJQNHE0aElCQmJjN3F3"
    },
    {
        "domain": ".youtube.com",
        "expirationDate": 1775361618.227693,
        "hostOnly": false,
        "httpOnly": false,
        "name": "PREF",
        "path": "/",
        "sameSite": null,
        "secure": true,
        "session": false,
        "storeId": null,
        "value": "f6=40000000&tz=Asia.Taipei&f5=30000&f7=100"
    }
]
"""

def get_cookies_path():
    """創建臨時 cookies 文件並返回路徑"""
    cookies_data = []
    
    try:
        if YOUTUBE_COOKIES_JSON.strip():
            cookies_data = json.loads(YOUTUBE_COOKIES_JSON)
    except json.JSONDecodeError:
        print("警告: cookies JSON 格式錯誤，將使用空 cookies")
        return None

    if not cookies_data:
        print("警告: 未設置 cookies，某些私人影片可能無法訪問")
        return None

    # 創建臨時文件存儲 cookies
    temp_dir = Path(tempfile.gettempdir())
    cookies_file = temp_dir / "youtube_cookies.txt"

    # 轉換為 Netscape 格式 (yt-dlp 使用的格式)
    with open(cookies_file, "w", encoding="utf-8") as f:
        f.write("# Netscape HTTP Cookie File\n")
        
        for cookie in cookies_data:
            if "domain" not in cookie or "name" not in cookie or "value" not in cookie:
                continue
                
            domain = cookie["domain"]
            flag = "TRUE" if cookie.get("hostOnly", False) else "FALSE"
            path = cookie.get("path", "/")
            secure = "TRUE" if cookie.get("secure", False) else "FALSE"
            expires = str(int(cookie.get("expirationDate", 0)))
            name = cookie["name"]
            value = cookie["value"]
            
            f.write(f"{domain}\t{flag}\t{path}\t{secure}\t{expires}\t{name}\t{value}\n")
    
    print(f"YouTube cookies 已保存到臨時文件: {cookies_file}")
    return str(cookies_file)

# 全局變量，以便共享
COOKIES_FILE_PATH = get_cookies_path()
