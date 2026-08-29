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
stands for the files directly inside it, in name order; dropping something with no
files in it says so rather than appearing to do nothing.

The batch is shown two columns wide: each file on the left, and on the right the name it
would be renamed to.  They are the two columns of a single list, so they scroll as one and
cannot drift apart.

### Renaming part of a batch

**Rename** works on the whole batch, or on one unbroken run of files picked out in the list --
click the first and shift-click the last.  Only the files which would be renamed have a name
against them, so picking out a run leaves the rest of the right-hand column empty and it is
plain what is about to happen.

A run is numbered from `p1` like any other batch, and the files not picked out stay in the
batch afterwards, still listed and ready for a rename of their own.  Two issues scanned one
after the other into the same folder can therefore be named an issue at a time: pick out the
first issue's pages, give them their number, Rename; what is left is the second issue, and the
Number box is already empty and waiting.

A selection with a gap in it is refused rather than guessed at -- the files are being numbered
in a run, so which files that run is made of has to be beyond doubt.

The proposed names are regenerated at every keystroke, from the first character typed.
Whichever of the name and the number has not been filled in yet is left out of them, so
typing just `Spaceways` shows `Spaceways p01.jpg` and the number slots itself in as it is
typed.  With neither filled in there is only the page numbering to show, and it appears as
`p 01.jpg`, `p 02.jpg`... -- spaced out to look like the placeholder it is.  Renaming still
needs both.

The order in which the files are supplied is the order in which they are numbered.  If that
order is not name order, ScanRenamer says so and offers a choice of sorting them by name,
numbering them as supplied, or cancelling.

Sorting renumbers the files, so it does not rename them there and then -- that would give
names the right-hand column never showed.  Instead the batch is put in order and left for you
to look at, the column now saying what each file would become, and pressing **Rename** again
does it.  The question is not asked twice, the batch being in name order by then.  **Keep as
supplied** renames straight away.

### Name order

Names are compared as text **except for a number at the end of the name, which is compared as
a number**:

    page1.jpg  page9.jpg  page10.jpg          and not  page1.jpg  page10.jpg  page9.jpg

A name with no number at the end comes before the numbered ones sharing its text, which puts
the scanner's own first page (`z-.jpg`) ahead of `z-_1.jpg`.  Only the last run of digits
counts, so `a2b.jpg`, `a2b3.jpg`, `a2b10.jpg`; digits anywhere else are just text.  Case is
ignored, as Windows ignores it, and files in different folders are grouped by folder.

The same rule is used everywhere -- for a dropped folder, for **Sort by name**, and for the
watched folder -- so dropping a folder of scans gives exactly the order watching it would.
It matters most when a scanner numbers without padding: sorting as plain text would put
`z-_10.jpg` between `z-_1.jpg` and `z-_2.jpg` and silently number the pages that way.

Files from the watched folder are never asked about, being in this order already.

Type the name and the number and press **Rename**, which is picked out in light yellow as the
button the work is done with.  The number is blanked, since it is always different, and the
cursor is put in the Number box ready to type the next one.

The name is kept -- for the next batch, and for the next run of the program.  It is saved
both when a batch is renamed and when the window is closed, so a name typed and not yet used
is still there next time.  (Emptying the box is remembered too: that is what you did.)

**Undo Last Rename** puts the most recent batch back the way it was.  **Exit** closes the
program -- asking first if the batch still holds files which have not been renamed, since the
gathering of them and the order they were put in would otherwise have to be done again.  The
window's own close box asks the same question.

## Nothing is ever overwritten

A rename never writes over an existing file.  Before anything is renamed, ScanRenamer looks
the whole batch over for three kinds of trouble:

* a file which would land on a name already belonging to a file which is not part of the
  batch,
* two files of the batch which would end up with the same name, and
* the same file supplied twice -- which would otherwise stop the batch part way through with
  a mystifying complaint about a file that cannot be found.

Any of them is reported, naming the files it is about (with the folder they are in), and the
whole batch is left exactly as it was -- it is never a matter of some files being renamed and
others not.

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
name order, and pages go on being added to the list as they are scanned, up until
**Rename** is pressed.  With the settings above that means `z-.jpg`, `z-_001.jpg`,
`z-_002.jpg`... and nothing else in the folder.  Files supplied by hand take the batch over;
the watcher leaves them alone until the batch is empty again.

A rename which would produce a scanner-looking name is refused rather than done, so a renamed
file can never be picked back up by the watcher.

The watcher does not wait for the scanner to finish writing a page, so a file can appear in
the list a moment before it is complete.  Press **Rename** when the scanning is done: a file
the scanner still has open cannot be renamed, and the whole batch would be rolled back.

The watcher is held still while a batch is being renamed or put back.  Windows goes on
delivering timer ticks while a dialog is up, so without that a page arriving in the middle of
a question could reload the batch under the work.

## ScanRenamer state.json

The retained name and a table of every batch renamed -- when it was done, the name and number
it was renamed with, and each old-name/new-name pair -- are kept in `ScanRenamer state.json`
in the program's directory.  Undo works off the last entry in that table and removes it when
it succeeds, so pressing it again walks back through the batches before it.  The last 50 are
kept -- the file is read and written whole at every rename, so there is nothing to be gained
by letting it grow for ever.  The file is per-installation and is not in the repository.

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
