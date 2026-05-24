# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0

"""Pytest configuration for the Weave addon."""

from __future__ import annotations

import sys
from pathlib import Path

_ADDON_ROOT = Path(__file__).resolve().parents[1]
_REPO_ROOT = _ADDON_ROOT.parents[1]

for _path in (_ADDON_ROOT / "python", _REPO_ROOT / "python"):
    _path_str = str(_path)
    if _path_str not in sys.path:
        sys.path.insert(0, _path_str)

del Path, _ADDON_ROOT, _REPO_ROOT, _path, _path_str
