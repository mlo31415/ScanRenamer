"""
ScanRenamer.py

Renames a batch of scanned files (in place) to the standard form

    XXX num pnnn.ext

where XXX is a title string typed into the dialog, num is an issue
number/letter combination also typed into the dialog, "p" is a literal, and nnn
is a sequence number which starts at 1 and increases by one for each file in the
order the files were supplied.  The sequence number is padded with leading zeroes
to just as many digits as the batch needs: 1...9 for nine files, 01...12 for
twelve, 001...150 for a hundred and fifty.  Each file keeps its own extension.

Files are supplied in any of three ways:

    * dropped on the window (a dropped folder stands for the files in it)
    * chosen with the Select Files... button
    * picked up from a watched folder

The batch is shown two columns wide -- each file on the left and the name it
would be renamed to on the right, the two being columns of one list so that they
cannot scroll apart.  The proposed names follow the name and number keystroke by
keystroke, from the first character typed; whichever of the two has not been
filled in yet is simply left out of them.  With neither filled in there is only
the page numbering to show, and it is spaced out as "p 01.jpg" to look like the
placeholder it is.

The order in which they are supplied is the order in which they are numbered; if
that order is not name order the user is warned and gets to choose between
sorting them and keeping them as they came.

Name order compares names as text except for a number at the end of the name,
which is compared as a number: "page9" comes before "page10" instead of after
it, and a scanner numbering its pages without padding is put in the order it
made them.  A name with no number at the end comes before the numbered ones
sharing its text, which is where the scanner's own first page ("z-.jpg" before
"z-_1.jpg") belongs.  Files from the watched folder are in this order already
and are never asked about.

The folder to watch and the prefix the scanner names its files with come from the
"Watch Folder=" and "Scan Prefix=" lines of "ScanRenamer settings.txt" in the
program's directory, which is read when the program starts; watching needs both
of them.  While no files have been supplied by hand, every file in that folder
named "{prefix}.jpg" or "{prefix}_nnn.jpg" (.jpeg counts too) is loaded into the
batch in name order, and the list is kept up to date as more pages are
scanned, until Rename is pressed.  A rename which would produce a name that
looks like scanner output is refused, so that the watcher can never pick a
renamed file back up.

Nothing is ever renamed over the top of an existing file.  The whole batch is
looked over first and anything which would go wrong is reported, naming the
files it is about, and nothing at all is renamed: a file which would land on a
name already taken by a file outside the batch, two files of the batch which
would end up with the same name, or the same file supplied twice.  The same
looking-over is done before undoing a rename, where a scan made since may have
taken one of the names the batch is going back to.

The title string is remembered from batch to batch (and from run to run); the
number is cleared after each successful batch, since it always changes.

Every batch is written to "ScanRenamer state.json" alongside this program as a
table of old-name/new-name pairs, and Undo Last Rename puts the most recent batch
back the way it was -- including the number it was renamed with, which goes back
into the dialog so that the batch can be done again with whatever needed
correcting.  The last fifty batches are kept, that being as far back as anything
can be undone; the file is read and written whole every time a batch is renamed,
so there is no sense in letting it grow for ever.  It is written by making a new
file and putting it in the old one's place, so that stopping half way through
cannot destroy the table; and a state file which cannot be read is put aside
under its own name rather than being written over.

A rename which is interrupted part way -- the program killed, the machine losing
power -- leaves the files it had already moved under temporary names ending in
".ScanRenamerTmp".  These are looked for in the watched folder at startup and
offered back under their own names.
"""

import json
import os
import re
import sys
from datetime import datetime

import wx

# The settings, which the user edits, and the persistent state (the retained title string
# and the table of renames done so far), which the program maintains.
SettingsFileName="ScanRenamer settings.txt"
StateFileName="ScanRenamer state.json"

# Characters which Windows will not accept in a file name.
IllegalCharacters='\\/:*?"<>|'

# The extensions the scanner writes.
ScanExtensions=r"\.jpe?g"

# What pass 1 of a rename tacks onto a name to move a file out of its own way.  A file is
# under one of these names only while a batch is being renamed -- unless the program is
# stopped in the middle of one, and then they are left behind for LeftoverTempFiles to find.
TempSuffix=".ScanRenamerTmp"

