#!/usr/bin/env python3
"""Attach a text file to a PDF as an embedded file."""

import argparse
import sys

import pikepdf


def main():
    parser = argparse.ArgumentParser(prog="pdfhide", description="Attach a text file to a PDF")
    parser.add_argument("input", help="Input PDF file")
    parser.add_argument("output", help="Output PDF file")
    parser.add_argument(
        "-f", "--file", type=argparse.FileType("rb"), default=sys.stdin.buffer,
        help="File to attach (default: stdin)",
    )
    parser.add_argument(
        "-n", "--name", default="extra.txt",
        help="Filename for the attachment (default: extra.txt)",
    )
    args = parser.parse_args()

    data = args.file.read()

    with pikepdf.open(args.input) as pdf:
        pdf.attachments[args.name] = data
        pdf.save(args.output)


if __name__ == "__main__":
    main()
