# Copyright: Damien Elmes <anki@ichi2.net>
# -*- coding: utf-8 -*-
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

from aqt.qt import *
import sys, re
import aqt.forms
import anki
from anki.errors import *
from anki.utils import stripHTML
from aqt.utils import saveGeom, restoreGeom, showWarning, askUser, shortcut, \
    tooltip, openHelp
from anki.sound import clearAudioQueue
from anki.hooks import addHook, remHook
from anki.utils import stripHTMLMedia, isMac
import aqt.editor, aqt.modelchooser

class AddCards(QDialog):

    def __init__(self, mw):
        QDialog.__init__(self, mw)
        self.mw = mw
        self.form = aqt.forms.addcards.Ui_Dialog()
        self.form.setupUi(self)
        self.setWindowTitle(_("Add"))
        self.setMinimumHeight(400)
        self.setMinimumWidth(500)
        self.setupChooser()
        self.setupEditor()
        self.setupButtons()
        self.onReset()
        self.history = []
        self.forceClose = False
        restoreGeom(self, "add")
        addHook('reset', self.onReset)
        addHook('currentModelChanged', self.onReset)
        self.mw.requireReset(modal=True)
        self.open()
        self.setupNewNote()

    def setupEditor(self):
        self.editor = aqt.editor.Editor(self.mw, self.form.fieldsArea, True)

    def setupChooser(self):
        self.modelChooser = aqt.modelchooser.ModelChooser(
            self.mw, self.form.modelArea)

    def helpRequested(self):
        openHelp("AddItems")

    def setupButtons(self):
        bb = self.form.buttonBox
        ar = QDialogButtonBox.ActionRole
        # add
        self.addButton = bb.addButton(_("Add"), ar)
        self.addButton.setShortcut(QKeySequence("Ctrl+Return"))
        self.addButton.setToolTip(shortcut(_("Add (shortcut: ctrl+enter)")))
        self.connect(self.addButton, SIGNAL("clicked()"), self.addCards)
        # close
        self.closeButton = QPushButton(_("Close"))
        self.closeButton.setAutoDefault(False)
        bb.addButton(self.closeButton,
                                        QDialogButtonBox.RejectRole)
        # help
        self.helpButton = QPushButton(_("Help"))
        self.helpButton.setAutoDefault(False)
        bb.addButton(self.helpButton,
                                        QDialogButtonBox.HelpRole)
        self.connect(self.helpButton, SIGNAL("clicked()"), self.helpRequested)
        # history
        b = bb.addButton(
            _("History")+ u'▼', ar)
        self.connect(b, SIGNAL("clicked()"), self.onHistory)
        b.setEnabled(False)
        self.historyButton = b

    # FIXME: need to make sure to clean up note on exit
    def setupNewNote(self, set=True):
        f = self.mw.col.newNote()
        f.tags = f.model()['tags']
        if set:
            self.editor.setNote(f)
        return f

    def onReset(self, model=None, keep=False):
        oldNote = self.editor.note
        note = self.setupNewNote(set=False)
        flds = note.model()['flds']
        # copy fields from old note
        if oldNote:
            if not keep:
                self.removeTempNote(oldNote)
            for n in range(len(note.fields)):
                try:
                    if not keep or flds[n]['sticky']:
                        note.fields[n] = oldNote.fields[n]
                    else:
                        note.fields[n] = ""
                except IndexError:
                    break
        self.editor.setNote(note)

    def removeTempNote(self, note):
        if not note or not note.id:
            return
        # we don't have to worry about cards; just the note
        self.mw.col._remNotes([note.id])

    def addHistory(self, note):
        txt = stripHTMLMedia(",".join(note.fields))[:30]
        self.history.append((note.id, txt))
        self.history = self.history[-15:]
        self.historyButton.setEnabled(True)

    def onHistory(self):
        m = QMenu(self)
        for nid, txt in self.history:
            a = m.addAction(_("Edit %s" % txt))
            a.connect(a, SIGNAL("triggered()"),
                      lambda nid=nid: self.editHistory(nid))
        m.exec_(self.historyButton.mapToGlobal(QPoint(0,0)))

    def editHistory(self, nid):
        browser = aqt.dialogs.open("Browser", self.mw)
        browser.form.searchEdit.setText("nid:%d" % nid)
        browser.onSearch()

    def addNote(self, note):
        if any(note.problems()):
            showWarning(_(
                "Some fields are missing or not unique."),
                     help="AddItems#AddError")
            return
        cards = self.mw.col.addNote(note)
        if not cards:
            showWarning(_("""\
The input you have provided would make an empty
question or answer on all cards."""), help="AddItems")
            return
        self.addHistory(note)
        # FIXME: return to overview on add?
        return note

    def addCards(self):
        self.editor.saveNow()
        note = self.editor.note
        note = self.addNote(note)
        if not note:
            return
        tooltip("Added", period=500)
        # stop anything playing
        clearAudioQueue()
        self.onReset(keep=True)
        self.mw.col.autosave()

    def keyPressEvent(self, evt):
        "Show answer on RET or register answer."
        if (evt.key() in (Qt.Key_Enter, Qt.Key_Return)
            and self.editor.tags.hasFocus()):
            evt.accept()
            return
        return QDialog.keyPressEvent(self, evt)

    def reject(self):
        if not self.canClose():
            return
        remHook('reset', self.onReset)
        remHook('currentModelChanged', self.onReset)
        clearAudioQueue()
        self.removeTempNote(self.editor.note)
        self.editor.setNote(None)
        self.modelChooser.cleanup()
        self.mw.maybeReset()
        saveGeom(self, "add")
        aqt.dialogs.close("AddCards")
        QDialog.reject(self)

    def canClose(self):
        if (self.forceClose or self.editor.fieldsAreBlank() or
            askUser(_("Close and lose current input?"))):
            return True
        return False
