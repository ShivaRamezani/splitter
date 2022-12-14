"""Manages info about the user's files."""
import os
import platform
import re
import subprocess
import uuid
import webbrowser
from copy import copy
from datetime import datetime
from datetime import timedelta
from typing import List
from typing import Optional
from typing import Tuple

import PySimpleGUI as sg
from send2trash import send2trash  # https://github.com/arsenetar/send2trash

from note_splitter import patterns
from note_splitter.settings import settings


class Note:
    """Info about one of the user's note files.

    Attributes
    ----------
    title : str
        The title of the note. This is the body of the first header, or
        the first line of the file if there is no header, or an empty
        string if the file is empty.
    name : str
        The name of the file, including the file extension.
    ext : str
        The file extension, starting with a period.
    path : str
        The absolute path to the file.
    folder_path : str
        The absolute path to the folder that the file is in.
    """

    def __init__(self, path: str, folder_path: str = None, name: str = None):
        """Creates a new Note object.

        Assumes that the file already exists and has its content.

        Parameters
        ----------
        path : str
            The absolute path to the file.
        folder_path : str, optional
            The absolute path to the folder that the file is in. If not
            provided, it will be retrieved from the path.
        name : str, optional
            The name of the file, including the file extension. If not
            provided, it will be retrieved from the path.
        """
        self.path = path
        if folder_path is None:
            self.folder_path = os.path.dirname(path)
        else:
            self.folder_path = folder_path
        if name is None:
            self.name = os.path.basename(path)
        else:
            self.name = name
        self.ext = os.path.splitext(self.path)[1]
        with open(self.path, "r", encoding="utf8") as file:
            contents = file.read()
        self.title = get_title(contents)

    def open(self) -> Optional[bool]:
        """Opens the note in the device's default editor.

        Returns
        -------
        bool, None
            True if the note was opened successfully, None if the note
            does not exist.
        """
        if not os.path.exists(self.path):
            sg.Popup(f"File not found: {self.path}")
            return None
        webbrowser.open("file://" + self.path)
        return True

    def show(self) -> Optional[bool]:
        """Shows the note in the file browser.

        Returns
        -------
        bool, None
            True if the note was shown successfully, None if the note
            does not exist.
        """
        if not os.path.exists(self.path):
            sg.Popup(f"File not found: {self.path}")
            return None
        if platform.system() == "Windows":
            temp_path = self.path.replace("/", "\\")
            subprocess.Popen(["explorer", "/select,", temp_path])
        elif platform.system() == "Darwin":  # macOS
            subprocess.call(["open", "-R", self.path])
        else:  # Linux
            subprocess.call(["xdg-open", "-R", self.path])
        return True

    def move(
        self, new_folder_path: str, window: sg.Window, all_notes: List["Note"]
    ) -> Optional[bool]:
        """Moves the note file to a new folder.

        Parameters
        ----------
        new_folder_path : str
            The absolute path to the new folder.
        window : sg.Window
            The application window.
        all_notes : List[Note]
            A list of all the notes in the user's notes folder.

        Returns
        -------
        bool, None
            True if the note was moved successfully, None if the note
            does not exist, False otherwise.
        """
        if not os.path.exists(self.path):
            sg.Popup(f"File not found: {self.path}")
            return None
        new_path = os.path.join(new_folder_path, self.name)
        if os.path.exists(new_path):
            sg.Popup(f"File already exists: {new_path}")
            return False
        move_files([self.path], new_folder_path, window, all_notes)
        self.path = new_path
        self.folder_path = new_folder_path
        return True

    def delete(self) -> Optional[bool]:
        """Moves the note file to the trash or recycle bin.

        Returns
        -------
        bool, None
            True if the note was deleted successfully, None if the note
            does not exist.
        """
        if not os.path.exists(self.path):
            sg.Popup(f"File not found: {self.path}")
            return None
        path = os.path.normpath(self.path)
        send2trash([path])
        return True


