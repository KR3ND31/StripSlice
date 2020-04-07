import sys
import threading
from queue import Queue
import numpy
import cv2

from PyQt5 import QtCore, QtWidgets, uic
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import QMainWindow, QApplication, QFileDialog, QWidget

import GUI.resources
from GUI import main_form

#class MainWindow(QMainWindow, main_form.Ui_f_main):
class MainWindow(QMainWindow): # after complete replace ^ class MainWindow(QMainWindow, main_form.Ui_f_main):
    def __init__(self):
        super(MainWindow, self).__init__()

        #self.setupUi(self)
        uic.loadUi('GUI/main_form.ui', self)  # after complete replace ^ self.setupUi(self)

        # self params
        self.mode = 0
        self.isCamConnected = False
        self.saveCaptureFromCam = False
        self.image = None
        self.fileName = None
        self.lastFrame = None
        # self render params
        self.slice_direction = 0  # Default Slice Direction = Vertical
        self.slice_start_position = 0  # Default Slice Start Position = 0
        self.slice_width = 1  # Default Slice Width = 1
        self.slice_append_side = 0  # Default Slice Append Side = Standard
        # mode 0 slice max params
        self.slice_max_width: int = 1
        self.slice_max_height: int = 1
        # mode 1 slice max params
        self.slice_max_cam_width: int = 1
        self.slice_max_cam_height: int = 1

        # Find ComboBoxes
        self.cb_method = self.findChild(QtWidgets.QComboBox, 'cb_method')
        # Find Buttons
        self.b_clear = self.findChild(QtWidgets.QPushButton, 'b_clear')
        self.b_open = self.findChild(QtWidgets.QPushButton, 'b_open')
        self.b_start = self.findChild(QtWidgets.QPushButton, 'b_start')
        self.b_stop = self.findChild(QtWidgets.QPushButton, 'b_stop')
        self.b_cam_connect = self.findChild(QtWidgets.QPushButton, 'b_cam_connect')
        self.b_save = self.findChild(QtWidgets.QPushButton, 'b_save')
        # Find Group Boxes
        self.gb_main = self.findChild(QtWidgets.QGroupBox, 'gb_main')
        self.gb_file = self.findChild(QtWidgets.QGroupBox, 'gb_file')
        self.gb_webcam = self.findChild(QtWidgets.QGroupBox, 'gb_webcam')
        self.gb_preview = self.findChild(QtWidgets.QGroupBox, 'gb_preview')
        # Find Labels
        self.l_size_info = self.findChild(QtWidgets.QLabel, 'l_size_info')
        self.l_filename = self.findChild(QtWidgets.QLabel, 'l_filename')
        # Find Slice Controls
        self.cb_slice_direction = self.findChild(QtWidgets.QComboBox, 'cb_slice_direction')
        self.sb_slice_start_position = self.findChild(QtWidgets.QSpinBox, 'sb_slice_start_position')
        self.sb_slice_width = self.findChild(QtWidgets.QSpinBox, 'sb_slice_width')
        self.cb_slice_append_side = self.findChild(QtWidgets.QComboBox, 'cb_slice_append_side')
        self.cb_auto_scroll = self.findChild(QtWidgets.QCheckBox, 'cb_auto_scroll')
        # Find Other
        self.vl_preview = self.findChild(QtWidgets.QVBoxLayout, 'vl_preview')
        self.scroll_image = self.findChild(QtWidgets.QScrollArea, 'scroll_image')

        # Connecting events
        self.b_clear.clicked.connect(self.OnClearButtonPressed)
        self.b_open.clicked.connect(self.OnOpenButtonPressed)
        self.b_start.clicked.connect(self.OnStartButtonPressed)
        self.b_stop.clicked.connect(self.OnStopButtonPressed)
        self.b_save.clicked.connect(self.OnSaveButtonPressed)
        self.cb_method.currentIndexChanged.connect(self.OnMethodChange)
        self.b_cam_connect.clicked.connect(self.OnCamConnectButtonPressed)
        # Connecting Slice Elements
        self.cb_slice_direction.currentIndexChanged.connect(self.OnSliceDirectionChanged)
        self.sb_slice_start_position.valueChanged.connect(self.OnSliceStartPositionValueChanged)
        self.sb_slice_width.valueChanged.connect(self.OnSliceWidthValueChanged)
        self.cb_slice_append_side.currentIndexChanged.connect(self.OnSliceAppendSideChanged)

        # Render Image
        self.l_renderImage = StripImageWidget()
        self.scroll_image.setWidget(self.l_renderImage)
        self.scroll_image.horizontalScrollBar().rangeChanged.connect(self.OnResizeScroll)
        self.scroll_image.verticalScrollBar().rangeChanged.connect(self.OnResizeScroll)

        # Set Up Preview Image Container
        self.img_preview = PreviewImageWidget()
        self.vl_preview.addWidget(self.img_preview)

        # Timer For Render From WebCam
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.update_frame)
        self.timer.start(1)

        # preset
        self.gb_webcam.setVisible(False)


    # On Actions Events
    def OnClearButtonPressed(self):
        self.clearImage()

    def OnSaveButtonPressed(self):
        if len(self.l_renderImage.image) != 0:
            options = QFileDialog.Options()
            options |= QFileDialog.DontUseNativeDialog
            fileName, _ = QFileDialog.getSaveFileName(self, "Save file", "",
                                                      "JPEG (*.jpg);;PNG (*.png);;JPEG 2000 (*.jp2);;GIF (*.gif)",
                                                      options=options)
            if fileName:
                if not fileName.endswith(".jpg") and _ == "JPEG (*.jpg)":
                    fileName += ".jpg"
                elif not fileName.endswith(".png") and _ == "PNG (*.png)":
                    fileName += ".png"
                elif not fileName.endswith(".jp2") and _ == "JPEG 2000 (*.jp2)":
                    fileName += ".jp2"
                elif not fileName.endswith(".gif") and _ == "GIF (*.gif)":
                    fileName += ".gif"
                else:
                    fileName += ".jpg"
                img = cv2.cvtColor(self.l_renderImage.image, cv2.COLOR_RGB2BGR)
                cv2.imwrite(fileName, cv2.UMat(img))
        else:
            QtWidgets.QMessageBox.critical(QWidget(), 'Error!', "Image is null!")

    def OnSliceDirectionChanged(self, i):
        self.clearImage()
        self.slice_direction = i

    def OnSliceStartPositionValueChanged(self, i):
        self.slice_start_position = i
        self.updateSliceSettings(self.mode)

    def OnSliceWidthValueChanged(self, i):
        self.slice_width = i

    def OnSliceAppendSideChanged(self, i):
        self.slice_append_side = i

    def OnCamConnectButtonPressed(self):
        global capture_from_cam
        if not self.isCamConnected:
            self.b_cam_connect.setEnabled(False)  # отключаем возможность отключить камеру
            self.b_cam_connect.setText('Connecting...')
            self.isCamConnected = True
            capture_from_cam = True  # включаем capture_thread

            capture = cv2.VideoCapture(0)

            capture_thread = threading.Thread(target=grab, args=(capture, q), daemon=True)
            capture_thread.start()
        else:
            self.gb_main.setEnabled(False)
            capture_from_cam = False
            self.isCamConnected = False  # отключаем capture_thread
            self.b_cam_connect.setText('Connect')

    def OnOpenButtonPressed(self):
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        fileName, _ = QFileDialog.getOpenFileName(self, "Open file", "",
                                                  "Video Files (*.avi *.mkv *.mkv *.mov *.mp4 *.wmv *.webm)",
                                                  options=options)
        if fileName:  # Если файл найден, устанавливаем его в плеер и разблокируем main controls
            self.loadDataFromFileAndUpdateForm(fileName)

    def OnStartButtonPressed(self):
        self.cb_method.setEnabled(False)  # при запущенном скане, отключаем возможность изменять режим
        self.b_start.setEnabled(False)
        if self.mode == 0:
            self.clearImage()
            global capture_from_video
            capture_from_video = True
            videoToImage_thread = threading.Thread(target=videoToImage, args=(self.fileName, self.videoConvertEnd), daemon=True)  # videoToImageThread and callback to VideoConvertEnd
            videoToImage_thread.start()
            self.b_start.setText('Started')
        if self.mode == 1:
            self.saveCaptureFromCam = True  # запускаем сохранение изображения с камеры в update_frame
            self.b_start.setText('Starting...')
        self.b_stop.setEnabled(True)

    def OnStopButtonPressed(self):
        self.b_stop.setEnabled(False)
        if self.mode == 0:
            global capture_from_video
            capture_from_video = False #stoping capture from vide
            pass
        if self.mode == 1:
            self.saveCaptureFromCam = False  # останавливаем сохранение изображения с камеры в update_frame
            self.b_cam_connect.setEnabled(True)  # включаем возможность отключить камеру
        self.b_start.setEnabled(True)
        self.b_start.setText('Start')
        self.cb_method.setEnabled(True)

    def OnMethodChange(self):
        self.mode = self.cb_method.currentIndex()
        self.clearImage()  # Очищаем изображение
        if self.mode == 0:
            self.gb_webcam.setVisible(False)

            self.gb_file.setVisible(True)

            if self.fileName:
                self.loadDataFromFileAndUpdateForm(self.fileName)
            else:
                self.gb_main.setEnabled(False)
                self.setMaximumSliceSizes(1, 1, 0)

        if self.mode == 1:
            self.gb_file.setVisible(False)
            self.gb_webcam.setVisible(True)
            self.img_preview.setVisible(True)

            self.gb_main.setEnabled(
                self.isCamConnected)  # Блокируем основные кнопки взависимости от статуса камеры (проверяем приконекчена ли камера)
            if self.isCamConnected:
                self.setMaximumSliceSizes(self.slice_max_cam_width, self.slice_max_cam_height,
                                          1)  # обновляем максимальные границы
            else:
                self.setMaximumSliceSizes(1, 1, 1)

    def OnResizeScroll(self, mini, maxi):
        if self.cb_auto_scroll.isChecked():
            if self.slice_append_side == 0:
                scrollValue = maxi
            else:
                scrollValue = mini
            if self.slice_direction == 0:
                self.scroll_image.verticalScrollBar().setValue(scrollValue)
            else:
                self.scroll_image.horizontalScrollBar().setValue(scrollValue)

    def videoConvertEnd(self):
        self.b_start.setEnabled(True)
        self.b_stop.setEnabled(False)

    def setMaximumSliceSizes(self, w, h, mode):
        self.l_size_info.setText('Size: ' + str(w) + 'x' + str(h))
        if mode == 0:
            self.slice_max_width = int(w)
            self.slice_max_height = int(h)
        else:
            self.slice_max_cam_width = int(w)
            self.slice_max_cam_height = int(h)
        self.updateSliceSettings(mode)

    def updateSliceSettings(self, mode):
        slice_max_p = 1
        if self.slice_direction == 0:
            if mode == 0:
                slice_max_p = int(self.slice_max_height)
            else:
                slice_max_p = int(self.slice_max_cam_height)
        if self.slice_direction == 1:
            if mode == 0:
                slice_max_p = int(self.slice_max_width)
            else:
                slice_max_p = int(self.slice_max_cam_width)
        self.sb_slice_start_position.setMaximum(slice_max_p - 1)
        self.sb_slice_width.setMaximum(slice_max_p - self.sb_slice_start_position.value() + 1)

    def clearImage(self):
        self.b_save.setEnabled(False)
        self.l_renderImage.image = []
        self.l_renderImage.setPixmap(QPixmap())

    def update_frame(self):
        if not q.empty():
            frame = q.get()
            frame = frame["img"]
            if self.mode == 1:  # обработка камеры
                self.lastFrame = frame

                if self.isCamConnected:
                    self.gb_main.setEnabled(True)
                    self.b_cam_connect.setText('Disconnect')
                    self.b_cam_connect.setEnabled(True)  # включаем возможность отключить камеру

                    if self.saveCaptureFromCam:
                        self.b_cam_connect.setEnabled(False)
                        self.l_renderImage.addImgLine(self.lastFrame, self.slice_start_position, self.slice_width,
                                                      self.slice_direction, self.slice_append_side)

                    # Рисуем на полученной фотографии в preview
                    start_pos = (0, 0)
                    end_pos = (0, 0)
                    if self.slice_direction == 0:
                        start_pos = (0, self.slice_start_position)
                        end_pos = (self.slice_max_cam_width - 1, self.slice_start_position + self.slice_width - 1)
                    if self.slice_direction == 1:
                        start_pos = (self.slice_start_position, 0)
                        end_pos = (self.slice_start_position + self.slice_width - 1, self.slice_max_cam_width - 1)

                    cv2.rectangle(self.lastFrame, start_pos, end_pos, (0, 0, 255), 2)
                    img = cv2.cvtColor(self.lastFrame, cv2.COLOR_BGR2RGB)

                    self.img_preview.setImage(img)
                else:
                    self.gb_main.setEnabled(False)
                    self.b_cam_connect.setEnabled(True)  # включаем возможность отключить камеру

    def loadDataFromFileAndUpdateForm(self, fileName):
        self.fileName = fileName
        capture = cv2.VideoCapture(self.fileName)
        self.setMaximumSliceSizes(capture.get(cv2.CAP_PROP_FRAME_WIDTH), capture.get(cv2.CAP_PROP_FRAME_HEIGHT), 0)

        capture.grab()
        retval, img = capture.retrieve(0)
        self.img_preview.setImage(img)

        self.l_filename.setText(fileName)
        self.gb_main.setEnabled(True)


