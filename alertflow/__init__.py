"""
Author: Luã Bida Vacaro
Email: luabidaa@gmail.com
Github: https://github.com/luabida
Date: 2023-04-13
"""
from importlib import metadata as importlib_metadata


def get_version() -> str:
    try:
        return importlib_metadata.version(__name__)
    except importlib_metadata.PackageNotFoundError:  # pragma: no cover
        return '1.1.1'  # changed by semantic-release


version: str = get_version()
__version__: str = version
