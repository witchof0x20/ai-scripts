#!/usr/bin/env python3
"""Convert text to a PDF and embed it as an attachment in another PDF."""

import argparse
import io
import os
import sys

import fpdf
import pikepdf


def text_to_pdf(text):
    """Convert a string of text into a PDF byte stream."""
    pdf = fpdf.FPDF()
    pdf.add_page()
    pdf.set_font("Courier", size=10)
    pdf.multi_cell(0, 5, text)
    return pdf.output()


def main():
    parser = argparse.ArgumentParser(prog="pdfhide", description="Embed a text file as a PDF attachment inside a PDF")
    parser.add_argument("input", help="Input PDF file")
    parser.add_argument("output", help="Output PDF file")
    parser.add_argument(
        "-f", "--file", type=argparse.FileType("rb"), default=sys.stdin.buffer,
        help="File to attach (default: stdin)",
    )
    parser.add_argument(
        "-n", "--name", default="extra.pdf",
        help="Filename for the attachment (default: extra.pdf)",
    )
    args = parser.parse_args()

    text = args.file.read().decode("utf-8", errors="replace")
    embedded_pdf = text_to_pdf(text)

    with pikepdf.open(args.input) as pdf:
        filespec = pikepdf.AttachedFileSpec(
            pdf, bytes(embedded_pdf), filename=args.name, mime_type="application/pdf",
        )
        pdf.attachments[args.name] = filespec
        pdf.save(args.output)


if __name__ == "__main__":
    main()