# Render Image Class Widget
class StripImageWidget(QtWidgets.QLabel):
    def __init__(self, parent=None):
        super(StripImageWidget, self).__init__(parent)

        self.image = []
        self.pixmap = QPixmap()

    def addImgLine(self, addingImage, startCoord=0, width=1, axis=0, append_side=0):

        if width <= 0: width = 1
        if axis == 0:
            addingImage = addingImage[startCoord:startCoord + width, :]
        else:
            addingImage = addingImage[:, startCoord:startCoord + width]

        addingLine = cv2.cvtColor(addingImage, cv2.COLOR_BGR2RGB)  # bgr 2 rgb

        if self.image.__len__() == 0:
            self.image = addingLine
        else:
            if append_side == 0:
                self.image = numpy.concatenate((self.image, addingLine), axis)  # split images
            else:
                self.image = numpy.concatenate((addingLine, self.image), axis)  # split images

        height, width, btp = self.image.shape
        bpl = btp * width

        image = QImage(self.image.data, width, height, bpl, QImage.Format_RGB888)  # array to QImage

        self.pixmap = QPixmap(image)
        self.setPixmap(self.pixmap)  # set Image to view
        q_form.b_save.setEnabled(True)


# Preview Image Class Widget
class PreviewImageWidget(QtWidgets.QLabel):
    def __init__(self, parent=None):
        super(PreviewImageWidget, self).__init__(parent)
        self.setScaledContents(True)
        self.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Ignored)
        self.image = None

    def setImage(self, image):
        self.image = image

        height, width, img_colors = image.shape
        bpl = img_colors * width
        img = QImage(image.data, width, height, bpl, QImage.Format_RGB888)

        pixmap = QPixmap(img)
        self.setPixmap(pixmap)