def get_chosen_notes(window: sg.Window, all_notes: List[Note] = None) -> List[Note]:
    """Gets the notes that the user chose to split.

    Parameters
    ----------
    window : sg.Window
        The application window.
    all_notes : List[Note], optional
        The list of all the notes in the user's chosen folder. If not
        provided, the list of all the notes in the user's chosen folder
        will be retrieved.
    """
    if all_notes is None:
        all_notes = get_all_notes(window)
    if not all_notes:
        return []

    chosen_notes: List[Note] = []
    for note in all_notes:
        with open(note.path, "r", encoding="utf8") as file:
            contents = file.read()
        if settings["split_keyword"] in contents:
            chosen_notes.append(note)

    return chosen_notes


def require_folder_path(folder_description: str) -> str:
    """Requires the user to choose a folder.

    Parameters
    ----------
    folder_description : str
        The description of the folder that the user will be choosing.

    Returns
    -------
    str
        The absolute path to a folder.
    """
    while True:
        folder_path = request_folder_path(folder_description)
        if folder_path:
            return folder_path


def request_folder_path(folder_description: str) -> Optional[str]:
    """Prompts the user to select a folder.

    Parameters
    ----------
    folder_description : str
        The description of the folder.

    Returns
    -------
    str, None
        The absolute path to a folder, or None if the user canceled.
    """
    message = f"Please select the {folder_description} folder."
    folder_path = sg.PopupGetFolder(message, keep_on_top=True)
    if not folder_path:
        return None
    settings["source_folder_path"] = folder_path
    return folder_path


def get_all_notes(window: sg.Window) -> List[Note]:
    """Gets all the notes in the user's chosen folder.

    Parameters
    ----------
    window : sg.Window
        The application window.
    """
    notes: List[Note] = []
    try:
        folder_list = os.listdir(settings["source_folder_path"])
    except FileNotFoundError:
        source_folder_path = request_folder_path("source")
        if not source_folder_path:
            return []
        else:
            settings["source_folder_path"] = source_folder_path
            window["-SOURCE FOLDER-"].update(settings["source_folder_path"])
            folder_list = os.listdir(source_folder_path)

    for file_name in folder_list:
        file_path = os.path.join(settings["source_folder_path"], file_name)
        if os.path.isfile(file_path):
            _, file_ext = os.path.splitext(file_name)
            if file_ext in settings["note_types"]:
                notes.append(Note(file_path, settings["source_folder_path"], file_name))

    return notes


def create_file_names(file_ext: str, files_contents: List[str]) -> List[str]:
    """Creates names for new files.

    The returned file names are in the format specified in the
    file_name_format setting. If more than one file name is created and
    file_name_format contains a time variable, the time will be
    incremented for each file name.

    Parameters
    ----------
    file_ext : str
        The file extension, including the leading period.
    files_contents : List[str]
        The contents of the files to be named.
    """
    file_names = []
    now = datetime.now()
    for file_contents in files_contents:
        file_name_format = copy(settings["file_name_format"])
        if r"%id" in file_name_format:
            file_name_format = file_name_format.replace(
                r"%id", settings["file_id_format"]
            )
        new_file_name = __create_file_name(
            file_ext, file_name_format, file_contents, now
        )
        new_file_name = validate_file_name(new_file_name)
        file_names.append(new_file_name)
        if r"%s" in file_name_format:
            now += timedelta(seconds=1)
        elif r"%m" in file_name_format:
            now += timedelta(minutes=1)
        elif r"%h" in file_name_format:
            now += timedelta(hours=1)
        elif r"%D" in file_name_format:
            now += timedelta(days=1)
    return file_names


def __create_file_name(
    file_ext: str, file_name_format: str, file_contents: str, dt: datetime
) -> str:
    """Creates a name for a new file.

    Parameters
    ----------
    file_ext : str
        The file extension, including the leading period.
    file_name_format : str
        The format of the file name.
    file_contents : str
        The contents of the file to be named.
    dt : datetime
        The date and time to use for the file name if the file name
        format contains any date and/or time variables.
    """
    if not file_name_format:
        file_name_format = r"%uuid4"
    variables = __get_variables(file_contents, dt)
    variables.append((r"%id", create_file_id(file_contents, dt)))
    for name, value in variables:
        file_name_format = file_name_format.replace(name, value)
    return f"{file_name_format}{file_ext}"


