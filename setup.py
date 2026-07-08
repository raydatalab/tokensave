"""Setup script — installs the .pth auto-activation file alongside the package.

The .pth file triggers `import tokensave._auto` on Python startup,
which monkey-patches openai.OpenAI with tokensave optimizations.

This is what makes `pip install tokensave` truly zero-config:
users keep `from openai import OpenAI`, bills go down automatically.
"""

import sysconfig
from setuptools import setup

sitepackages = sysconfig.get_path("purelib")

setup(
    data_files=[(sitepackages, ["tokensave.pth"])],
)
