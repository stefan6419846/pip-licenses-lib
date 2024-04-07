"""
Make `importlib.metadata` compatible for intersphinx mappings.

Issue: The official Python docs refer to the external `importlib_metadata` package
and thus this is leading to undefined names.

Upstream implementation: https://github.com/sphinx-doc/sphinx/blob/master/sphinx/ext/intersphinx.py
"""

# This file is loosely based upon the upstream implementation of the intersphinx extension.
# Original source: https://github.com/sphinx-doc/sphinx/blob/c7c02002e58befc64e4df7db0263994db5204f12/sphinx/ext/intersphinx.py
# The file follows the same copyright.
#
# Copyright (c) 2007-2024 by the Sphinx team (see AUTHORS file).
# Copyright (c) 2024 stefan6419846
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are
# met:
#
# * Redistributions of source code must retain the above copyright
#   notice, this list of conditions and the following disclaimer.
#
# * Redistributions in binary form must reproduce the above copyright
#   notice, this list of conditions and the following disclaimer in the
#   documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import functools
import zlib
from typing import Generator, IO, List

import requests
from sphinx.util.inventory import InventoryFileReader


def load_original(url: str) -> IO:
    response = requests.get(url, stream=True)
    response.raise_for_status()
    response.raw.url = response.url
    # decode content-body based on the header.
    # ref: https://github.com/psf/requests/issues/2155
    response.raw.read = functools.partial(response.raw.read, decode_content=True)
    return response.raw


def load_lines(url: str) -> Generator[str, None, None]:
    data = load_original(url)
    reader = InventoryFileReader(data)
    yield data.readline().decode()  # Inventory version.
    yield data.readline().decode()  # Project name.
    yield data.readline().decode()  # Project version.
    yield data.readline().decode()  # Compression indicator.
    for line in reader.read_compressed_lines():
        yield line


def replace_names(lines: List[str], source: str, target: str) -> None:
    for index, line in enumerate(lines):
        if line.startswith("# Project: "):
            lines[index] = "# Project: " + target
        if line.startswith(source):
            name = line.split(" ", maxsplit=1)
            new_line = target + line[len(source):]
            if " api.html#$ " in line:
                # Self-references (`$`) do not work anymore due to changing the name.
                # Fix this by adding an explicit reference with the original name.
                new_line = new_line.replace(" api.html#$ ", f" api.html#{name[0]} ")
            lines[index] = new_line


def dump(filename: str, lines: List[str]):
    with open(filename, 'wb') as f:
        # header
        f.write((
            f'# Sphinx inventory version 2\n'
            f'{lines[1].rstrip()}\n'
            f'# Version: custom\n'
            f'# The remainder of this file is compressed using zlib.\n'
        ).encode())

        # body
        compressor = zlib.compressobj(9)
        for line in lines[4:]:  # Skip header lines.
            # Ensure we add a trailing newline!
            f.write(compressor.compress(f'{line}\n'.encode()))
        f.write(compressor.flush())


def main() -> None:
    lines = list(load_lines("https://importlib-metadata.readthedocs.io/en/latest/objects.inv"))
    replace_names(lines, "importlib_metadata", "importlib.metadata")
    dump(filename="importlib.metadata-inv.txt", lines=lines)


if __name__ == "__main__":
    main()
