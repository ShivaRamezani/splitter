"""For changing some important details in Section tokens before output.

The Formatter class' callable normalizes header levels, adds frontmatter
and global tags to each section, and then converts the section tokens to
strings.
"""
import uuid
from typing import List
from typing import Optional

import yaml  # https://pyyaml.org/wiki/PyYAMLDocumentation

from note_splitter import tokens
from note_splitter.settings import settings


class Formatter:
    """Creates a Callable that prepares sections for output.

    The callable normalizes header levels, adds frontmatter and global
    tags to each section, and then converts the section tokens to
    strings.
    """

    def __call__(
        self,
        sections: List[tokens.Section],
        global_tags: List[str],
        frontmatter: Optional[object] = None,
        footnotes: Optional[List[tokens.Footnote]] = None,
    ) -> List[str]:
        """Formats sections for output.

        Parameters
        ----------
        sections : List[tokens.Section]
            The sections to format.
        global_tags : List[str]
            The global tags to add to each section.
        frontmatter : Optional[object]
            The frontmatter to add to each section.
        footnotes : Optional[List[tokens.Footnote]]
            The footnotes to add to each section with the respective
            footnote reference.
        """
        split_contents: List[str] = []
        for section in sections:
            if not section:
                continue
            section_title = None
            if isinstance(section[0], tokens.Header):
                section_title = self.normalize_headers(section)
            if settings["copy_global_tags"] and global_tags:
                self.insert_global_tags(global_tags, section)
            if settings["copy_frontmatter"]:
                if not section_title:
                    section_title = self.get_section_title(section)
                self.prepend_frontmatter(frontmatter, section_title, section)
            if settings["move_footnotes"] and footnotes:
                self.move_footnotes(footnotes, section)
            split_contents.append(str(section))
        return split_contents

    def normalize_headers(self, section: tokens.Section) -> str:
        """Normalizes the markdown header levels in a section.

        Parameters
        ----------
        section : tokens.Section
            The section to normalize.

        Returns
        -------
        str
            The title of the section.
        """
        assert isinstance(section[0], tokens.Header)
        if section[0].level <= 1:
            return section[0].body
        difference = section[0].level - 1
        for i, token in enumerate(section):
            if isinstance(token, tokens.Header):
                token.level -= difference
                token.content = token.content[difference:]
                section[i] = token
        return section[0].body

    def insert_global_tags(
        self, global_tags: List[str], section: tokens.Section
    ) -> None:
        """Inserts the global tags into a section.

        Parameters
        ----------
        global_tags : List[str]
            The global tags to add to the section.
        section : tokens.Section
            The section to insert the global tags into.
        """
        i = 0
        while i < len(section) and not isinstance(section[i], tokens.Header):
            i += 1
        i += 1
        if i <= len(section):
            section.insert(i, tokens.Text(" ".join(global_tags)))
        else:
            section.insert(0, tokens.Text(" ".join(global_tags)))

    def get_section_title(self, section: tokens.Section) -> str:
        """Gets the title of a section.

        The title is the body of the first header, or the first Text
        token's content if there is no header, or a random string if the
        section is empty.

        Parameters
        ----------
        section : tokens.Section
            The section to get the title of.
        """
        for token in section:
            if isinstance(token, tokens.Header):
                return token.body
        for token in section:
            if isinstance(token, tokens.Text):
                return token.content.strip()
        return str(uuid.uuid4())

    def prepend_frontmatter(
        self, frontmatter: Optional[object], section_title: str, section: tokens.Section
    ) -> None:
        """Prepends the frontmatter to a section as a Text object.

        Parameters
        ----------
        frontmatter : Optional[object]
            The frontmatter to add to the section.
        section_title : str
            The title of the section.
        section : tokens.Section
            The section to prepend the frontmatter to.
        """
        if not frontmatter:
            return
        if isinstance(frontmatter, dict):
            if "title" in frontmatter:
                frontmatter["title"] = section_title
        frontmatter_string = yaml.dump(frontmatter)
        frontmatter_string = "---\n" + frontmatter_string + "---\n"
        frontmatter_string = frontmatter_string.replace("\n\n", "\n")
        section.insert(0, tokens.Text(frontmatter_string))

    def move_footnotes(
        self, footnotes: List[tokens.Footnote], section: tokens.Section
    ) -> None:
        """Moves footnotes to sections with the relevant references.

        Parameters
        ----------
        footnotes : List[tokens.Footnote]
            The footnotes to add to the section if it contains
            references to them, or to remove from the section if it does
            not contain references to them.
        section : tokens.Section
            The section to append/remove the footnotes to/from.
        """
        for footnote in footnotes:
            if footnote_referenced_in_section(footnote, section):
                if footnote not in section:
                    section.append(footnote)
            elif footnote in section:
                section.remove(footnote)


def footnote_referenced_in_section(
    footnote: tokens.Footnote, section: tokens.Section
) -> bool:
    """Checks if a footnote is referenced in a section.

    Parameters
    ----------
    footnote : tokens.Footnote
        The footnote to search for a reference to.
    section : tokens.Section
        The section to search in.

    Returns
    -------
    bool
        Whether the footnote is referenced in the section.
    """
    for token in section:
        if (
            isinstance(token, tokens.CanHaveInlineElements)
            and not isinstance(token, tokens.Footnote)
            and footnote.reference
            and footnote.reference in token.content
        ):
            return True
    return False
