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
Files...**, or let ScanRenamer pick them up from a watched folder (below).  The order in
which they are supplied is the order in which they are numbered.  If that order is not
alphabetical, ScanRenamer says so and offers a choice of sorting them alphabetically,
numbering them as supplied, or cancelling.

Type the name and the number and press **Rename**.  The name is kept for the next batch (and
for the next run of the program); the number is blanked, since it is always different.

**Undo Last Rename** puts the most recent batch back the way it was.  **Exit** closes the
program.

## The watched folder

`ScanRenamer settings.txt`, in the program's directory, names the folder to watch:

    Watch Folder=C:\Users\mlo\Documents\Scans

The line is read when ScanRenamer starts, so change it with the program shut down.  With no
such line -- or with its value commented out, `Watch Folder=#...` -- no folder is watched and
the window says so.

So long as nothing has been supplied by hand, everything in that folder which looks like
scanner output is loaded into the batch in alphabetical order, and pages go on being added to
the list as they are scanned, up until **Rename** is pressed.  Files supplied by hand take
the batch over; the watcher leaves them alone until the batch is empty again.

"Looks like scanner output" means a name with no spaces in it and a `.jpg` or `.jpeg`
extension, so both `{xx}.jpg` and `{xx}_nnn.jpg` qualify (as does any other spaceless name).
A renamed file always has spaces in its name, so it can never be mistaken for a new scan; a
rename which would produce a scanner-looking name is refused rather than done.

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
