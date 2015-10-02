"""
UI elements for interaction with Frame.io from within Nuke Studio

"""
from PySide import QtGui
from PySide.QtCore import Qt, QUrl, QRegExp, QCoreApplication
from PySide.QtWebKit import QWebView
import hiero.core 
from hiero.ui import activeView, createMenuAction, mainWindow
import frameio
import os
cwd = os.path.dirname(os.path.realpath(__file__))
#gIconPath = os.path.abspath(os.path.join(cwd, "icons"))
gIconPath = "/Users/ant/.nuke/Python/Startup/frameio_exporter/icons/"

gGoogleAccountsEnabled = False # until we get oauth2 login figured out

class FnFrameioMenu(QtGui.QMenu):
    def __init__(self):
        QtGui.QMenu.__init__(self, "Frame.io", None)
        hiero.core.events.registerInterest("kShowContextMenu/kBin", self.eventHandler)
        self._actionUploadSelection = createMenuAction("Share to Frame.io...", 
                                                                self.FrameioUploadSelectionAction, 
                                                                icon=os.path.join(gIconPath + "logo-gray.png"))
        self.addAction(self._actionUploadSelection)

    def FrameioUploadSelectionAction(self):
        """Presents the Frame.io Widget with the active selection of Bin items"""
        selection = activeView().selection()
        if not selection:
            return

        print "Presenting the Frame.io view controller with %s" % str(selection)

        hiero.core.frameioDelegate.showFrameioWidgetWithSelection(selection=selection)

    def eventHandler(self, event):
        # Check if this actions are not to be enabled

        if not hasattr(event.sender, 'selection'):
          # Something has gone wrong, we shouldn't only be here if raised
          # by the timeline view which will give a selection.
          return
        event.menu.addMenu(self)    