# Grab image from Capture & send to Queue
def grab(capture, queue):
    global capture_from_cam

    w = capture.get(cv2.CAP_PROP_FRAME_WIDTH)
    h = capture.get(cv2.CAP_PROP_FRAME_HEIGHT)

    q_form.slice_max_width = w
    q_form.slice_max_height = h
    q_form.setMaximumSliceSizes(w, h, 1)

    while capture_from_cam:
        frame = {}
        capture.grab()
        retval, img = capture.retrieve(0)
        frame["img"] = img

        if queue.qsize() < 10:
            queue.put(frame)
        else:
            print(queue.qsize())
    capture.release()


# Convert Video To Strip Image
def videoToImage(url, end_callback):
    # Opens the Video file
    cap = cv2.VideoCapture(url)
    while cap.isOpened() and capture_from_video:
        ret, frame = cap.read()
        if not ret:
            break
        q_form.l_renderImage.addImgLine(frame, q_form.slice_start_position, q_form.slice_width, q_form.slice_direction, q_form.slice_append_side)
    end_callback()
    cap.release()


# Global Vars
capture_from_cam = False
capture_from_video = False
q = Queue()

# Main Thread
if __name__ == '__main__':
    app = QApplication(sys.argv)

    q_form = MainWindow()
    q_form.show()

    sys.exit(app.exec_())
