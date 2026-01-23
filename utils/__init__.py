# utils/__init__.py
from .platform_utils import (
    get_base_path,
    open_download_folder,
    setup_env_path,
    is_cmd_available
)
from .cookie_utils import parse_cookie_file
from .net_utils import ResourceProvider