class FnFrameioWidget(QtGui.QWidget):
    """
    Main Frame.io widget for handling interaction with
    Frame.io
    """

    eStatusCheckEmail = "Checking E-mail."
    eStatusCheckCredentials = "Checking user login credentials."
    eStatusEmailInvalid = "Not a valid E-mail."
    eStatusGmailUnsupported =  "Google Accounts not currently supported."
    eStatusPasswordInvalid =  "Please enter a valid password."
    eStatusLoggingIn = "Logging in..."
    eConnectionError = "Connection error. Check internet access!"

    def __init__(self, delegate, username=None):
        super(FnFrameioWidget, self).__init__()

        global gIconPath

        self._clips = []
        self._sequences = []

        self.username = username

        # FrameioDelegate
        self.delegate = delegate #kwargs.get("delegate", None)

        # setGeometry(x_pos, y_pos, width, height)
        self.setGeometry(240, 160, 726, 552)
        self.setStyleSheet('QWidget {background-color: #3B3E4A;} QLineEdit {color: #D0D5DC; border-color:#6F757F; border-width: 1px; border-radius: 4px; border-style: solid;} QLabel {color: #D0D5DC;}')
        self.setWindowTitle("Frame.io Uploader")

        #self.setAttribute( Qt.WA_TranslucentBackground, True )  
        self.setWindowFlags( Qt.FramelessWindowHint )
        self.setMouseTracking(True)
        self.draggable = True
        self.dragging_threshold = 0
        self.__mousePressPos = None
        self.__mouseMovePos = None

        layout = QtGui.QVBoxLayout(self)

        layout.setAlignment(Qt.AlignCenter)

        self.toolBar = QtGui.QToolBar()
        self.toolBar.setStyleSheet('QToolBar {background-color: #3B3E4A; border-width: 0px; border-radius: 0px; border-style: none;}')
        
        self.closeButton = QtGui.QPushButton("")
        self.closeButton.setStyleSheet('QPushButton {border: none;}')
        icon = QtGui.QIcon(os.path.join(gIconPath + "close.png"))

        self.closeButton.setIcon(icon)
        self.closeButton.clicked.connect(self.close)
        self.toolBar.addWidget(self.closeButton)
        layout.addWidget(self.toolBar)

        pixmap = QtGui.QPixmap(os.path.join(gIconPath + "logo-64px.png"))
        lbl = QtGui.QLabel("")
        lbl.setPixmap(pixmap)
        lbl.setAlignment(Qt.AlignCenter)    
        layout.addWidget(lbl)

        font = QtGui.QFont()
        font.setPointSize(20)
        self.topLabel = QtGui.QLabel("Sign In")
        self.topLabel.setFont(font)
        self.topLabel.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.topLabel)

        self.statusLabel = QtGui.QLabel("")
        self.statusLabel.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.statusLabel)


        self.stackView = QtGui.QStackedWidget(self)

        # Login Screen View
        self.loginView = QtGui.QWidget()
        self.loginViewLayout = QtGui.QVBoxLayout(self)
        self.loginViewLayout.setAlignment(Qt.AlignCenter)        

        self.emailLineEdit = QtGui.QLineEdit()
        self.emailLineEdit.setPlaceholderText("E-mail")
        self.emailLineEdit.setFont(font)
        self.emailLineEdit.setAlignment(Qt.AlignCenter)  
        self.emailLineEdit.setFixedWidth(370)
        self.emailLineEdit.setFixedHeight(60)
        if self.username:
            self.emailLineEdit.setText(self.username)

        # Validator for checking email address is valid
        namerx = QRegExp("\\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\\.[A-Z]{2,4}\\b")
        namerx.setCaseSensitivity(Qt.CaseInsensitive);
        namerx.setPatternSyntax(QRegExp.RegExp);
        self.nameval = QtGui.QRegExpValidator(namerx, self)
        self.emailLineEdit.setValidator(self.nameval)

        self.loginViewLayout.addWidget(self.emailLineEdit)

        self.passwordLineEdit = QtGui.QLineEdit()
        self.passwordLineEdit.setStyleSheet('')
        self.passwordLineEdit.setPlaceholderText("Password")
        self.passwordLineEdit.setFont(font)
        self.passwordLineEdit.setAlignment(Qt.AlignCenter)  
        self.passwordLineEdit.setFixedWidth(370)
        self.passwordLineEdit.setFixedHeight(60)
        self.passwordLineEdit.setEchoMode(QtGui.QLineEdit.Password)

        self.loginViewLayout.addWidget(self.passwordLineEdit)        

        self.submitButton = QtGui.QPushButton("LET'S GO")
        self.submitButton.setFlat(True)
        self.submitButton.setFont(font)
        self.submitButton.clicked.connect(self._submitButtonPressed)
        self.submitButton.setStyleSheet('QPushButton {width: 370px; height: 60px; border-width: 0px; border-radius: 4px; border-style: solid; background-color: #83DEBD; color: white;}')

        self.loginViewLayout.addWidget(self.submitButton)

        self.loginView.setLayout(self.loginViewLayout)

        self.stackView.addWidget(self.loginView)

        ### View to handle uploading of Clips via drag-drop into a dropzone
        self.uploadDropzoneView = QtGui.QWidget()
        self.uploadDropzoneView.setAcceptDrops(True) # Not hooked up.

        self.uploadDropzoneLayout = QtGui.QVBoxLayout(self)
        self.uploadDropzoneLayout.setAlignment(Qt.AlignCenter)

        pixmap = QtGui.QPixmap(os.path.join(gIconPath + "uploadDropzone-64px.png"))
        uploadIcon = QtGui.QLabel("")
        uploadIcon.setPixmap(pixmap)
        uploadIcon.setAlignment(Qt.AlignCenter)
        self.uploadDropzoneLayout.addWidget(uploadIcon)

        self.uploadDropzoneLabel1 = QtGui.QLabel("Upload your files")
        self.uploadDropzoneLabel1.setAlignment(Qt.AlignCenter)
        self.uploadDropzoneLabel1.setFont(font)
        self.uploadDropzoneLabel2 = QtGui.QLabel("Drag 'n Drop your files or Clips/Sequences here.")
        self.uploadDropzoneLabel1.setAlignment(Qt.AlignCenter)
        self.uploadDropzoneLayout.addWidget(self.uploadDropzoneLabel1)
        font.setPointSize(16)
        self.uploadDropzoneLabel2.setFont(font)
        self.uploadDropzoneLayout.addWidget(self.uploadDropzoneLabel2)

        self.uploadDropzoneView.setLayout(self.uploadDropzoneLayout)
        self.stackView.addWidget(self.uploadDropzoneView)

        ### View to handle uploading of Clips and Timelines View
        self.uploadView = QtGui.QWidget()
        self.uploadView.setStyleSheet('QPushButton {width: 100px; height: 100px; border-width: 0px; border-radius: 50px; border-style: solid; background-color: #9974BA; color: white;}')

        self.uploadViewLayout = QtGui.QVBoxLayout(self)
        self.uploadViewLayout.setAlignment(Qt.AlignCenter)

        self.uploadTopButtonWidget = QtGui.QWidget()
        self.uploadTopButtonLayout = QtGui.QHBoxLayout(self)
        self.uploadTopButtonLayout.setAlignment(Qt.AlignCenter)
        self.uploadTimelineOptionButton = QtGui.QPushButton("Timeline")
        self.uploadClipOptionButton = QtGui.QPushButton("Clips")
        self.uploadTimelineOptionButton.setCheckable(True)
        self.uploadTimelineOptionButton.setChecked(False)
        self.uploadTimelineOptionButton.setFont(font)
        self.uploadClipOptionButton.setCheckable(True)
        self.uploadClipOptionButton.setChecked(False)
        self.uploadClipOptionButton.setFont(font)
        self.uploadTopButtonLayout.addWidget(self.uploadTimelineOptionButton)
        self.uploadTopButtonLayout.addWidget(self.uploadClipOptionButton)
        self.uploadTopButtonWidget.setLayout(self.uploadTopButtonLayout)

        # This will control whether annotations are uploaded into Frame.io for the item
        self.exportAnnotationsCheckbox = QtGui.QCheckBox("Export Tags+Annotations Text comments")

        self.uploadBottomButtonWidget = QtGui.QWidget()
        self.uploadBottomButtonLayout = QtGui.QHBoxLayout(self)
        self.uploadBottomButtonLayout.setAlignment(Qt.AlignCenter)
        self.uploadCancelButton = QtGui.QPushButton("Cancel")
        self.uploadCancelButton.setStyleSheet('QPushButton {width: 170px; height: 70px; border-width: 0px; border-radius: 4px; border-style: solid; background-color: #767C8E; color: white;}')
        self.uploadCancelButton.clicked.connect(self.showDropzoneUploadView)

        self.uploadTaskButton = QtGui.QPushButton("Upload")
        self.uploadTaskButton.setStyleSheet('QPushButton {width: 170px; height: 70px; border-width: 0px; border-radius: 4px; border-style: solid; color: white;}')
        self.uploadTaskButton.clicked.connect(self._uploadButtonPushed)
        font.setPointSize(20)
        self.uploadCancelButton.setFont(font)
        self.uploadTaskButton.setFont(font)
        self.uploadBottomButtonLayout.addWidget(self.uploadCancelButton)
        self.uploadBottomButtonLayout.addWidget(self.uploadTaskButton)
        self.uploadBottomButtonWidget.setLayout(self.uploadBottomButtonLayout)

        self.projectDropdown = QtGui.QComboBox()
        self.projectDropdown.setFont(font)
        self.projectDropdown.setEditable(True)
        self.projectDropdown.lineEdit().setAlignment(Qt.AlignCenter)
        self.projectDropdown.setEditable(False)
        self.projectDropdown.setStyleSheet('QComboBox {width: 350px; height: 50px; border-width: 0px; border-radius: 4px; border-style: solid; background-color: #4F535F; color: white;}')

        # We don't really need these FCP X style buttons because this acts upon a Selection
        #self.uploadViewLayout.addWidget(self.uploadTopButtonWidget)

        ### Enable when annotation uploads are supported
        #self.uploadViewLayout.addWidget(self.exportAnnotationsCheckbox)

        self.uploadViewLayout.addWidget(self.projectDropdown)
        self.uploadViewLayout.addWidget(self.uploadBottomButtonWidget)

        self.uploadView.setLayout(self.uploadViewLayout)

        self.stackView.addWidget(self.uploadView)

        sizeGrip = QtGui.QSizeGrip(self)
        sizeGrip.setStyleSheet("QSizeGrip { height:12px; }")

        layout.addWidget(self.stackView)
        layout.addWidget(sizeGrip, 0, Qt.AlignBottom | Qt.AlignRight);
        self.setMinimumSize(160, 160)        
        self.setLayout(layout)
        self.emailLineEdit.setFocus()

    def show(self, selection):
        if selection:
            self._clips = [item.activeItem() for item in selection if hasattr(item, 'activeItem') and isinstance(item.activeItem(), hiero.core.Clip)]
            self._sequences = [item.activeItem() for item in selection if hasattr(item, 'activeItem') and isinstance(item.activeItem(), hiero.core.Sequence)]

        return super(FnFrameioWidget, self).show()

    def mousePressEvent(self, event):
        if self.draggable and event.button() == Qt.LeftButton:
            self.__mousePressPos = event.globalPos()                # global
            self.__mouseMovePos = event.globalPos() - self.pos()    # local
        super(FnFrameioWidget, self).mousePressEvent(event)
 
    def mouseMoveEvent(self, event):
        if self.draggable and event.buttons() & Qt.LeftButton:
            globalPos = event.globalPos()
            if globalPos and self.__mousePressPos:
                moved = globalPos - self.__mousePressPos
                diff = globalPos - self.__mouseMovePos
                self.move(diff)
                self.__mouseMovePos = globalPos - self.pos()
        super(FnFrameioWidget, self).mouseMoveEvent(event)

    def setStatus(self, text):
        self.statusLabel.setText(text)

    def selectedProject(self):
        """Returns the currently selected Project name"""
        return self.projectDropdown.currentText()

    def _uploadButtonPushed(self):
        project = self.selectedProject()
        self.setStatus("Clips: %s\n, Sequences %s" % (str(self._clips), str(self._sequences)))

        # Should move logic below out of UI here and just pass the items
        movieClips = []
        nonMovieClips = []
        
        if len(self._clips) > 0:
            # Find out which Clips do not need to be transcoded
            movieClips = [clip for clip in self._clips if hiero.core.isQuickTimeFileExtension(os.path.splitext(clip.mediaSource().filename())[-1])]
            nonMovieClips = [clip for clip in self._clips if clip not in movieClips]

        self.setStatus("Movie Clips: %s, nonMovieClips %s" % (str(movieClips), str(nonMovieClips)))
        filesToUpload = []
        for movClip in movieClips:
            filesToUpload += [ movClip.mediaSource().fileinfos()[0].filename() ]

        for filePath in filesToUpload:
            print  "_uploadButtonPushed: filePath to upload: %s" % filePath
            self.delegate.uploadFile(filePath, project)
 
    def showLoginView(self):
        # Sets the stackView to show the Login View
        self.stackView.setCurrentWidget(self.loginView)

    def showDropzoneUploadView(self):
        # Sets the stackView to show the Dropzone Upload View
        self.stackView.setCurrentWidget(self.uploadDropzoneView)

    def showUploadView(self):
        # Sets the stackView to show the Upload View
        self._updateProjectsList()
        self.stackView.setCurrentWidget(self.uploadView)

    def _updateProjectsList(self):
        #Updates the Project list with list of project strings
        self.projectDropdown.clear()

        print str(self.delegate.frameioSession.projectdict().values())
        projects = self.delegate.frameioSession.projectdict().values()
        for project in projects:
            self.projectDropdown.addItem(project)

    def _submitButtonPressed(self):
        """Called when Submit button is pressed."""
        emailText = self.emailLineEdit.text()
        passwordText = self.passwordLineEdit.text()
        res = self.nameval.validate(emailText, 0)

        # If Gmail oauth2 is not implemented...
        if not gGoogleAccountsEnabled:
            if "gmail.com" in emailText or "googlemail.com" in emailText:
                    self.setStatus(self.eStatusGmailUnsupported)
                    self.emailLineEdit.setFocus()
                    return

        if res[0] != QtGui.QValidator.State.Acceptable:
                self.setStatus(self.eStatusEmailInvalid)
                self.emailLineEdit.setFocus()
                return
        else:
            self.setStatus(self.eStatusCheckEmail)
            self.username = emailText
            if len(passwordText) < 6:
                self.setStatus(self.eStatusPasswordInvalid)
                return
            else:
                self.password = passwordText

        if self.username and self.password:
            self.delegate.attemptLogin(self.username, self.password)

    def keyPressEvent(self, e):
        """Close the popover if Escape is pressed"""
        if e.key() == Qt.Key_Escape:
            self.close()