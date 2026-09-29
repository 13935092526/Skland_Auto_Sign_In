"""全局常量，对应 skland-kit 的 src/constants.ts 及各处硬编码值。"""

# 森空岛签名时间向前偏移，规避服务端时间校验过严导致的误判（毫秒）
SERVER_TIMESTAMP_OFFSET_MS = 2 * 1000

# 森空岛在鹰角通行证的 appCode
SKLAND_APP_CODE = '4ca99fa6b56cc2ba'

# API 主机
SKLAND_BASE_URL = 'https://zonai.skland.com'
HYPERGRYPH_BASE_URL = 'https://as.hypergryph.com'

# 终末地
ENDFIELD_GAME_ID = 3
ENDFIELD_APP_CODE = 'endfield'
ENDFIELD_GAME_NAME = '明日方舟：终末地'

# 请求头
MOBILE_UA = (
    'Mozilla/5.0 (Linux; Android 12; SM-A5560 Build/V417IR; wv) '
    'AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 '
    'Chrome/101.0.4951.61 Safari/537.36; SKLand/1.52.1'
)
DESKTOP_UA = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
    'AppleWebKit/537.36 (KHTML, like Gecko) '
    'Chrome/129.0.0.0 Safari/537.36'
)
X_REQUESTED_WITH = 'com.hypergryph.skland'

# 签名头部固定字段
SIGN_PLATFORM = '3'
SIGN_VNAME = '1.0.0'

# 默认行为配置
DEFAULT_MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 1.0
REQUEST_TIMEOUT_SECONDS = 30