# How often the watched folder is looked at, in milliseconds.
WatchInterval=1000

# How many batches the state file keeps.  Undo walks back through them one at a time, so this
# is how far back a rename can be undone; the older ones are only so much weight in the file,
# which is read and written whole every time a batch is renamed.
MaxBatchesKept=50

# The gap between the two columns of the display, in 96-to-the-inch units: about a third of
# an inch.  It is turned into real pixels with FromDIP(), so it stays a third of an inch on
# a high-resolution screen too.
ColumnGap=32


# Where the program's own directory is.  PyInstaller unpacks a frozen program into a
# temporary folder and points __file__ at that, so everything the *user* keeps -- the
# settings and the state -- must be looked for beside the executable instead.
def ProgramDirectory() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


# Read the settings file of name=value lines.  Blank lines and lines starting with '#' are
# ignored, as is a value whose first character is '#' (a commented-out value means "unset").
# Names are matched case-insensitive.  A missing settings file is not an error.
def ReadSettings() -> dict[str, str]:
    settings: dict[str, str]={}
    try:
        with open(os.path.join(ProgramDirectory(), SettingsFileName), "r", encoding="utf-8") as f:
            for line in f:
                line=line.strip()
                if len(line) == 0 or line.startswith("#") or "=" not in line:
                    continue
                name, _, val=line.partition("=")
                val=val.strip()
                if val.startswith("#"):
                    continue
                if len(val) > 1 and val[0] == val[-1] and val[0] in "\"'":
                    val=val[1:-1]       # A path pasted with its quotes still on it

                settings[name.strip().casefold()]=val
    except OSError:
        pass
    return settings


# The full path of the state file, which lives in the program's own directory.
def StateFilePath() -> str:
    return os.path.join(ProgramDirectory(), StateFileName)


# Read the saved state.  Not having one yet is perfectly normal and we just start clean.
# A damaged one is another matter: it holds the table of renames done, which is the only
# record of what was renamed to what, so it is put aside under its own name rather than
# being written over, and the user is told.
def ReadState() -> dict:
    empty={"Title": "", "Batches": []}
    try:
        with open(StateFilePath(), "r", encoding="utf-8") as f:
            state=json.load(f)
    except OSError:
        return empty
    except json.JSONDecodeError as e:
        aside=os.path.join(ProgramDirectory(), f"ScanRenamer state (damaged {datetime.now():%Y-%m-%d %H%M%S}).json")
        try:
            os.replace(StateFilePath(), aside)
            saved=f"\n\nIt has been put aside as '{os.path.basename(aside)}' in case the renames it lists are wanted."
        except OSError:
            saved=""
        wx.MessageBox(f"'{StateFileName}' cannot be read ({e}), so Undo Last Rename has nothing to work "
                      f"from until a new batch is renamed.{saved}", "ScanRenamer", wx.OK|wx.ICON_ERROR)
        return empty

    if "Title" not in state:
        state["Title"]=""
    if "Batches" not in state:
        state["Batches"]=[]
    return state


