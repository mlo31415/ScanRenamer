# ScanRenamer

Renames a batch of scanned files, in place, to the standard form

    XXX num pnnn.ext

* **XXX** -- a name typed into the dialog (e.g. a fanzine or convention publication title)
* **num** -- an issue number/letter combination, also typed into the dialog
* **p** -- a literal "p"
* **nnn** -- a sequence number starting at 1 and increasing by one, in the order the files
  were supplied.  It is padded to just as many digits as the batch needs: `p1`...`p9` for a
  batch of nine, `p01`...`p12` for a batch of twelve, `p001`...`p150` for a batch of a
  hundred and fifty.

Each file keeps its own extension.

## Using it

Supply the files in any of three ways: drop them on the window, choose them with **Select
Files...**, or let ScanRenamer pick them up from a watched folder (below).  A dropped folder
stands for the files directly inside it, in alphabetical order; dropping something with no
files in it says so rather than appearing to do nothing.

The batch is shown two columns wide: each file on the left, and on the right the name it
would be renamed to.  They are the two columns of a single list, so they scroll as one and
cannot drift apart.

The proposed names are regenerated at every keystroke, from the first character typed.
Whichever of the name and the number has not been filled in yet is left out of them, so
typing just `Spaceways` shows `Spaceways p01.jpg` and the number slots itself in as it is
typed.  With neither filled in there is only the page numbering to show, and it appears as
`p 01.jpg`, `p 02.jpg`... -- spaced out to look like the placeholder it is.  Renaming still
needs both.

The order in which the files are supplied is the order in which they are numbered.  If that
order is not alphabetical, ScanRenamer says so and offers a choice of sorting them
alphabetically, numbering them as supplied, or cancelling.  Choosing to sort renumbers them,
so the names actually given are not the ones the right-hand column was showing.

Files from the watched folder are not asked about.  They arrive in the order the scanner made
them: sorted by the number in the name read *as a number*, with the unnumbered first page
ahead of them all.  That matters if the scanner is ever set to number without padding, where
sorting by name would put `z-_10.jpg` between `z-_1.jpg` and `z-_2.jpg` and silently number
the pages in that order.

Type the name and the number and press **Rename**.  The name is kept for the next batch (and
for the next run of the program); the number is blanked, since it is always different.

**Undo Last Rename** puts the most recent batch back the way it was.  **Exit** closes the
program.

## Nothing is ever overwritten

A rename never writes over an existing file.  Before anything is renamed, ScanRenamer looks
for two kinds of trouble:

* a file which would land on a name already belonging to a file which is not part of the
  batch, and
* two files of the batch which would end up with the same name.

Either one is reported, naming both the file being renamed and the file standing in its way
(with the folder it is in), and the whole batch is left exactly as it was -- it is never a
matter of some files being renamed and others not.

Undo is protected the same way: a scan made since the rename may well have been given one of
the names the batch is about to go back to, and if so nothing is put back.

Renaming a batch to names it is already using is fine, and so is any shuffling of names
within a batch -- the renaming is done in two passes for exactly that reason.  As a last
guard, if a file appears at one of the new names while the batch is being renamed, the
renaming stops and everything already done is put back.

## The watched folder

`ScanRenamer settings.txt`, in the program's directory, names the folder to watch and the
prefix the scanner gives its files:

    Watch Folder=C:\Users\mlo\Documents\usr\Scanning
    Scan Prefix=z-

A path may be quoted or not, as you please.  The lines are read when ScanRenamer starts, so
change them with the program shut down.  Watching needs both of them: with either line
missing -- or its value commented out, `Watch Folder=#...` -- nothing is watched for, and the
window says so.

So long as nothing has been supplied by hand, every file in that folder named `{prefix}.jpg`
or `{prefix}_nnn.jpg` (`.jpeg` counts too, and case is ignored) is loaded into the batch in
alphabetical order, and pages go on being added to the list as they are scanned, up until
**Rename** is pressed.  With the settings above that means `z-.jpg`, `z-_001.jpg`,
`z-_002.jpg`... and nothing else in the folder.  Files supplied by hand take the batch over;
the watcher leaves them alone until the batch is empty again.

A rename which would produce a scanner-looking name is refused rather than done, so a renamed
file can never be picked back up by the watcher.

The watcher does not wait for the scanner to finish writing a page, so a file can appear in
the list a moment before it is complete.  Press **Rename** when the scanning is done: a file
the scanner still has open cannot be renamed, and the whole batch would be rolled back.

## ScanRenamer state.json

The retained name and a table of every batch renamed -- when it was done, the name and number
it was renamed with, and each old-name/new-name pair -- are kept in `ScanRenamer state.json`
in the program's directory.  Undo works off the last entry in that table and removes it when
it succeeds.  The file is per-installation and is not in the repository.

Because renaming blanks the number, undoing a rename puts that batch's number (and its name,
if the box has since been emptied) back into the dialog, so the batch can be done again with
whatever needed correcting.  A number typed since the rename is left alone -- undo fills the
boxes in, it never overwrites them.

The file is saved by writing a new one and putting it in the old one's place, so that being
stopped half way through cannot leave a wrecked file where the table of renames used to be.
A state file which cannot be read is renamed to `ScanRenamer state (damaged ...).json` and
reported, rather than being quietly written over -- it is the only record of what was renamed
to what, and an undo can be done by hand from it.

## If a rename is interrupted

Renaming moves every file of a batch to a temporary name ending in `.ScanRenamerTmp` before
giving it its real one.  If the program is killed, or the machine loses power, between those
two steps, the files are left under those temporary names -- invisible to the watcher and to
everything else.  ScanRenamer looks for them in the watched folder when it starts and offers
to put them back under their own names; it will not put one back over the top of a file which
has since taken its name.

## Running it

wxPython is the only requirement:

    pip install -r requirements.txt
    python ScanRenamer.py
