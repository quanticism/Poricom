"""
Poricom Main Window Component

Copyright (C) `2021-2022` `<Alarcon Ace Belen>`

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

from shutil import rmtree
from time import sleep

import toml
from manga_ocr import MangaOcr
from PyQt5.QtCore import (Qt, QAbstractNativeEventFilter, QThreadPool)
from PyQt5.QtWidgets import (QVBoxLayout, QWidget, QDesktopWidget, QMainWindow, QApplication,
                             QPushButton, QFileDialog, QInputDialog, QSplitter)

from utils.image_io import mangaFileToImageDir
from utils.config import config, saveOnClose
from Workers import BaseWorker
from Ribbon import (Ribbon)
from Explorers import (ImageExplorer)
from Views import (OCRCanvas, FullScreen)
from Popups import (FontPicker, LanguagePicker, ScaleImagePicker,
                    ShortcutPicker, PickerPopup, MessagePopup, CheckboxPopup)


class WinEventFilter(QAbstractNativeEventFilter):
    def __init__(self, keybinder):
        self.keybinder = keybinder
        super().__init__()

    def nativeEventFilter(self, eventType, message):
        ret = self.keybinder.handler(eventType, message)
        return ret, 0


class MainWindow(QMainWindow):

    def __init__(self, parent=None, tracker=None):
        super(QWidget, self).__init__(parent)
        self.tracker = tracker
        self.config = config

        self.vLayout = QVBoxLayout()
        self.ribbon = Ribbon(self, self.tracker)
        self.vLayout.addWidget(self.ribbon)
        self.canvas = OCRCanvas(self, self.tracker)
        self.explorer = ImageExplorer(self, self.tracker)

        self.splitter = QSplitter()
        self.splitter.addWidget(self.explorer)
        self.splitter.addWidget(self.canvas)
        self.splitter.setChildrenCollapsible(False)
        for i, s in enumerate(config["NAV_VIEW_RATIO"]):
            self.splitter.setStretchFactor(i, s)

        self.vLayout.addWidget(self.splitter)
        _mainWidget = QWidget()
        _mainWidget.setLayout(self.vLayout)
        self.setCentralWidget(_mainWidget)

        self.threadpool = QThreadPool()

    def viewImageFromExplorer(self, filename, filenext):
        if not self.canvas.splitViewMode():
            self.tracker.pixImage = filename
        if self.canvas.splitViewMode():
            self.tracker.pixImage = (filename, filenext)
        if not self.tracker.pixImage.isValid():
            return False
        self.canvas.resetTransform()
        self.canvas.currentScale = 1
        self.canvas.verticalScrollBar().setSliderPosition(0)
        self.canvas.viewImage()
        self.canvas.setFocus()
        return True

    def resizeEvent(self, event):
        self.explorer.setMinimumWidth(0.1*self.width())
        self.canvas.setMinimumWidth(0.6*self.width())
        return super().resizeEvent(event)

    def closeEvent(self, event):
        try:
            rmtree("./poricom_cache")
        except FileNotFoundError:
            pass
        self.config["NAV_ROOT"] = self.tracker.filepath
        saveOnClose(self.config)
        return QMainWindow.closeEvent(self, event)

    def poricomNoop(self):
        MessagePopup(
            "WIP",
            "This function is not yet implemented."
        ).exec()

# ------------------------------ File Functions ------------------------------ #

    def openDir(self):
        filepath = QFileDialog.getExistingDirectory(
            self,
            "Open Directory",
            self.tracker.filepath  # , QFileDialog.DontUseNativeDialog
        )

        if filepath:
            try:
                self.tracker.filepath = filepath
                self.explorer.setDirectory(filepath)
            except FileNotFoundError:
                MessagePopup(
                    f"No images found in the directory",
                    f"Please select a directory with images."
                ).exec()

    def openManga(self):
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Open Manga File",
            self.tracker.filepath,
            "Manga (*.cbz *.cbr *.zip *.rar *.pdf)"
        )

        if filename:
            def setDirectory(filepath):
                self.tracker.filepath = filepath
                self.explorer.setDirectory(filepath)

            openMangaButton = self.ribbon.findChild(
                QPushButton, "openManga")

            worker = BaseWorker(mangaFileToImageDir, filename)
            worker.signals.result.connect(setDirectory)
            worker.signals.finished.connect(
                lambda: openMangaButton.setEnabled(True))

            self.threadpool.start(worker)
            openMangaButton.setEnabled(False)

    def captureExternalHelper(self):
        self.showMinimized()
        sleep(0.5)
        if self.isMinimized():
            self.captureExternal()

    def captureExternal(self):
        externalWindow = QMainWindow()
        externalWindow.layout().setContentsMargins(0, 0, 0, 0)
        externalWindow.setStyleSheet("border:0px; margin:0px")
        externalWindow.setAttribute(Qt.WA_DeleteOnClose)

        externalWindow.setCentralWidget(
            FullScreen(externalWindow, self.tracker))
        fullScreen = externalWindow.centralWidget()

        screenIndex = fullScreen.getActiveScreenIndex()
        screen = QDesktopWidget().screenGeometry(screenIndex)
        fullScreen.takeScreenshot(screenIndex)
        externalWindow.move(screen.left(), screen.top())
        externalWindow.showFullScreen()

# ------------------------------ View Functions ------------------------------ #

    def toggleStylesheet(self):
        config = "./utils/config.toml"
        lightMode = "./assets/styles.qss"
        darkMode = "./assets/styles-dark.qss"

        data = toml.load(config)
        if data["STYLES_DEFAULT"] == lightMode:
            data["STYLES_DEFAULT"] = darkMode
        elif data["STYLES_DEFAULT"] == darkMode:
            data["STYLES_DEFAULT"] = lightMode
        with open(config, 'w') as fh:
            toml.dump(data, fh)

        app = QApplication.instance()
        if app is None:
            raise RuntimeError("No Qt Application found.")

        styles = data["STYLES_DEFAULT"]
        self.config["STYLES_DEFAULT"] = data["STYLES_DEFAULT"]
        with open(styles, 'r') as fh:
            app.setStyleSheet(fh.read())

    def modifyFontSettings(self):
        confirmation = PickerPopup(FontPicker(self, self.tracker))
        ret = confirmation.exec()

        if ret:
            app = QApplication.instance()
            if app is None:
                raise RuntimeError("No Qt Application found.")

            with open(config["STYLES_DEFAULT"], 'r') as fh:
                app.setStyleSheet(fh.read())

    def toggleSplitView(self):
        self.canvas.toggleSplitView()
        if self.canvas.splitViewMode():
            self.canvas.setViewImageMode(2)
            index = self.explorer.currentIndex()
            self.explorer.currentChanged(index, index)
        elif not self.canvas.splitViewMode():
            index = self.explorer.currentIndex()
            self.explorer.currentChanged(index, index)

    def scaleImage(self):
        confirmation = PickerPopup(ScaleImagePicker(self, self.tracker))
        confirmation.exec()

    def hideExplorer(self):
        self.explorer.setVisible(not self.explorer.isVisible())

# ----------------------------- Control Functions ---------------------------- #

    def toggleMouseMode(self):
        self.canvas.toggleZoomPanMode()

    def modifyHotkeys(self):
        confirmation = PickerPopup(ShortcutPicker(self, self.tracker))
        ret = confirmation.exec()
        if ret:
            MessagePopup(
                "Shortcut Remapped",
                "Close the app to apply changes."
            ).exec()

# ------------------------------ Misc Functions ------------------------------ #

    def loadModel(self):
        loadModelButton = self.ribbon.findChild(QPushButton, "loadModel")
        loadModelButton.setChecked(not self.tracker.ocrModel)

        if loadModelButton.isChecked() and self.config["LOAD_MODEL_POPUP"]:
            confirmation = CheckboxPopup(
                "Load the MangaOCR model?",
                "If you are running this for the first time, this will " +
                "download the MangaOcr model which is about 400 MB in size. " +
                "This will improve the accuracy of Japanese text detection " +
                "in Poricom. If it is already in your cache, it will take a " +
                "few seconds to load the model.",
                MessagePopup.Ok | MessagePopup.Cancel
            )
            ret = confirmation.exec()
            self.config["LOAD_MODEL_POPUP"] = not confirmation.checkBox().isChecked()
            if (ret == MessagePopup.Ok):
                pass
            else:
                loadModelButton.setChecked(False)
                return

        def loadModelHelper(tracker):
            betterOCR = tracker.switchOCRMode()
            if betterOCR:
                import http.client as httplib

                def isConnected(url=self.config["CHECK_INTERNET_URL"]):
                    if not self.config["CHECK_INTERNET_POPUP"]:
                        return True
                    connection = httplib.HTTPSConnection(url, timeout=2)
                    try:
                        connection.request("HEAD", "/")
                        return True
                    except Exception:
                        tracker.switchOCRMode()
                        return False
                    finally:
                        connection.close()

                connected = isConnected()
                if connected:
                    try:
                        tracker.ocrModel = MangaOcr()
                    except ValueError:
                        return (betterOCR, False)
                return (betterOCR, connected)
            else:
                tracker.ocrModel = None
                return (betterOCR, True)

        def modelLoadedConfirmation(typeConnectionTuple):
            usingMangaOCR, connected = typeConnectionTuple
            modelName = "MangaOCR" if usingMangaOCR else "Tesseract"
            if connected:
                MessagePopup(
                    f"{modelName} model loaded",
                    f"You are now using the {modelName} model for Japanese text detection."
                ).exec()

            elif not connected:
                connectionErrorMessage = CheckboxPopup(
                    "Connection Error",
                    "Please try again or make sure your Internet connection is on.",
                    checkboxMessage=(
                        "Check this box if you keep getting this error even with connection on."
                    )
                )
                connectionErrorMessage.exec()
                self.config["CHECK_INTERNET_POPUP"] = \
                            not connectionErrorMessage.checkBox().isChecked()
                loadModelButton.setChecked(False)

        worker = BaseWorker(loadModelHelper, self.tracker)
        worker.signals.result.connect(modelLoadedConfirmation)
        worker.signals.finished.connect(lambda:
                                        loadModelButton.setEnabled(True))

        self.threadpool.start(worker)
        loadModelButton.setEnabled(False)

    def modifyTesseract(self):
        confirmation = PickerPopup(LanguagePicker(self, self.tracker))
        confirmation.exec()

    def toggleLogging(self):
        self.tracker.switchWriteMode()

# --------------------------- Always On Functions ---------------------------- #

    def loadPrevImage(self):
        index = self.explorer.indexAbove(self.explorer.currentIndex())
        if self.canvas.splitViewMode():
            tempIndex = self.explorer.indexAbove(index)
            if tempIndex.isValid():
                index = tempIndex
        if (not index.isValid()):
            return
        self.explorer.setCurrentIndex(index)

    def loadNextImage(self):
        index = self.explorer.indexBelow(self.explorer.currentIndex())
        if self.canvas.splitViewMode():
            tempIndex = self.explorer.indexBelow(index)
            if tempIndex.isValid():
                index = tempIndex
        if (not index.isValid()):
            return
        self.explorer.setCurrentIndex(index)

    def loadImageAtIndex(self):
        rowCount = self.explorer.model.rowCount(self.explorer.rootIndex())
        i, _ = QInputDialog.getInt(
            self,
            'Jump to',
            f'Enter page number: (max is {rowCount})',
            value=-1,
            min=1,
            max=rowCount,
            flags=Qt.CustomizeWindowHint | Qt.WindowTitleHint)
        if (i == -1):
            return

        index = self.explorer.model.index(i-1, 0, self.explorer.rootIndex())
        self.explorer.setCurrentIndex(index)

    def zoomIn(self):
        self.canvas.zoomView(True, usingButton=True)

    def zoomOut(self):
        self.canvas.zoomView(False, usingButton=True)
