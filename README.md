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

Supply the files either by dropping them on the window or with **Select Files...**.  The
order in which they are supplied is the order in which they are numbered.  If that order is
not alphabetical, ScanRenamer says so and offers a choice of sorting them alphabetically,
numbering them as supplied, or cancelling.

Type the name and the number and press **Rename**.  The name is kept for the next batch (and
for the next run of the program); the number is blanked, since it is always different.

**Undo Last Rename** puts the most recent batch back the way it was.  **Exit** closes the
program.

## ScanRenamer state.json

The retained name and a table of every batch renamed -- when it was done and each
old-name/new-name pair -- are kept in `ScanRenamer state.json` in the program's directory.
Undo works off the last entry in that table and removes it when it succeeds.  The file is
per-installation and is not in the repository.

## Running it

wxPython is the only requirement:

    pip install -r requirements.txt
    python ScanRenamer.py
