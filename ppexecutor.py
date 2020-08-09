import time
import multiprocessing


class ProcessPoolExecutor:

    def __init__(self, number):
        self.number = number
        self.processes = []

    def exec(self, func, args):
        while len(self.processes) >= self.number:
            for p in tuple(self.processes):
                if not p.is_alive():
                    self.processes.remove(p)
            if len(self.processes) >= self.number:
                time.sleep(0.1)
        p = multiprocessing.Process(target=func, args=args, daemon=True)
        p.start()
        self.processes.append(p)

    def join(self):
        for p in self.processes:
            p.join()
