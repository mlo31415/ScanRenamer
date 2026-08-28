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

    * dropped on the window
    * chosen with the Select Files... button
    * picked up from a watched folder

The batch is shown two columns wide -- each file on the left and the name it
would be renamed to on the right, the two being columns of one list so that they
cannot scroll apart.  The proposed names follow the name and number as they are
typed.

The order in which they are supplied is the order in which they are numbered; if
that order is not alphabetical the user is warned and gets to choose between
sorting them and keeping them as they came.  (Files from the watched folder are
always in alphabetical order, so the question never arises for them.)

The folder to watch and the prefix the scanner names its files with come from the
"Watch Folder=" and "Scan Prefix=" lines of "ScanRenamer settings.txt" in the
program's directory, which is read when the program starts; watching needs both
of them.  While no files have been supplied by hand, every file in that folder
named "{prefix}.jpg" or "{prefix}_nnn.jpg" (.jpeg counts too) is loaded into the
batch in alphabetical order, and the list is kept up to date as more pages are
scanned, until Rename is pressed.  A rename which would produce a name that
looks like scanner output is refused, so that the watcher can never pick a
renamed file back up.

The title string is remembered from batch to batch (and from run to run); the
number is cleared after each successful batch, since it always changes.

Every batch is written to "ScanRenamer state.json" alongside this program as a
table of old-name/new-name pairs, and Undo Last Rename puts the most recent batch
back the way it was.
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

# How often the watched folder is looked at, in milliseconds.
WatchInterval=1000


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


# Read the saved state.  A missing or damaged state file is not an error: we just start clean.
def ReadState() -> dict:
    try:
        with open(StateFilePath(), "r", encoding="utf-8") as f:
            state=json.load(f)
    except (OSError, json.JSONDecodeError):
        return {"Title": "", "Batches": []}

    if "Title" not in state:
        state["Title"]=""
    if "Batches" not in state:
        state["Batches"]=[]
    return state


