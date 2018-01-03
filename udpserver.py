import socket
import threading


class UdpServer(threading.Thread):
    def __init__(self, port):
        address = ('0.0.0.0', port)
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind(address)
        self.socket.settimeout(2)
        self.lock = threading.Lock()
        self.data_length = 0
        self.is_exit = False
        super().__init__()

    def run(self):
        self.is_exit = False
        while not self.is_exit:
            try:
                data, _ = self.socket.recvfrom(4096)
                self.lock.acquire()
                self.data_length += len(data)
                self.lock.release()
            finally:
                pass

    def stop(self):
        self.is_exit = True

    def get_recv_length(self):
        self.lock.acquire()
        ret = self.data_length
        self.data_length = 0
        self.lock.release()
        return ret


import time

if __name__ == '__main__':
    udp = UdpServer(10000)
    udp.start()
    for _ in range(5):
        time.sleep(1)
        print("Length: ", udp.get_recv_length())
    udp.stop()