def create_file_id(file_contents: str, dt: datetime = None) -> str:
    """Creates an ID for a file.

    This function depends on the file_id_format setting.

    Parameters
    ----------
    file_contents : str
        The contents of the file to be IDed.
    dt : datetime, optional
        The datetime to use in the file name. If not provided, the
        current time will be used.
    """
    if dt is None:
        dt = datetime.now()
    file_id = copy(settings["file_id_format"])
    variables = __get_variables(file_contents, dt)
    for name, value in variables:
        file_id = file_id.replace(name, value)
    return file_id


def __get_variables(file_contents: str, dt: datetime) -> List[Tuple[str, str]]:
    """Gets the variable names and values for file name and ID formats.

    Parameters
    ----------
    file_contents : str
        The contents of the file being named or IDed.
    dt : datetime
        The datetime to use in the file name or ID if the format
        contains any date and/or time variables.
    """
    return [
        (r"%uuid4", str(uuid.uuid4())),
        (r"%title", get_title(file_contents)),
        (r"%Y", str(dt.year)),
        (r"%M", str(dt.month).zfill(2)),
        (r"%D", str(dt.day).zfill(2)),
        (r"%h", str(dt.hour).zfill(2)),
        (r"%m", str(dt.minute).zfill(2)),
        (r"%s", str(dt.second).zfill(2)),
    ]


def get_title(file_contents: str) -> str:
    """Gets the title of the file.

    The title is the body of the first header, or the first line if
    there is no header, or a random string if the file is empty.

    Parameters
    ----------
    file_contents : str
        The contents of the file to get the title from.
    """
    for line in file_contents.split("\n"):
        if patterns.header.match(line):
            return line.lstrip("#").strip()
    title = file_contents.split("\n")[0].strip()
    if title:
        return title
    return str(uuid.uuid4())


def validate_file_name(file_name: str, max_length: int = 30) -> str:
    """Validates a file name's characters and length.

    This function does NOT ensure that a file with the same name does
    not already exist. Invalid characters are replaced with hyphens. If
    the file name has a length greater than max_length, it is truncated.
    If the file name starts or ends with certain characters, they are
    removed.

    Parameters
    ----------
    file_name : str
        The file name to validate.
    max_length : int, optional
        The maximum length of the file name.

    Returns
    -------
    file_name : str
        The validated file name.
    """
    root, ext = os.path.splitext(file_name)
    root = root[:max_length]
    invalid_characters = "#%{&}\\<>*?/$!'\":@+`|="
    for ch in invalid_characters:
        root = root.replace(ch, "-")
    root = root.strip(" .-_")
    return root + ext


def ensure_file_path_uniqueness(file_path: str) -> str:
    """Makes sure a file's path is unique.

    If a file with the same name already exists, a ``.1`` is appended
    to the file name unless that is already there, in which case it is
    changed to ``.2``, etc. This function assumes the file name does
    not have any invalid characters.

    Parameters
    ----------
    file_path : str
        The absolute path for the file, including the planned file name.

    Returns
    -------
    file_path : str
        The absolute path for the file, including the unique file name.
    """
    while os.path.exists(file_path):
        folder_path, file_name_and_ext = os.path.split(file_path)
        file_name, file_ext = os.path.splitext(file_name_and_ext)
        match = re.match(r".+\.(\d+)$", file_name)
        if not match:
            file_name += ".1"
        else:
            file_name = file_name[: match.start(1)] + f"{int(match[1]) + 1}"
        file_name_and_ext = file_name + file_ext
        file_path = os.path.join(folder_path, file_name_and_ext)
    return file_path