# Save the state, by writing a new file and putting it in the old one's place.  Writing over
# the old one would leave nothing but wreckage if the program stopped half way through, and
# the table of renames done would go with it.
def WriteState(state: dict) -> None:
    partial=StateFilePath()+".partial"
    try:
        with open(partial, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(partial, StateFilePath())
    except OSError as e:
        wx.MessageBox(f"Unable to save {StateFileName}:\n{e}", "ScanRenamer", wx.OK|wx.ICON_ERROR)


# Rename a list of (old, new) pairs in two passes, so that the new names are free to be
# names which some other file in the batch is still using.
# Returns "" if all went well and an error message if it did not.  If it did not, everything
# which had already been done is put back the way it was.
def RenameFiles(pairs: list[tuple[str, str]]) -> str:

    # Pass 1: move every file out of the way to a temporary name.
    temps: list[str]=[]
    for old, _ in pairs:
        tmp=old+TempSuffix
        i=0
        while os.path.exists(tmp):
            i+=1
            tmp=f"{old}{TempSuffix}{i}"
        try:
            os.rename(old, tmp)
        except OSError as e:
            PutBack(list(zip(temps, [p[0] for p in pairs])))
            return f"Could not rename {os.path.basename(old)}:\n{e}\n\nNothing was renamed."
        temps.append(tmp)

    # Pass 2: move each of them to its real new name.  Every file of the batch is out of the
    # way under a temporary name by now, so anything sitting at one of these names is a file
    # which has appeared since the batch was looked over -- and it is not to be overwritten.
    done: list[tuple[str, str]]=[]
    for (old, new), tmp in zip(pairs, temps):
        if os.path.exists(new):
            PutBack([(n, o) for o, n in done])
            PutBack(list(zip(temps[len(done):], [p[0] for p in pairs[len(done):]])))
            return (f"{os.path.basename(new)} appeared in {os.path.dirname(new)} while the files were "
                    f"being renamed, and {os.path.basename(old)} would have overwritten it.\n\nNothing was renamed.")
        try:
            os.rename(tmp, new)
        except OSError as e:
            PutBack([(n, o) for o, n in done])
            PutBack(list(zip(temps[len(done):], [p[0] for p in pairs[len(done):]])))
            return f"Could not rename {os.path.basename(old)} to {os.path.basename(new)}:\n{e}\n\nNothing was renamed."
        done.append((old, new))

    return ""


# Look for anything which would make these renames go wrong, and say what it is.  Returns ""
# when there is nothing in the way, and otherwise a line for each conflict, naming the files
# it is about.
# A new name which is the old name of another file in the batch is not a conflict: the
# renaming is done in two passes so that a batch may shuffle its own names about freely.
def ConflictReport(pairs: list[tuple[str, str]]) -> str:
    olds={os.path.normcase(old) for old, _ in pairs}
    conflicts: list[str]=[]

    # The same file supplied twice.  Only the first of the two could be renamed, and the
    # second would be looked for under a name which by then belongs to nothing, stopping the
    # batch part way with an error about a file which cannot be found.
    supplied: dict[str, str]={}
    for old, new in pairs:
        key=os.path.normcase(old)
        if key in supplied:
            conflicts.append(f"{os.path.basename(old)} is in the batch twice, and would have to become "
                             f"both {os.path.basename(supplied[key])} and {os.path.basename(new)}")
        else:
            supplied[key]=new

    # Two files of the batch which would end up with the same name.  One would overwrite
    # the other, and which of them survived would be a matter of luck.
    claimed: dict[str, str]={}
    for old, new in pairs:
        key=os.path.normcase(new)
        if key in claimed:
            conflicts.append(f"{os.path.basename(claimed[key])} and {os.path.basename(old)} "
                             f"would both become {os.path.basename(new)}")
        else:
            claimed[key]=old

    # A name which already belongs to some file which is not part of the batch.
    for old, new in pairs:
        if os.path.exists(new) and os.path.normcase(new) not in olds:
            conflicts.append(f"{os.path.basename(old)} would become {os.path.basename(new)}, "
                             f"which already exists in {os.path.dirname(new)}")

    if len(conflicts) == 0:
        return ""

    shown=conflicts[:6]
    report="\n".join("    "+c for c in shown)
    if len(conflicts) > len(shown):
        report+=f"\n    ...and {len(conflicts)-len(shown)} more"
    return report


# Rename each (from, to) pair, ignoring failures.  This is used only to put back a
# partly-done batch, where there is nothing useful to be done about a failure anyway.
def PutBack(pairs: list[tuple[str, str]]) -> None:
    for frm, to in pairs:
        try:
            os.rename(frm, to)
        except OSError:
            pass


# Files left under the temporary names of pass 1 by a rename which never finished, paired
# with the names they should go back to.  Only the watched folder is looked in, that being
# where a batch is renamed in the ordinary way of things.
def LeftoverTempFiles(folder: str) -> list[tuple[str, str]]:
    try:
        names=os.listdir(folder)
    except OSError:
        return []

    leftovers: list[tuple[str, str]]=[]
    for name in sorted(names):
        stripped=re.sub(re.escape(TempSuffix)+r"\d*$", "", name)
        if stripped != name and os.path.isfile(os.path.join(folder, name)):
            leftovers.append((os.path.join(folder, name), os.path.join(folder, stripped)))
    return leftovers


# Is this file name scanner output: the scanner's own prefix, optionally followed by an
# underscore and digits, with a scan extension?  With no prefix supplied, nothing is.
def IsScannerFileName(name: str, prefix: str) -> bool:
    if len(prefix) == 0:
        return False
    return re.fullmatch(re.escape(prefix)+r"(_\d+)?"+ScanExtensions, name, re.IGNORECASE) is not None


# Everything in the watched folder which is scanner output, in the order the scanner made it.
def ScannerFilesIn(folder: str, prefix: str) -> list[str]:
    try:
        names=os.listdir(folder)
    except OSError:
        return []       # The folder has gone away or is unreadable: nothing to pick up

    paths=[os.path.join(folder, n) for n in names if IsScannerFileName(n, prefix)]
    return SortByName([p for p in paths if os.path.isfile(p)])


# What a file name is sorted on: everything but a numeric suffix compared as text, and the
# numeric suffix compared as a number.  So "page10" follows "page9" instead of falling
# between "page1" and "page2", which is how a scanner numbering without padding writes its
# pages, and how anything else counting in its file names does too.
# A name with no numeric suffix comes before the numbered ones sharing its text -- "z-.jpg",
# the scanner's own name for a first page, ahead of "z-_1.jpg" and the rest.
# Files in different folders are grouped by folder first.
def NameKey(path: str) -> tuple:
    folder, name=os.path.split(path)
    stem, ext=os.path.splitext(name)
    digits=re.search(r"\d+$", stem)
    text=stem[:digits.start()] if digits else stem
    return (os.path.normcase(folder), os.path.normcase(text),
            int(digits.group()) if digits else -1, os.path.normcase(ext))


def SortByName(paths: list[str]) -> list[str]:
    return sorted(paths, key=NameKey)


# Is this list of paths in that order already?
def IsInNameOrder(paths: list[str]) -> bool:
    keys=[NameKey(p) for p in paths]
    return keys == sorted(keys)


# Turn a list of paths into a list of (old, new) pairs.  The sequence number gets just as
# many digits as the batch needs and each file keeps its own extension.
# A name and a number which is not there yet is simply left out, so that a half-typed name
# can be shown as it is built up.  (Renaming needs both of them, so nothing can actually be
# renamed to one of these partial names.)
def BuildNewNames(paths: list[str], title: str, number: str) -> list[tuple[str, str]]:
    width=len(str(len(paths)))
    supplied=[s for s in (title, number) if len(s) > 0]
    pairs: list[tuple[str, str]]=[]
    for i, old in enumerate(paths):
        _, ext=os.path.splitext(old)
        stem=" ".join(supplied+[f"p{i+1:0{width}d}"])
        new=os.path.join(os.path.dirname(old), stem+ext)
        pairs.append((old, new))
    return pairs


# What was supplied by hand comes to this first: a dropped folder stands for the files
# directly inside it, in name order, and anything which is neither a file nor a folder is
# passed over.
def ExpandSupplied(paths: list[str]) -> list[str]:
    files: list[str]=[]
    for path in paths:
        if os.path.isdir(path):
            try:
                inside=[os.path.join(path, n) for n in os.listdir(path)]
            except OSError:
                continue
            files.extend(SortByName([p for p in inside if os.path.isfile(p)]))
        elif os.path.isfile(path):
            files.append(path)
    return files


# Accepts files dropped on the window and hands them to the frame.
class ScanRenamerDropTarget(wx.FileDropTarget):
    def __init__(self, frame: "ScanRenamerFrame") -> None:
        wx.FileDropTarget.__init__(self)
        self.Frame=frame

    def OnDropFiles(self, x, y, filenames) -> bool:
        self.Frame.SetSuppliedFiles(list(filenames))
        return True


class ScanRenamerFrame(wx.Frame):
    def __init__(self) -> None:
        wx.Frame.__init__(self, None, title="ScanRenamer", size=wx.Size(760, 520))

        self.State=ReadState()
        self.Files: list[str]=[]

        # The watched folder and the scanner's prefix, and whether the files now in the batch
        # came from the watcher.  Files supplied by hand take the batch over: the watcher
        # leaves them alone until the batch is empty again.
        self.SizingColumns=False        # Guards against SizeColumns setting itself off again
        self.LastListWidth=-1           # The width the columns were last sized to fit

        settings=ReadSettings()
        self.WatchFolder=settings.get("watch folder", "")
        self.ScanPrefix=settings.get("scan prefix", "")
        self.FilesFromWatcher=False

        panel=wx.Panel(self)
        sizer=wx.BoxSizer(wx.VERTICAL)

        sizer.Add(wx.StaticText(panel, label="Drop the files to be renamed here, or use Select Files..."), 0, wx.ALL, 5)

        self.bSelect=wx.Button(panel, label="Select Files...")
        sizer.Add(self.bSelect, 0, wx.ALL, 5)

        # The batch: each supplied file on the left, the name it would be renamed to on the
        # right.  The two are columns of one list control, so they cannot scroll apart.
        self.lcFiles=wx.ListCtrl(panel, style=wx.LC_REPORT|wx.LC_SINGLE_SEL)
        self.lcFiles.InsertColumn(0, "File")
        self.lcFiles.InsertColumn(1, "Renamed to")
        sizer.Add(self.lcFiles, 1, wx.EXPAND|wx.ALL, 5)

        grid=wx.FlexGridSizer(2, 2, 5, 5)
        grid.AddGrowableCol(1)
        grid.Add(wx.StaticText(panel, label="Name:"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.tTitle=wx.TextCtrl(panel, value=self.State["Title"])
        grid.Add(self.tTitle, 1, wx.EXPAND)
        grid.Add(wx.StaticText(panel, label="Number:"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.tNumber=wx.TextCtrl(panel)
        grid.Add(self.tNumber, 1, wx.EXPAND)
        sizer.Add(grid, 0, wx.EXPAND|wx.ALL, 5)

        self.stStatus=wx.StaticText(panel, label="")
        sizer.Add(self.stStatus, 0, wx.ALL, 5)

        self.stWatching=wx.StaticText(panel, label=self.WatchingMessage())
        sizer.Add(self.stWatching, 0, wx.ALL, 5)

        buttons=wx.BoxSizer(wx.HORIZONTAL)
        self.bRename=wx.Button(panel, label="Rename")
        buttons.Add(self.bRename, 0, wx.ALL, 5)
        self.bUndo=wx.Button(panel, label="Undo Last Rename")
        buttons.Add(self.bUndo, 0, wx.ALL, 5)
        buttons.AddStretchSpacer()
        self.bExit=wx.Button(panel, label="Exit")
        buttons.Add(self.bExit, 0, wx.ALL, 5)
        sizer.Add(buttons, 0, wx.EXPAND)

        panel.SetSizer(sizer)

        # Files may be dropped anywhere on the window.  The list fills most of it and would
        # otherwise swallow the drops itself, so it gets a drop target of its own.
        panel.SetDropTarget(ScanRenamerDropTarget(self))
        self.lcFiles.SetDropTarget(ScanRenamerDropTarget(self))

        self.lcFiles.Bind(wx.EVT_SIZE, self.OnListResized)
        self.tTitle.Bind(wx.EVT_TEXT, self.OnNameOrNumberChanged)
        self.tNumber.Bind(wx.EVT_TEXT, self.OnNameOrNumberChanged)
        self.bSelect.Bind(wx.EVT_BUTTON, self.OnSelect)
        self.bRename.Bind(wx.EVT_BUTTON, self.OnRename)
        self.bUndo.Bind(wx.EVT_BUTTON, self.OnUndo)
        self.bExit.Bind(wx.EVT_BUTTON, self.OnExit)
        self.Bind(wx.EVT_CLOSE, self.OnClose)

        # Watch the folder, if there is one, for scans to add to the batch.
        self.Timer=wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.OnTimer, self.Timer)
        if self.Watching():
            self.Timer.Start(WatchInterval)
            self.OnTimer(None)      # Pick up whatever is already there without waiting a tick

        self.UpdateControls()
        self.Centre()

        # Ask about anything a half-done rename left behind, once the window is up to ask in
        # front of.
        if len(self.WatchFolder) > 0:
            wx.CallAfter(self.CheckForLeftovers)


    # A rename which was interrupted -- the program killed, the machine losing power -- leaves
    # the files it had moved out of the way under temporary names.  Nothing else will ever
    # pick them up, and the folder looks empty of scans, so they are offered back at startup.
    def CheckForLeftovers(self) -> None:
        leftovers=LeftoverTempFiles(self.WatchFolder)
        if len(leftovers) == 0:
            return

        names="\n".join("    "+os.path.basename(new) for _, new in leftovers[:6])
        if len(leftovers) > 6:
            names+=f"\n    ...and {len(leftovers)-6} more"
        answer=wx.MessageBox(f"{len(leftovers)} files in {self.WatchFolder} were left behind by a rename "
                             f"which did not finish.\n\nPut them back under their own names?\n\n{names}",
                             "ScanRenamer", wx.YES_NO|wx.ICON_QUESTION)
        if answer != wx.YES:
            return

        report=ConflictReport(leftovers)
        if report != "":
            wx.MessageBox(f"They cannot be put back as things stand:\n\n{report}\n\nNothing was put back.",
                          "ScanRenamer", wx.OK|wx.ICON_ERROR)
            return

        msg=RenameFiles(leftovers)
        if msg != "":
            wx.MessageBox(msg, "ScanRenamer", wx.OK|wx.ICON_ERROR)
            return

        self.stStatus.SetLabel(f"Put back {len(leftovers)} files left over from an unfinished rename.")
        self.OnTimer(None)      # They may well be scans the watcher wants


    # Watching needs both a folder to watch and the prefix to watch for.
    def Watching(self) -> bool:
        return len(self.WatchFolder) > 0 and len(self.ScanPrefix) > 0


    def WatchingMessage(self) -> str:
        if len(self.WatchFolder) == 0:
            return f"Not watching a folder.  (Add a 'Watch Folder=' line to {SettingsFileName}.)"
        if len(self.ScanPrefix) == 0:
            return f"Not watching a folder.  (Add a 'Scan Prefix=' line to {SettingsFileName}.)"
        if not os.path.isdir(self.WatchFolder):
            return f"Watch Folder '{self.WatchFolder}' does not exist."
        return f"Watching {self.WatchFolder} for {self.ScanPrefix}*.jpg"


    # Files supplied by hand, dropped or chosen.  A batch which comes to nothing -- an empty
    # folder dropped, say -- is said so rather than silently doing nothing at all.
    def SetSuppliedFiles(self, paths: list[str]) -> None:
        files=ExpandSupplied(paths)
        if len(files) == 0:
            wx.MessageBox("There are no files there to rename.", "ScanRenamer", wx.OK|wx.ICON_INFORMATION)
            return
        self.SetFiles(files)


    # The files supplied for this batch, in the order in which they were supplied.
    def SetFiles(self, paths: list[str], fromWatcher: bool=False) -> None:
        self.Files=[p for p in paths if os.path.isfile(p)]
        self.FilesFromWatcher=fromWatcher and len(self.Files) > 0

        self.lcFiles.DeleteAllItems()
        for i, path in enumerate(self.Files):
            self.lcFiles.InsertItem(i, os.path.basename(path))
        self.UpdateProposedNames()

        self.stStatus.SetLabel("")
        self.UpdateControls()


    # The names the files would be renamed to, as things stand -- which is shown from the
    # first character typed, with whatever part of the name has been supplied so far.
    def ProposedNames(self) -> list[str]:
        title=self.tTitle.GetValue().strip()
        number=self.tNumber.GetValue().strip()
        names=[os.path.basename(new) for _, new in BuildNewNames(self.Files, title, number)]

        # With nothing typed at all there is only the page numbering to show, and it is
        # spaced out as "p 01.jpg" to look like the placeholder it is.  The moment anything
        # is typed the space goes and the names are the real ones.
        if len(title) == 0 and len(number) == 0:
            names=[f"p {n[1:]}" for n in names]
        return names


    # Show the proposed names in the right-hand column.
    def UpdateProposedNames(self) -> None:
        for i, new in enumerate(self.ProposedNames()):
            self.lcFiles.SetItem(i, 1, new)
        self.SizeColumns()


    # Each column is wide enough for what is in it, with a gap between the two of them, and
    # the right-hand one then takes up whatever room is left over, so that the display looks
    # like the two halves it is.
    def SizeColumns(self) -> None:
        # Setting a column width can itself provoke a size event, and this is called from
        # one: without the guard the two would chase each other round and round.
        if self.SizingColumns:
            return
        self.SizingColumns=True
        try:
            autosize=wx.LIST_AUTOSIZE if self.lcFiles.GetItemCount() > 0 else wx.LIST_AUTOSIZE_USEHEADER
            self.lcFiles.SetColumnWidth(0, autosize)
            self.lcFiles.SetColumnWidth(0, self.lcFiles.GetColumnWidth(0)+self.FromDIP(ColumnGap))
            self.lcFiles.SetColumnWidth(1, autosize)

            # Stop short of the full width.  Filling it exactly brings up a horizontal
            # scrollbar, and a scrollbar which appears and disappears again is another way
            # for this to chase its own tail.
            room=self.lcFiles.GetClientSize().width-self.FromDIP(ColumnGap)
            slack=room-self.lcFiles.GetColumnWidth(0)-self.lcFiles.GetColumnWidth(1)
            if slack > 0:
                self.lcFiles.SetColumnWidth(1, self.lcFiles.GetColumnWidth(1)+slack)

            # Remember the width these columns were sized for.  Recording it here, at the end
            # of the outermost pass, means a size event carrying a width we have not actually
            # sized for is never taken for one we have.
            self.LastListWidth=self.lcFiles.GetClientSize().width
        finally:
            self.SizingColumns=False


    def OnNameOrNumberChanged(self, event) -> None:
        self.UpdateProposedNames()


    # Widening the window widens the right-hand half with it.  Size events which leave the
    # width alone -- and the ones setting a column width provokes are all of that kind --
    # are ignored, so that resizing the columns cannot start the whole thing over again.
    # The sizing is put off until the event has been dealt with: during the event the control
    # may not have taken up its new width yet, and sizing the columns to the old one would
    # leave them wrong with no further event coming to put them right.
    def OnListResized(self, event) -> None:
        if self.lcFiles.GetClientSize().width != self.LastListWidth:
            wx.CallAfter(self.SizeColumns)
        event.Skip()


    # Look at the watched folder.  Scans there fill an empty batch and go on being added to
    # it as they are made, up until Rename -- but files supplied by hand are never disturbed.
    def OnTimer(self, event) -> None:
        if len(self.Files) > 0 and not self.FilesFromWatcher:
            return

        files=ScannerFilesIn(self.WatchFolder, self.ScanPrefix)
        if files != self.Files:
            self.SetFiles(files, fromWatcher=True)


    def UpdateControls(self) -> None:
        self.bRename.Enable(len(self.Files) > 0)
        self.bUndo.Enable(len(self.State["Batches"]) > 0)


    def OnSelect(self, event) -> None:
        with wx.FileDialog(self, "Select the files to be renamed", wildcard="All files (*.*)|*.*",
                           style=wx.FD_OPEN|wx.FD_MULTIPLE|wx.FD_FILE_MUST_EXIST) as dlg:
            if dlg.ShowModal() == wx.ID_CANCEL:
                return
            self.SetSuppliedFiles(dlg.GetPaths())


    def OnRename(self, event) -> None:
        title=self.tTitle.GetValue().strip()
        number=self.tNumber.GetValue().strip()

        if len(self.Files) == 0:
            wx.MessageBox("There are no files to rename.", "ScanRenamer", wx.OK|wx.ICON_INFORMATION)
            return
        if title == "":
            wx.MessageBox("You must supply a name.", "ScanRenamer", wx.OK|wx.ICON_INFORMATION)
            return
        if number == "":
            wx.MessageBox("You must supply a number.", "ScanRenamer", wx.OK|wx.ICON_INFORMATION)
            return
        bad=[c for c in IllegalCharacters if c in title+number]
        if len(bad) > 0:
            wx.MessageBox(f"The name and number may not contain {' '.join(bad)}", "ScanRenamer", wx.OK|wx.ICON_INFORMATION)
            return

        # The files are numbered in the order in which they were supplied.  If that is not
        # name order, the user needs to know about it and to say what to do.
        # Files from the watcher are not asked about: they are already in the order the
        # scanner made them, which is name order and is the order wanted.
        files=self.Files
        if not self.FilesFromWatcher and not IsInNameOrder(files):
            dlg=wx.MessageDialog(self, "These files are not in name order.\n\n"
                                       "Sort by name:  sort them and number them in that order.  Names are "
                                       "compared as text except for a number at the end, which is compared "
                                       "as a number, so page10 follows page9.\n"
                                       "Keep as supplied:  number them in the order they were supplied.",
                                 "ScanRenamer", wx.YES_NO|wx.CANCEL|wx.ICON_QUESTION)
            dlg.SetYesNoCancelLabels("Sort by name", "Keep as supplied", "Cancel")
            answer=dlg.ShowModal()
            dlg.Destroy()
            if answer == wx.ID_CANCEL:
                return
            if answer == wx.ID_YES:
                files=SortByName(files)

        pairs=BuildNewNames(files, title, number)

        # A renamed file must never look like fresh scanner output, or the watcher would pick
        # it straight back up and rename it again.
        looksScanned=[n for _, n in pairs if IsScannerFileName(os.path.basename(n), self.ScanPrefix)]
        if len(looksScanned) > 0:
            wx.MessageBox(f"{os.path.basename(looksScanned[0])} would look like a new scan, and would be "
                          f"picked up again by the folder watcher.\n\nNothing was renamed.",
                          "ScanRenamer", wx.OK|wx.ICON_ERROR)
            return

        # Nothing is ever renamed over the top of an existing file.
        report=ConflictReport(pairs)
        if report != "":
            wx.MessageBox(f"The batch cannot be renamed as it stands:\n\n{report}\n\nNothing was renamed.",
                          "ScanRenamer", wx.OK|wx.ICON_ERROR)
            return

        msg=RenameFiles(pairs)
        if msg != "":
            wx.MessageBox(msg, "ScanRenamer", wx.OK|wx.ICON_ERROR)
            return

        # Remember the batch so that it can be undone, keep the name for the next batch and
        # blank the number, which will always be different next time.
        self.State["Title"]=title
        self.State["Batches"].append({"When": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                      "Title": title,
                                      "Number": number,
                                      "Renames": [[o, n] for o, n in pairs]})
        self.State["Batches"]=self.State["Batches"][-MaxBatchesKept:]
        WriteState(self.State)

        self.tNumber.SetValue("")
        self.SetFiles([])
        self.stStatus.SetLabel(f"Renamed {len(pairs)} files.")


    def OnUndo(self, event) -> None:
        if len(self.State["Batches"]) == 0:
            return

        batch=self.State["Batches"][-1]
        pairs=[(n, o) for o, n in batch["Renames"]]

        missing=[n for n, _ in pairs if not os.path.exists(n)]
        if len(missing) > 0:
            wx.MessageBox(f"{os.path.basename(missing[0])} is no longer there, so the rename of "
                          f"{batch['When']} cannot be undone.", "ScanRenamer", wx.OK|wx.ICON_ERROR)
            return

        # Nor does putting a batch back overwrite anything -- a scan made since the rename may
        # well have been given one of the names the batch is about to go back to.
        report=ConflictReport(pairs)
        if report != "":
            wx.MessageBox(f"The files cannot be put back as things stand:\n\n{report}\n\n"
                          f"Nothing was put back.", "ScanRenamer", wx.OK|wx.ICON_ERROR)
            return

        msg=RenameFiles(pairs)
        if msg != "":
            wx.MessageBox(msg, "ScanRenamer", wx.OK|wx.ICON_ERROR)
            return

        self.State["Batches"].pop()
        WriteState(self.State)

        # Renaming blanks the number.  Undoing the rename puts it back, so that the batch just
        # undone can be done again with whatever needed correcting.  Anything typed in the
        # meantime is left alone -- this fills the boxes in, it never overwrites them.
        if len(self.tNumber.GetValue().strip()) == 0:
            self.tNumber.SetValue(batch.get("Number", ""))
        if len(self.tTitle.GetValue().strip()) == 0:
            self.tTitle.SetValue(batch.get("Title", ""))

        self.stStatus.SetLabel(f"Undid the rename of {len(pairs)} files.")
        self.UpdateControls()


    def OnExit(self, event) -> None:
        self.Close()


    # Stop looking at the watched folder before the window goes away, so that no timer tick
    # arrives at a half-destroyed frame.
    def OnClose(self, event) -> None:
        self.Timer.Stop()
        event.Skip()


def main() -> None:
    app=wx.App(False)
    frame=ScanRenamerFrame()
    frame.Show()
    app.MainLoop()
    sys.exit()


if __name__ == "__main__":
    main()
