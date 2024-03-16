import argparse
import logging
import sys

from bs4 import Tag, NavigableString, BeautifulSoup

__version__ = "0.1.2"

logger = logging.getLogger(__name__)


class Context:
    def __init__(self):
        self.tags = []
        self.indent_level = 0
        self.table_shape = (0, 0)
        self.table_index = (0, 0)

    @property
    def tag_depth(self):
        return len(self.tags)

    def down_tag(self, tag: str):
        self.tags.append(tag)

    def up_tag(self):
        return self.tags.pop()

    def inc_indent(self):
        self.indent_level += 1
        return self.indent_level

    def dec_indent(self):
        self.indent_level -= 1
        return self.indent_level

    def bullet_prefix(self):
        """
        Return a bullet sign for listing.
        """
        indent = "    " * (self.indent_level - 1)
        for tag in reversed(self.tags):
            if tag == "ul":
                return indent + "-"
            elif tag == "ol":
                return indent + "1."
        raise ValueError('Not inside "ul" or "ol".')

    def inside_table(self):
        return "table" in self.tags

    def is_second_row(self):
        row, _ = self.table_index
        return row == 2

    def next_row_index(self):
        row, col = self.table_index
        self.table_index = (row + 1, col)

    def next_column_index(self):
        row, col = self.table_index
        self.table_index = (row, col + 1)

    def clear_table_index(self):
        self.table_index = (0, 0)