def move_files(
    paths_of_files_to_move: List[str],
    destination_path: str,
    window: sg.Window,
    all_notes: List[Note] = None,
) -> None:
    """Moves files and updates all relevant references everywhere.

    Updates paths to these files in any of the notes in the source
    folder chosen in settings, and updates any relative paths in these
    files if they are of a note type.

    Parameters
    ----------
    paths_of_files_to_move : List[str]
        List of absolute paths of files to be moved. These can be files
        of any type.
    destination_path : str
        Absolute path to the destination folder.
    window : sg.Window
        The window to update.
    all_notes : List[Note], optional
        List of all notes in the source folder. If not given, it will be
        loaded from the source folder.
    """
    if all_notes is None:
        all_notes = get_all_notes(window)
    for path in paths_of_files_to_move:
        path = os.path.normpath(path)
        file_name_with_ext = os.path.basename(path)
        _, file_ext = os.path.splitext(file_name_with_ext)
        if file_ext in settings["note_types"]:
            _make_file_paths_absolute(note_path=path)
        new_path = os.path.join(destination_path, file_name_with_ext)
        new_path = os.path.normpath(new_path)
        __change_all_links_to_file(path, new_path, all_notes)
        os.rename(path, new_path)


def make_file_paths_absolute(note_content: str, note_path: str) -> str:
    """Makes all file paths in a note's file links absolute.

    Assumes that all the file paths that should be made absolute are
    valid. Invalid paths are ignored.

    Parameters
    ----------
    note_content : str
        The note's content.
    note_path : str
        The absolute path to the note.

    Returns
    -------
    note_content : str
        The note's content with all file paths made absolute.
    """
    note_folder_path = os.path.dirname(note_path)
    file_paths: List[Tuple[str, str]] = get_file_paths(note_content, note_folder_path)
    for original_path, formatted_path in file_paths:
        note_content = note_content.replace(original_path, formatted_path)
    return note_content


def _make_file_paths_absolute(note_path: str) -> None:
    """Makes all file paths in a note's file links absolute.

    Assumes that all the file paths that should be made absolute are
    valid. Invalid paths are ignored.

    Parameters
    ----------
    note_path : str
        Absolute path to the note.
    """
    with open(note_path, "r", encoding="utf8") as file:
        content = file.read()
    content = make_file_paths_absolute(content, note_path)
    with open(note_path, "w", encoding="utf8") as file:
        file.write(content)


def __change_all_links_to_file(
    current_path_to_change: str, new_path: str, all_notes: List[Note]
) -> None:
    """Changes the path to a file in all notes' links.

    Use this before moving a file to a different location.

    Parameters
    ----------
    current_path_to_change : str
        Absolute path to the file.
    new_path : str
        Absolute path the file will have after being moved.
    all_notes : List[Note]
        List of all notes in the source folder.
    """
    for note_ in all_notes:
        with open(note_.path, "r", encoding="utf8") as file:
            content = file.read()
        file_paths = get_file_paths(content, note_.folder_path)
        for original_path, formatted_path in file_paths:
            if os.path.samefile(formatted_path, current_path_to_change):
                content = content.replace(original_path, new_path)
        with open(note_.path, "w", encoding="utf8") as file:
            file.write(content)


def get_file_paths(note_content: str, note_folder_path: str) -> List[Tuple[str, str]]:
    """Gets the original and formatted file paths in links in a note.

    Only paths to files that exist are returned.

    Parameters
    ----------
    note_content : str
        The note's content.
    note_folder_path : str
        The absolute path to the note's folder.

    Returns
    -------
    List[Tuple[str, str]]
        List of tuples of the original file path in the note and its
        normalized, absolute version. All the paths are valid. (Broken
        file links and links to websites are ignored.)
    """
    noted_file_path_groups: List[Tuple[str]] = patterns.file_path_in_link.findall(
        note_content
    )
    noted_file_paths: List[str] = [t[0] for t in noted_file_path_groups]
    file_paths: List[Tuple[str, str]] = []
    for file_path in noted_file_paths:
        if os.path.isabs(file_path):
            abs_path = file_path
        else:
            abs_path = os.path.join(note_folder_path, file_path)
        norm_path = os.path.normpath(abs_path)
        if os.path.exists(norm_path):
            file_paths.append((file_path, norm_path))
    return file_paths


def get_by_title(notes: List[Note], title: str) -> Note:
    """Gets a note by its title.

    Parameters
    ----------
    notes : List[Note]
        List of all notes in the source folder.
    title : str
        The title of the note.

    Returns
    -------
    Note
        The note with the given title.
    """
    for note in notes:
        if note.title == title:
            return note
    raise ValueError(f'Note with title "{title}" not found.')
