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

Files are supplied either by dropping them on the window or with the Select
Files... button.  The order in which they are supplied is the order in which they
are numbered; if that order is not alphabetical the user is warned and gets to
choose between sorting them and keeping them as they came.

The title string is remembered from batch to batch (and from run to run); the
number is cleared after each successful batch, since it always changes.

Every batch is written to "ScanRenamer state.json" alongside this program as a
table of old-name/new-name pairs, and Undo Last Rename puts the most recent batch
back the way it was.
"""

import json
import os
import sys
from datetime import datetime

import wx

# The persistent state: the retained title string and the table of renames done so far.
StateFileName="ScanRenamer state.json"

# Characters which Windows will not accept in a file name.
IllegalCharacters='\\/:*?"<>|'


# The full path of the state file, which lives in the program's own directory.
def StateFilePath() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), StateFileName)


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
        wx.Frame.__init__(self, None, title="ScanRenamer", size=wx.Size(460, 480))

        self.State=ReadState()
        self.Files: list[str]=[]

        panel=wx.Panel(self)
        sizer=wx.BoxSizer(wx.VERTICAL)

        sizer.Add(wx.StaticText(panel, label="Drop the files to be renamed here, or use Select Files..."), 0, wx.ALL, 5)

        self.bSelect=wx.Button(panel, label="Select Files...")
        sizer.Add(self.bSelect, 0, wx.ALL, 5)

        self.lbFiles=wx.ListBox(panel, style=wx.LB_SINGLE)
        sizer.Add(self.lbFiles, 1, wx.EXPAND|wx.ALL, 5)

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
        panel.SetDropTarget(ScanRenamerDropTarget(self))

        self.bSelect.Bind(wx.EVT_BUTTON, self.OnSelect)
        self.bRename.Bind(wx.EVT_BUTTON, self.OnRename)
        self.bUndo.Bind(wx.EVT_BUTTON, self.OnUndo)
        self.bExit.Bind(wx.EVT_BUTTON, self.OnExit)

        self.UpdateControls()
        self.Centre()


    # The files supplied for this batch, in the order in which they were supplied.
    def SetFiles(self, paths: list[str]) -> None:
        self.Files=[p for p in paths if os.path.isfile(p)]
        self.lbFiles.Set([os.path.basename(p) for p in self.Files])
        self.stStatus.SetLabel("")
        self.UpdateControls()


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


def main() -> None:
    app=wx.App(False)
    frame=ScanRenamerFrame()
    frame.Show()
    app.MainLoop()
    sys.exit()


if __name__ == "__main__":
    main()
