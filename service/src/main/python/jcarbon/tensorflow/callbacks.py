import os
import time
import pandas as pd

from tensorflow.keras.callbacks import Callback

from jcarbon.client import JCarbonClient
from jcarbon.report import to_dataframe

from jcarbon.nvml.sampler import create_report, NvmlSampler

DEFAULT_PERIOD_MS = 10
DEFAULT_PERIOD_SECS = 2
DEFAULT_SIGNALS = [
    'nvml',
    'linux_process',
    'JOULES',
    'GRAMS_OF_CO2',
]
UNITS = {
    'GRAMS_OF_CO2': 'CO2',
    'JOULES': 'J',
    'ACTIVITY': '%',
    'NANOSECONDS': 'ns',
    'JIFFIES': '',
    'WATTS': 'W',
}


def add_jcarbon_log(df, logs=None):
    if logs:
        for (component_type, component_id, unit, source), df in df.groupby(['component_type', 'component_id', 'unit', 'source']):
            # TODO: this should really not ignore negatives
            if unit == 'JOULES':
                logs[f'{component_type}-{UNITS[unit]}'] = df[df > 0].sum()


class JCarbonCallback(Callback):
    def __init__(
            self,
            addr,
            period_ms=DEFAULT_PERIOD_MS,
            signals=DEFAULT_SIGNALS):
        self.pid = os.getpid()
        self.client = JCarbonClient(addr)
        self.period_ms = period_ms
        self.signals = signals

    def start_jcarbon(self):
        self.client.purge()
        self.client.start(self.pid, self.period_ms)

    def stop_jcarbon(self):
        self.client.stop(self.pid)
        # return to_dataframe(self.client.read(self.pid, self.signals))
        return self.client.read(self.pid, self.signals)


# TODO: these two benchmarks exist for completeness; always use the chunking callback.
# TODO: we need the streaming response rpc for this
class JCarbonEpochCallback(JCarbonCallback):
    def __init__(self, addr='localhost:8980', period_ms=DEFAULT_PERIOD_MS, signals=DEFAULT_SIGNALS):
        super().__init__(addr, period_ms, signals)
        self.reports = {}

    def on_epoch_begin(self, epoch, logs=None):
        self.start_jcarbon()

    def on_epoch_end(self, epoch, logs=None):
        self.reports[epoch] = to_dataframe(self.stop_jcarbon())
        add_jcarbon_log(self.reports[epoch], logs)

# TODO: this kills performance due to the GRPC layer
class JCarbonBatchCallback(JCarbonCallback):
    def __init__(self, addr='localhost:8980', period_ms=DEFAULT_PERIOD_MS, signals=DEFAULT_SIGNALS):
        super().__init__(addr, period_ms, signals)
        self.reports = {}

    def on_train_batch_begin(self, epoch, logs=None):
        self.start_jcarbon()
        self.reports[epoch] = []

    def on_train_batch_end(self, epoch, logs=None):
        self.reports[epoch].append(to_dataframe(self.stop_jcarbon()))
        add_jcarbon_log(self.reports[epoch], logs)


class JCarbonChunkingCallback(JCarbonCallback):
    def __init__(
            self,
            addr='localhost:8980',
            period_ms=DEFAULT_PERIOD_MS,
            signals=DEFAULT_SIGNALS,
            chunking_period_sec=DEFAULT_PERIOD_SECS):
        super().__init__(addr, period_ms, signals)
        self.reports = {}
        self.chunking_period_sec = chunking_period_sec

    def on_epoch_begin(self, epoch, logs=None):
        self.time = time.time()
        self.last_report = None
        self.start_jcarbon()

    def on_train_batch_end(self, epoch, logs=None):
        curr = time.time()
        if (curr - self.time > self.chunking_period_sec):
            self.time = curr
            if self.last_report is None:
                self.last_report = to_dataframe(self.stop_jcarbon())
            else:
                self.last_report = pd.concat([
                    self.last_report,
                    to_dataframe(self.stop_jcarbon()),
                ])
            add_jcarbon_log(self.last_report, logs)
            self.start_jcarbon()

    def on_epoch_end(self, epoch, logs=None):
        if self.last_report is None:
            self.last_report = to_dataframe(self.stop_jcarbon())
        else:
            self.last_report = pd.concat([
                self.last_report,
                to_dataframe(self.stop_jcarbon()),
            ])
        add_jcarbon_log(self.last_report, logs)
        self.reports[epoch] = self.last_report.to_frame().assign(
            epoch=epoch).set_index('epoch', append=True)

