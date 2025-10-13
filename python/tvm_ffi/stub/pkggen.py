# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
"""Python package generator."""

from __future__ import annotations

import argparse
import dataclasses
import sys


@dataclasses.dataclass
class Options:
    """Command line options for package generation."""

    prefix: str
    dlls: list[str] = dataclasses.field(default_factory=list)
    indent: int = 4
    verbose: bool = True


def __main__() -> int:
    parser = argparse.ArgumentParser(description="Generate Python package from TVM FFI metadata.")
    parser.add_argument(
        "--prefix",
        type=str,
        required=True,
        help="The prefix of the TVM FFI functions to generate.",
    )
    parser.add_argument(
        "--dlls",
        type=str,
        nargs="+",
        required=True,
        help="The shared libraries to load.",
    )
    parser.add_argument(
        "--indent",
        type=int,
        default=4,
        help="The number of spaces to use for indentation.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging.",
    )
    opt = parser.parse_args(namespace=Options(""))
    if not opt.prefix or not opt.dlls:
        parser.error("Both `--prefix` and `--dlls` are required.")
    print(opt)
    return 0


if __name__ == "__main__":
    sys.exit(__main__())