class MarkdownConverter:
    def __init__(self):
        self._context: Context = None

    def convert(self, content: Tag):
        self._context = Context()
        return self._convert(content)

    def _convert(self, content):
        if isinstance(content, Tag):
            logger.info("%s => %s", type(content), content.name)
            try:
                self._context.down_tag(content.name)
                return self._convert_tag(content)
            finally:
                self._context.up_tag()
        elif isinstance(content, NavigableString):
            logger.info("%s => %s", type(content), content)
            return str(content).strip()

    def _convert_tag(self, tag: Tag):
        if tag.name == "html":
            return self._convert_html(tag)
        elif tag.name == "s":
            return ""
        elif tag.name == "h1":
            return f"# {self._convert_contents(tag)}\n\n"
        elif tag.name == "h2":
            return self._convert_h2(tag)
        elif tag.name == "h3":
            return self._convert_h3(tag)
        elif tag.name == "div":
            return self._convert_div(tag)
        elif tag.name == "p":
            return f"{self._convert_contents(tag)}\n"
        elif tag.name == "blockquote":
            return f">{self._convert_contents(tag)}\n"
        elif tag.name == "pre":
            # don't interpret tags under <pre> tag and use innerText as is
            return f"```\n{tag.text.strip()}\n```\n"
        elif tag.name == "code":
            return f"`{self._convert_contents(tag)}`"
        elif tag.name == "a":
            return self._convert_a(tag)
        elif tag.name == "span":
            return f"{self._convert_contents(tag)}"
        elif tag.name == "u":
            return f"{self._convert_contents(tag)}"
        elif tag.name == "b":
            return f"**{self._convert_contents(tag)}**"
        elif tag.name == "em":
            return f"*{self._convert_contents(tag)}*"
        elif tag.name == "strong":
            return f"__{self._convert_contents(tag)}__"
        elif tag.name == "br":
            return self._convert_br()
        elif tag.name == "ul":
            return self._convert_list(tag)
        elif tag.name == "ol":
            return self._convert_list(tag)
        elif tag.name == "li":
            return self._convert_li(tag)
        elif tag.name == "table":
            return self._convert_table(tag)
        elif tag.name == "colgroup":
            return ""  # ignore
        elif tag.name == "tbody":
            return f"{self._convert_contents(tag)}\n"
        elif tag.name == "tr":
            self._context.next_row_index()
            return self._convert_tr(tag)
        elif tag.name == "td":
            self._context.next_column_index()
            return f"{self._convert_contents(tag).strip()} | "
        elif tag.name == "img":
            return self._convert_img(tag)
        else:
            return f"<<<CANNOT CONVERT {tag.name}>>>"

    def _convert_contents(self, tag: Tag):
        return "".join([self._convert(c) for c in tag.children])

    def _convert_a(self, a: Tag):
        href = a.attrs["href"]
        text = self._convert_contents(a)
        if href == text:
            # use URL if URL and label is the same
            return href
        else:
            return f"[{text}]({href})"

    def _convert_list(self, tag: Tag):
        try:
            self._context.inc_indent()
            return f"\n{self._convert_contents(tag)}"
        finally:
            self._context.dec_indent()

    def _convert_li(self, li: Tag):
        inner_text = self._convert_contents(li)
        prefix = self._context.bullet_prefix()
        return f"{prefix} {inner_text}\n"

    def _convert_html(self, html: Tag):
        # Embedded metadata into HTML comment
        metadata = f"""\
<!--
page: {html.attrs["data-page"]}
canvas: {html.attrs["data-canvas"]}
site: {html.attrs["data-site"]}
list: {html.attrs["data-list"]}
tabId: {html.attrs["data-tabid"]}
slug: {html.attrs["data-slug"]}
threadId: {html.attrs["data-threadid"]}
-->
"""
        return metadata + self._convert_contents(html)

    def _convert_h3(self, tag: Tag):
        if "wiki-mht-note" in tag.attrs.get("class", []):
            # ignore "wiki-mht-note" class because it is a hidden element in Teams wiki
            return ""
        return f"### {self._convert_contents(tag)}\n\n"

    def _convert_h2(self, tag: Tag):
        if "wiki-mht-note" in tag.attrs.get("class", []):
            # ignore "wiki-mht-note" class because it is a hidden element in Teams wiki
            return ""
        return f"## {self._convert_contents(tag)}\n\n"

    def _convert_br(self):
        if self._context.inside_table():
            return "<br />"
        else:
            return " \n"

    def _convert_div(self, tag):
        if self._context.inside_table():
            return f"{self._convert_contents(tag)}<br />"
        else:
            return f"{self._convert_contents(tag)}\n"

    def _convert_table(self, table: Tag):
        try:
            rows = len(table.find_all("tr"))
            cols = len(table.find_all("col"))
            self._context.table_shape = (rows, cols)
            return f"\n{self._convert_contents(table)}\n"
        finally:
            self._context.clear_table_index()

    def _convert_tr(self, tr: Tag):
        if self._context.is_second_row():
            # insert a separator in the second row
            separator = "|" + (" --- |" * self._context.table_shape[1]) + "\n"
        else:
            separator = ""
        return separator + "| " + self._convert_contents(tr) + "\n"

    def _convert_img(self, img: Tag):
        if "data-preview-src" in img.attrs:
            src = img.attrs["data-preview-src"]
            # "data-preview-src" attribute is a string like below.
            # "/sites/msteams_1b3d5f/Teams Wiki Data/General/img-123-fe3028d38dc34d1e94b6cd350d0f9941.png"
            # Last entry "img-123-fe3028d38dc34d1e94b6cd350d0f9941.png" is a image file stored in
            # "Teams Wiki Data" folder, so link it as embedded image.
            url = src.split("/")[-1]
        else:
            # Preserve original "src" attrribute
            url = img.attrs["src"]
        return f"![]({url})"


def cli_main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--verbose", action="store_true", help="output logging message")
    parser.add_argument("--version", action="store_true", help="output this program version")
    parser.add_argument("file", type=str, nargs="?", help="mhtml file to convert into markdown")
    args = parser.parse_args(sys.argv[1:])

    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING, stream=sys.stderr)

    if args.version:
        print(__version__)
        return

    with open(args.file, mode="r", encoding="utf-8") as f:
        html_text = f.read()
    soup = BeautifulSoup(html_text, "html.parser")  # parse HTML

    # print(soup.prettify())
    html: Tag = soup.html
    converter = MarkdownConverter()
    markdown = converter.convert(html)
    print(markdown)


if __name__ == "__main__":
    cli_main()
