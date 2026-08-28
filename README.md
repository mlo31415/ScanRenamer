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
Files...**, or let ScanRenamer pick them up from a watched folder (below).

The batch is shown two columns wide: each file on the left, and on the right the name it
would be renamed to, which follows the name and number as they are typed.  They are the two
columns of a single list, so they scroll as one and cannot drift apart.

The order in which the files are supplied is the order in which they are numbered.  If that
order is not alphabetical, ScanRenamer says so and offers a choice of sorting them
alphabetically, numbering them as supplied, or cancelling.  Choosing to sort renumbers them,
so the names actually given are not the ones the right-hand column was showing.

Type the name and the number and press **Rename**.  The name is kept for the next batch (and
for the next run of the program); the number is blanked, since it is always different.

**Undo Last Rename** puts the most recent batch back the way it was.  **Exit** closes the
program.

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

The retained name and a table of every batch renamed -- when it was done and each
old-name/new-name pair -- are kept in `ScanRenamer state.json` in the program's directory.
Undo works off the last entry in that table and removes it when it succeeds.  The file is
per-installation and is not in the repository.

## Running it

wxPython is the only requirement:

    pip install -r requirements.txt
    python ScanRenamer.py