class JCarbonExperimentCallback(JCarbonChunkingCallback):
    def __init__(
            self,
            addr='localhost:8980',
            period_ms=DEFAULT_PERIOD_MS,
            signals=DEFAULT_SIGNALS,
            chunking_period_sec=DEFAULT_PERIOD_SECS):
        super().__init__(addr, period_ms, signals)
        self.timestamps = {}
        self.batch_timestamps = None

    def on_epoch_begin(self, epoch, logs=None):
        super().on_epoch_begin(epoch)
        self.curr_batch_timestamps = None
    
    def on_train_batch_begin(self, batch, logs=None):
        self.batch_start = time.time()
        super().on_train_batch_begin(batch)
        
        
    def on_train_batch_end(self, batch, logs=None):
        curr = time.time()
        super().on_train_batch_end(batch)
        self.batch_end = int((10**9 * curr))
        self.batch_start = int((10**9 * self.batch_start))
        if self.curr_batch_timestamps is None:
            self.curr_batch_timestamps = [{'batch': batch, 'start': self.batch_start, 'end': self.batch_end}]
        else:
            self.curr_batch_timestamps.append({'batch': batch, 'start': self.batch_start, 'end': self.batch_end})

    def on_epoch_end(self, epoch, logs=None):
        super().on_epoch_end(epoch)
        if self.batch_timestamps is None:
            self.batch_timestamps = pd.DataFrame.from_dict(self.curr_batch_timestamps)
        else:
            self.batch_timestamps = pd.concat([pd.DataFrame.from_dict(self.curr_batch_timestamps)])
        self.timestamps[epoch] = self.batch_timestamps.assign(
            epoch=epoch)


class JCarbonChunkingCallback2(JCarbonCallback):
    def __init__(
            self,
            addr='localhost:8980',
            period_ms=DEFAULT_PERIOD_MS,
            signals=DEFAULT_SIGNALS,
            chunking_period_sec=DEFAULT_PERIOD_SECS):
        super().__init__(addr, period_ms, signals)
        self.reports = {}
        self.chunking_period_sec = chunking_period_sec

    def on_epoch_begin(self, epoch, logs=None):
        self.time = time.time()
        self.last_report = None
        self.start_jcarbon()

    def on_train_batch_end(self, epoch, logs=None):
        curr = time.time()
        if (curr - self.time > self.chunking_period_sec):
            self.time = curr
            if self.last_report is None:
                self.last_report = [self.stop_jcarbon()]
            else:
                self.last_report.append(self.stop_jcarbon())
            self.start_jcarbon()

    def on_epoch_end(self, epoch, logs=None):
        if self.last_report is None:
            self.last_report = [self.stop_jcarbon()]
        else:
            self.last_report.append(self.stop_jcarbon())
        self.reports[epoch] = pd.concat(list(map(
            to_dataframe,
            self.last_report
        ))).to_frame().assign(
            epoch=epoch).set_index('epoch', append=True)


# TODO: we need the streaming response rpc for this
class JCarbonDumpingEpochCallback(JCarbonCallback):
    def __init__(
            self,
            addr='localhost:8980',
            period_ms=DEFAULT_PERIOD_MS,
            signals=DEFAULT_SIGNALS,
            output_path=None):
        super().__init__(addr, period_ms, signals)
        if output_path is None:
            self.output_path = f'/tmp/jcarbon-{os.getpid()}'
        else:
            self.output_path = output_path

    def on_epoch_begin(self, epoch, logs=None):
        self.start_jcarbon()

    def on_epoch_end(self, epoch, logs=None):
        self.client.stop(self.pid)
        self.client.dump(
            self.pid, f'{self.output_path}/report-{epoch}.pb', self.signals)

class JCarbonNvmlCallback():
    def __init__(
            self,
            addr='localhost:8980',
            period_ms=DEFAULT_PERIOD_MS,
            signals=DEFAULT_SIGNALS,
            chunking_period_sec=DEFAULT_PERIOD_SECS):
        # super().__init__(addr, period_ms, signals)
        self.reports = {}
        self.sampler = NvmlSampler()
    
    def on_epoch_begin(self, epoch, logs = None):
        self.last_report = None
        self.sampler.sample()
    
    def on_epoch_end(self, epoch, logs = None):
        self.sampler.sample()
        if self.last_report is None:
            self.last_report = [create_report(self.sampler.samples)]
        else:
            self.last_report.append(create_report(self.sampler.samples))

        # self.reports[epoch] = pd.concat(list(map(
        #     to_dataframe,
        #     self.last_report
        # ))).to_frame().assign(
        #     epoch=epoch).set_index('epoch', append=True)