def WriteState(state: dict) -> None:
    try:
        with open(StateFilePath(), "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
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
        tmp=old+".ScanRenamerTmp"
        i=0
        while os.path.exists(tmp):
            i+=1
            tmp=f"{old}.ScanRenamerTmp{i}"
        try:
            os.rename(old, tmp)
        except OSError as e:
            PutBack(list(zip(temps, [p[0] for p in pairs])))
            return f"Could not rename {os.path.basename(old)}:\n{e}\n\nNothing was renamed."
        temps.append(tmp)

    # Pass 2: move each of them to its real new name.
    done: list[tuple[str, str]]=[]
    for (old, new), tmp in zip(pairs, temps):
        try:
            os.rename(tmp, new)
        except OSError as e:
            PutBack([(n, o) for o, n in done])
            PutBack(list(zip(temps[len(done):], [p[0] for p in pairs[len(done):]])))
            return f"Could not rename {os.path.basename(old)} to {os.path.basename(new)}:\n{e}\n\nNothing was renamed."
        done.append((old, new))

    return ""


# Rename each (from, to) pair, ignoring failures.  This is used only to put back a
# partly-done batch, where there is nothing useful to be done about a failure anyway.
def PutBack(pairs: list[tuple[str, str]]) -> None:
    for frm, to in pairs:
        try:
            os.rename(frm, to)
        except OSError:
            pass


# Is this file name scanner output: the scanner's own prefix, optionally followed by an
# underscore and digits, with a scan extension?  With no prefix supplied, nothing is.
def IsScannerFileName(name: str, prefix: str) -> bool:
    if len(prefix) == 0:
        return False
    return re.fullmatch(re.escape(prefix)+r"(_\d+)?"+ScanExtensions, name, re.IGNORECASE) is not None


# Everything in the watched folder which is scanner output, in alphabetical order.
def ScannerFilesIn(folder: str, prefix: str) -> list[str]:
    try:
        names=os.listdir(folder)
    except OSError:
        return []       # The folder has gone away or is unreadable: nothing to pick up

    paths=[os.path.join(folder, n) for n in names if IsScannerFileName(n, prefix)]
    return Alphabetize([p for p in paths if os.path.isfile(p)])


# Is this list of paths in alphabetical order?
def IsAlphabetical(paths: list[str]) -> bool:
    keys=[os.path.normcase(p) for p in paths]
    return keys == sorted(keys)


def Alphabetize(paths: list[str]) -> list[str]:
    return sorted(paths, key=os.path.normcase)


# Turn a list of paths into a list of (old, new) pairs.  The sequence number gets just as
# many digits as the batch needs and each file keeps its own extension.
def BuildNewNames(paths: list[str], title: str, number: str) -> list[tuple[str, str]]:
    width=len(str(len(paths)))
    pairs: list[tuple[str, str]]=[]
    for i, old in enumerate(paths):
        _, ext=os.path.splitext(old)
        new=os.path.join(os.path.dirname(old), f"{title} {number} p{i+1:0{width}d}{ext}")
        pairs.append((old, new))
    return pairs


# Accepts files dropped on the window and hands them to the frame.
class ScanRenamerDropTarget(wx.FileDropTarget):
    def __init__(self, frame: "ScanRenamerFrame") -> None:
        wx.FileDropTarget.__init__(self)
        self.Frame=frame

    def OnDropFiles(self, x, y, filenames) -> bool:
        self.Frame.SetFiles(list(filenames))
        return True


class ScanRenamerFrame(wx.Frame):
    def __init__(self) -> None:
        wx.Frame.__init__(self, None, title="ScanRenamer", size=wx.Size(760, 520))

        self.State=ReadState()
        self.Files: list[str]=[]

        # The watched folder and the scanner's prefix, and whether the files now in the batch
        # came from the watcher.  Files supplied by hand take the batch over: the watcher
        # leaves them alone until the batch is empty again.
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


    # The names the files would be renamed to, as things stand.  While the name and number
    # are not both filled in there is nothing to propose.
    def ProposedNames(self) -> list[str]:
        title=self.tTitle.GetValue().strip()
        number=self.tNumber.GetValue().strip()
        if len(title) == 0 or len(number) == 0:
            return [""]*len(self.Files)
        return [os.path.basename(new) for _, new in BuildNewNames(self.Files, title, number)]


    # Show the proposed names in the right-hand column.
    def UpdateProposedNames(self) -> None:
        for i, new in enumerate(self.ProposedNames()):
            self.lcFiles.SetItem(i, 1, new)
        self.SizeColumns()


    # Each column is wide enough for what is in it, and the right-hand one then takes up
    # whatever room is left over, so that the display looks like the two halves it is.
    def SizeColumns(self) -> None:
        autosize=wx.LIST_AUTOSIZE if self.lcFiles.GetItemCount() > 0 else wx.LIST_AUTOSIZE_USEHEADER
        self.lcFiles.SetColumnWidth(0, autosize)
        self.lcFiles.SetColumnWidth(1, autosize)

        slack=self.lcFiles.GetClientSize().width-self.lcFiles.GetColumnWidth(0)-self.lcFiles.GetColumnWidth(1)
        if slack > 0:
            self.lcFiles.SetColumnWidth(1, self.lcFiles.GetColumnWidth(1)+slack)


    def OnNameOrNumberChanged(self, event) -> None:
        self.UpdateProposedNames()


    # Widening the window widens the right-hand half with it.
    def OnListResized(self, event) -> None:
        self.SizeColumns()
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
            self.SetFiles(dlg.GetPaths())


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
        # alphabetical order, the user needs to know about it and to say what to do.
        files=self.Files
        if not IsAlphabetical(files):
            dlg=wx.MessageDialog(self, "These files are not in alphabetical order.\n\n"
                                       "Sort alphabetically:  sort them and number them in that order.\n"
                                       "Keep as supplied:  number them in the order they were supplied.",
                                 "ScanRenamer", wx.YES_NO|wx.CANCEL|wx.ICON_QUESTION)
            dlg.SetYesNoCancelLabels("Sort alphabetically", "Keep as supplied", "Cancel")
            answer=dlg.ShowModal()
            dlg.Destroy()
            if answer == wx.ID_CANCEL:
                return
            if answer == wx.ID_YES:
                files=Alphabetize(files)

        pairs=BuildNewNames(files, title, number)

        # A renamed file must never look like fresh scanner output, or the watcher would pick
        # it straight back up and rename it again.
        looksScanned=[n for _, n in pairs if IsScannerFileName(os.path.basename(n), self.ScanPrefix)]
        if len(looksScanned) > 0:
            wx.MessageBox(f"{os.path.basename(looksScanned[0])} would look like a new scan, and would be "
                          f"picked up again by the folder watcher.\n\nNothing was renamed.",
                          "ScanRenamer", wx.OK|wx.ICON_ERROR)
            return

        # A new name may be the old name of another file in the batch (the renaming is done in
        # two passes so that that works), but it may not be the name of a file outside the batch.
        olds={os.path.normcase(o) for o, _ in pairs}
        blocked=[n for _, n in pairs if os.path.exists(n) and os.path.normcase(n) not in olds]
        if len(blocked) > 0:
            wx.MessageBox(f"{os.path.basename(blocked[0])} already exists.\n\nNothing was renamed.",
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
                                      "Renames": [[o, n] for o, n in pairs]})
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

        msg=RenameFiles(pairs)
        if msg != "":
            wx.MessageBox(msg, "ScanRenamer", wx.OK|wx.ICON_ERROR)
            return

        self.State["Batches"].pop()
        WriteState(self.State)

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
