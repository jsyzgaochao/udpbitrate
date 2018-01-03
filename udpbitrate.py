import sys
import os
import re
import json
from PyQt5.Qt import QPainter
from PyQt5.QtCore import Qt, QTimer, QPointF
from PyQt5.QtWidgets import QWidget, QApplication
from PyQt5.QtWidgets import QVBoxLayout, QHBoxLayout, QGridLayout
from PyQt5.QtWidgets import QLabel, QLineEdit, QPushButton, QCheckBox
from PyQt5.QtWidgets import QFileDialog
from PyQt5.QtChart import QChart, QChartView, QLineSeries
from udpserver import UdpServer

class UDPBitrate(QWidget):
    def __init__(self):
        super().__init__()

        self.mainLayout = QVBoxLayout()
        self.headerLayout = QGridLayout()
        self.portLayout = QHBoxLayout()
        self.axisxLayout = QHBoxLayout()
        self.axisyLayout = QHBoxLayout()
        self.btnsLayout = QHBoxLayout()
        self.lblPort = QLabel("Port: ")
        self.lblAxisX = QLabel("X-Axis(Time): ")
        self.lblAxisY = QLabel("Y-Axis(Bitrate): ")
        self.txtPort = QLineEdit()
        self.txtAxisX = QLineEdit()
        self.txtAxisY = QLineEdit()
        self.chkMode = QCheckBox("Stack Mode")
        self.btnStart = QPushButton("Start")
        self.btnExport = QPushButton("Export")
        self.btnStart.clicked.connect(self.onStartClick)
        self.btnExport.clicked.connect(self.onExportClick)

        self.portLayout.addWidget(self.lblPort)
        self.portLayout.addWidget(self.txtPort)

        self.axisxLayout.addWidget(self.lblAxisX)
        self.axisxLayout.addWidget(self.txtAxisX)

        self.axisyLayout.addWidget(self.lblAxisY)
        self.axisyLayout.addWidget(self.txtAxisY)

        self.btnsLayout.addWidget(self.chkMode)
        self.btnsLayout.addWidget(self.btnStart)
        self.btnsLayout.addWidget(self.btnExport)

        self.headerLayout.addLayout(self.portLayout, 0, 0, 1, 4)
        self.headerLayout.addLayout(self.axisxLayout, 0, 4, 1, 3)
        self.headerLayout.addLayout(self.axisyLayout, 0, 7, 1, 3)
        self.headerLayout.addLayout(self.btnsLayout, 0, 10, 1, 2)

        self.chart = QChart()
        self.chartview = QChartView(self.chart)
        self.chartview.setRenderHint(QPainter.HighQualityAntialiasing)
        self.chart.legend().setAlignment(Qt.AlignBottom)
        self.chart.setTitle("UDP Bitrate")

        self.mainLayout.addLayout(self.headerLayout)
        self.mainLayout.addWidget(self.chartview)

        self.timer = QTimer()
        self.timer.timeout.connect(self.onTimeOut)

        self.axis_x_unit_str = ["Sec", "Min", "Hour", "Day"]
        self.axis_y_unit_str = ["bps", "Kbps", "Mbps", "Gbps"]
        self.axis_x_unit_scale = [1, 60, 3600, 3600*24]
        self.axis_y_unit_scale = [1, 1e3, 1e6, 1e9]
        self.axis_x_default_resolution = 1000

        self.ports = []
        self.udpthreads = []

        if os.path.exists("udpbitrate.conf"):
            with open("udpbitrate.conf", "r") as fp:
                try:
                    json_data = json.load(fp)
                    self.txtPort.setText(json_data.get("port",""))
                    self.txtAxisX.setText(json_data.get("x-axis",""))
                    self.txtAxisY.setText(json_data.get("y-axis",""))
                    self.chkMode.setChecked(json_data.get("mode",False))
                finally:
                    pass

        self.setWindowTitle("UDP Bitrate")
        self.setLayout(self.mainLayout)
        self.resize(960, 600)
        self.show()

    def onStartClick(self):
        if self.btnStart.text() == "Start":
            self.btnStart.setText("Stop")
            self.chkMode.setEnabled(False)
            self.txtPort.setEnabled(False)
            self.txtAxisX.setEnabled(False)
            self.txtAxisY.setEnabled(False)
            self.parse_port()
            self.parse_axis_x()
            self.parse_axis_y()
            self.start_record()
            json_data = {"port":self.txtPort.text(),
                         "x-axis":self.txtAxisX.text(),
                         "y-axis":self.txtAxisY.text(),
                         "mode":self.chkMode.isChecked()}
            with open("udpbitrate.conf", "w") as fp:
                json.dump(json_data, fp)
        else:
            self.btnStart.setText("Start")
            self.chkMode.setEnabled(True)
            self.txtPort.setEnabled(True)
            self.txtAxisX.setEnabled(True)
            self.txtAxisY.setEnabled(True)
            self.stop_record()

    def onExportClick(self):
        image = QApplication.primaryScreen().grabWindow(self.chartview.winId()).toImage()
        filename, filetype = QFileDialog.getSaveFileName(self, "Export Image", "./udpbitrate.png",
                                               "PNG Files (*.png);;JEPG Files (*.jpg);;All Files (*)")
        if filename:
            ext = ".jpg" if ".jpg" in filetype else ".png"
            filename = filename + ext if ext not in filename else filename
            image.save(filename)


    def onTimeOut(self):
        if self.chkMode.isChecked():
            bitrate = 0
            for i in range(len(self.udpthreads)):
                length = float(self.udpthreads[i].get_recv_length())
                bitrate += length * 8.0 / self.axis_x_step / self.axis_y_unit_scale[self.axis_y_unit]
                self.add_point(bitrate, self.chart.series()[i])
        else:
            total_bitrate = 0
            for i in range(len(self.udpthreads)):
                length = float(self.udpthreads[i].get_recv_length())
                bitrate = length * 8.0 / self.axis_x_step / self.axis_y_unit_scale[self.axis_y_unit]
                total_bitrate += bitrate
                self.add_point(bitrate, self.chart.series()[i])
            self.add_point(total_bitrate, self.chart.series()[-1])

    def add_point(self, val, series):
        points = series.pointsVector()
        if len(points) <= self.axis_x_resolution:
            points.append(QPointF(len(points) * self.axis_x_step / self.axis_x_unit_scale[self.axis_x_unit], val))
        else:
            for i in range(len(points)-1):
                points[i] = QPointF(i * self.axis_x_step / self.axis_x_unit_scale[self.axis_x_unit], points[i+1].y())
            points[-1] = QPointF(len(points) * self.axis_x_step / self.axis_x_unit_scale[self.axis_x_unit], val)
        series.replace(points)

    def parse_port(self):
        self.ports = []
        s = self.txtPort.text()
        sl = map(str.strip, s.split(','))
        p = re.compile('^(\d+)\s?-\s?(\d+)$|^(\d+)$')
        for ss in sl:
            m = p.match(ss)
            if m:
                if m.group(3):
                    cur = int(m.group(3))
                    if len(self.ports) > 16:
                        break
                    if cur > 0:
                        self.ports.append(cur)
                else:
                    start, end = int(m.group(1)), int(m.group(2))
                    for cur in range(start, end+1):
                        if len(self.ports) > 16:
                            break
                        if cur > 0:
                            self.ports.append(cur)

    def parse_axis_x(self):
        self.axis_x_val = 0
        self.axis_x_unit = 0
        s = self.txtAxisX.text().lower()
        p = re.compile('^(\d+(?:\.\d+)?)\s?(s(?:ec)?|m(?:in)?|h(?:our)?|d(?:ay)?)?$')
        m = p.match(s)
        if m:
            self.axis_x_val = float(m.group(1))
            if m.group(2):
                if m.group(2) == "s" or m.group(2) == "sec":
                    self.axis_x_unit = 0
                elif m.group(2) == "m" or m.group(2) == "min":
                    self.axis_x_unit = 1
                elif m.group(2) == "h" or m.group(2) == "hour":
                    self.axis_x_unit = 2
                elif m.group(2) == "d" or m.group(2) == "day":
                    self.axis_x_unit = 3
        self.axis_x_step = self.axis_x_val * self.axis_x_unit_scale[self.axis_x_unit] / self.axis_x_default_resolution
        if self.axis_x_step < 0.1:
            self.axis_x_resolution = int(10 * self.axis_x_val * self.axis_x_unit_scale[self.axis_x_unit])
            self.axis_x_step = self.axis_x_val * self.axis_x_unit_scale[self.axis_x_unit] / self.axis_x_resolution
        else:
            self.axis_x_resolution = self.axis_x_default_resolution

    def parse_axis_y(self):
        self.axis_y_val = 0
        self.axis_y_unit = 0
        s = self.txtAxisY.text().lower()
        p = re.compile('^(\d+(?:\.\d+)?)\s?(k|m|g)?$')
        m = p.match(s)
        if m:
            self.axis_y_val = float(m.group(1))
            if m.group(2):
                if m.group(2) == "k":
                    self.axis_y_unit = 1
                elif m.group(2) == "m":
                    self.axis_y_unit = 2
                elif m.group(2) == "g":
                    self.axis_y_unit = 3

    def start_record(self):
        self.chart.removeAllSeries()
        self.series = []

        try:
            for port in self.ports:
                udp = UdpServer(port)
                udp.start()
                self.udpthreads.append(udp)
                series = QLineSeries()
                series.setName(str(port))
                self.chart.addSeries(series)
        finally:
            pass

        if not self.chkMode.isChecked():
            series = QLineSeries()
            series.setName("Total")
            self.chart.addSeries(series)

        self.chart.createDefaultAxes()

        axis_x = self.chart.axisX()
        axis_x.setRange(0, self.axis_x_val)
        axis_x.setLabelFormat("%g")
        axis_x.setTitleText("Time / " + self.axis_x_unit_str[self.axis_x_unit])

        axis_y = self.chart.axisY()
        axis_y.setRange(0, self.axis_y_val)
        axis_y.setLabelFormat("%g")
        axis_y.setTitleText("Bitrate / " + self.axis_y_unit_str[self.axis_y_unit])

        self.timer.start(self.axis_x_step * 1000)

    def stop_record(self):
        if self.timer.isActive():
            self.timer.stop()
        for udp in self.udpthreads:
            udp.stop()
        self.udpthreads = []

if __name__ == '__main__':
    app = QApplication(sys.argv)
    udpbitrate = UDPBitrate()
    sys.exit(app.exec_())
