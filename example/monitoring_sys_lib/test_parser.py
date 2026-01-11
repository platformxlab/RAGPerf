from common import *

import utils.colored_print as cprint
from utils.logger import logging, Logger
from datetime import datetime, timezone

import os
import argparse

parser = argparse.ArgumentParser()
parser.add_argument(
    "--target_folder",
    default=os.path.join(script_dir, "output"),
    type=str,
    help="Output folder to be analyzed. Default to be in <current_dir>/output",
)

# only parse known args because there could be other arg parsers in the system
args = parser.parse_known_args()[0]

search_dir = os.path.abspath(args.target_folder)
cprint.iprintf(f"Analyze on folder {search_dir}")

# differentiate the exact output folder with output folders with several outputs signified by timestamp
outputs = {
    dir_name: epoch
    for dir_name, epoch in (
        (d, datetime.strptime(d, Logger().dir_time_format).replace(tzinfo=timezone.utc).timestamp())
        for d in os.listdir(search_dir)
        if os.path.isdir(os.path.join(search_dir, d))
    )
}
sorted_outputs = sorted(outputs.items(), key=lambda x: x[1], reverse=True)
assert len(sorted_outputs) > 0, "No output directories found in the specified path."

output_folder_name, time_since_epoch = sorted_outputs[0]
output_folder = os.path.join(search_dir, output_folder_name)
cprint.iprintf(f"Preprocessing output folder: {output_folder}")

data_filenames = [
    filename for filename in os.listdir(output_folder) if filename.endswith(".pb.bin")
]
cprint.iprintf(f"Available data files: {data_filenames}")

import proto.cpu_metrics_pb2 as cpu_metrics_pb2
import proto.gpu_metrics_pb2 as gpu_metrics_pb2
import proto.disk_metrics_pb2 as disk_metrics_pb2
import proto.proc_metrics_pb2 as proc_metrics_pb2
import google.protobuf.message
from typing import Type, TypeVar, BinaryIO


def read_next_buf(msg: google.protobuf.message.Message, f: BinaryIO) -> bool:
    """
    Read the next message from the file. Assumes the file is in the format where
    each message is preceded by its length as an 8-byte little-endian integer.

    Args:
        msg: The protobuf message to fill.
        f: The file object to read from.
    """
    msg_len_bytes = 8
    read_buf = f.read(msg_len_bytes)
    if len(read_buf) == 0:
        return False
    if len(read_buf) < msg_len_bytes:
        raise EOFError("Reached end of file before reading a full message length.")
    msg_len = int.from_bytes(read_buf, byteorder="little")
    act_len = msg.ParseFromString(f.read(msg_len))
    assert act_len == msg_len, f"Expected to read {msg_len} bytes, but got {act_len} bytes."
    return True


T = TypeVar("T", bound=google.protobuf.message.Message)


def extract_time_series(data_file: str, message_type: Type[T]) -> T:
    whole_msg = message_type()
    with open(data_file, "rb") as f:
        msg = message_type()
        while read_next_buf(msg, f):
            whole_msg.MergeFrom(msg)
    return whole_msg


import utils.colored_print as cprint
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick

window_size = 5
smooth_filter = np.ones(window_size, dtype=np.float64) / window_size
smoothing = True

for data_filename in data_filenames:
    if data_filename.startswith("CPUMeter"):
        cprint.iprintf("Generating figures for CPU metrics...")
        data_file = os.path.join(output_folder, data_filename)
        msg = extract_time_series(data_file, cpu_metrics_pb2.CPUMetricsTimeSeries)

        nfields = len(cpu_metrics_pb2.CoreStat.DESCRIPTOR.fields)
        ntslices = len(msg.metrics)

        timestamps = np.empty(ntslices, dtype=np.int64)
        result = np.empty((nfields, ntslices), dtype=np.int64)

        for metric_idx, metric in enumerate(msg.metrics):
            timestamps[metric_idx] = metric.timestamp
            for field_idx, field in enumerate(cpu_metrics_pb2.CoreStat.DESCRIPTOR.fields):
                result[field_idx, metric_idx] = getattr(metric.core_stats[0], field.name)
        result_processed = np.array([result[:, i] - result[:, i - 1] for i in range(1, ntslices)]).T

        # normalize ntslices
        result = result_processed / np.sum(result_processed, axis=0) * 100
        if smoothing:
            # apply smoothing filter
            result = np.apply_along_axis(
                lambda x: np.convolve(x, smooth_filter, mode='same'), axis=1, arr=result
            )

        # remove the first timestamp as it is the base
        timestamps = timestamps[
            1:
        ]  # remove the first timestamp as it is not used in result_processed
        timestamps = (
            timestamps - timestamps[0]
        ) / 1e9  # normalize timestamps to start from 0 and convert to seconds
        labels = [field.name for field in cpu_metrics_pb2.CoreStat.DESCRIPTOR.fields]

        cprint.iprintf(f"Last timestamp: {timestamps[-1]}")

        fig = plt.figure(figsize=(12, 6))
        ax = plt.subplot(111)
        # print(result.shape, result_processed.shape, timestamps.shape)
        ax.stackplot(timestamps, result, labels=labels)
        fig.legend(loc='upper center', ncol=len(labels), bbox_to_anchor=(0.5, 0.95))
        ax.set_xlabel("Timestamp (s)")
        ax.set_ylabel("Percentage of CPU Usage (%)")
        ax.set_xlim(0, timestamps[-1])
        ax.set_ylim(0, 15)
        ax.yaxis.set_major_formatter(mtick.PercentFormatter())
        fig.savefig(f"{data_filename}.png", dpi=300, bbox_inches='tight')
        cprint.iprintf(f"CPU metrics figure saved to {data_filename}.png")

    if data_filename.startswith("GPUMeter"):
        cprint.iprintf("Generating figures for GPU metrics...")
        colors = ["#57B4E9", "#019E73", "#E69F00", "#0072B2", "#B21000", "#5B0680"]
        linestyles = ['-', '--', '-.', ':', "-"]
        data_file = os.path.join(output_folder, data_filename)
        msg = extract_time_series(data_file, gpu_metrics_pb2.GPUMetricsTimeSeries)
        ts = np.array(
            [1757098153657814454, 1757098155015994472, 1757098167621610434, 1757098249092188605]
        )

        nfields = len(msg.metrics[0].per_gpu_metrics[0].GPM_metrics_values)
        ntslices = len(msg.metrics)

        timestamps = np.empty(ntslices, dtype=np.int64)
        result = np.empty((nfields, ntslices), dtype=np.float64)
        for metric_idx, metric in enumerate(msg.metrics):
            timestamps[metric_idx] = metric.timestamp
            for field_idx in range(nfields):
                result[field_idx, metric_idx] = metric.per_gpu_metrics[
                    gpu_id := 0
                ].GPM_metrics_values[field_idx]
        # normalize ntslices
        # result = result / np.sum(result, axis=0) * 100
        if smoothing:
            # apply smoothing filter
            result = np.apply_along_axis(
                lambda x: np.convolve(x, smooth_filter, mode='same'), axis=1, arr=result
            )
        ts_rectified = (ts - ts[0]) / 1e9
        timestamps = (timestamps - timestamps[0]) / 1e9
        labels = [field.name for field in gpu_metrics_pb2.GPUMetrics.DESCRIPTOR.fields]
        fig = plt.figure(figsize=(12, 8))

        cprint.iprintf(f"Last timestamp: {timestamps[-1]}")

        ax = plt.subplot(411)
        ax.plot(timestamps, result[0], label="SM Utilization", color=colors[0], linewidth=1)
        ax.plot(timestamps, result[1], label="SM Occupancy", color=colors[1], linewidth=1)
        ax.set_xlabel("Timestamp (s)")
        ax.set_ylabel("Utilization (%)")
        ax.legend(loc='upper right', ncols=10)
        ax.set_xlim(0, timestamps[-1])
        ax.set_ylim(0, 20)
        ax.axhline(y=100, color='black', linestyle='--', linewidth=1)
        ax.yaxis.grid(color='lightgray', linestyle='--', linewidth=0.7)
        for t in ts_rectified:
            ax.axvline(x=t, color='black', linestyle='--', linewidth=1)
        ax.set_xticks(range(0, int(timestamps[-1]) + 1, 5))

        ax = plt.subplot(412)
        ax.plot(timestamps, result[2], label="PCIe TX", color=colors[0], linewidth=1)
        ax.plot(timestamps, result[3], label="PCIe RX", color=colors[1], linewidth=1)
        ax.set_xlabel("Timestamp (s)")
        ax.set_ylabel("Throughput (MB/s)")
        ax.legend(loc='upper right', ncols=10)
        ax.set_xlim(0, timestamps[-1])
        ax.set_ylim(0, 150)
        ax.yaxis.grid(color='lightgray', linestyle='--', linewidth=0.7)
        for t in ts_rectified:
            ax.axvline(x=t, color='black', linestyle='--', linewidth=1)
        ax.set_xticks(range(0, int(timestamps[-1]) + 1, 5))

        ax = plt.subplot(413)
        ax.plot(
            timestamps,
            result[4],
            label="DRAM BW Utilization",
            color=colors[0],
            linestyle=linestyles[0],
        )
        ax.set_xlabel("Timestamp (s)")
        ax.set_ylabel("Utilization (%)")
        ax.set_xlim(0, timestamps[-1])
        ax.set_ylim(0, 105)
        ax.legend(loc='upper right', ncols=10)
        ax.yaxis.grid(color='lightgray', linestyle='--', linewidth=0.7)
        for t in ts_rectified:
            ax.axvline(x=t, color='black', linestyle='--', linewidth=1)
        ax.set_xticks(range(0, int(timestamps[-1]) + 1, 5))

        ax = plt.subplot(414)
        ax.plot(timestamps, result[5], label="Integer Utilization", color=colors[0], linewidth=1)
        ax.plot(timestamps, result[6], label="FP16 Utilization", color=colors[1], linewidth=1)
        ax.plot(timestamps, result[7], label="FP32 Utilization", color=colors[2], linewidth=1)
        ax.plot(timestamps, result[8], label="FP64 Utilization", color=colors[3], linewidth=1)
        ax.set_xlabel("Timestamp (s)")
        ax.set_ylabel("Utilization (%)")
        ax.legend(loc='upper right', ncols=10)
        ax.set_xlim(0, timestamps[-1])
        ax.set_ylim(0, 5)
        ax.axhline(y=100, color='black', linestyle='--', linewidth=1)
        ax.yaxis.grid(color='lightgray', linestyle='--', linewidth=0.7)
        for t in ts_rectified:
            ax.axvline(x=t, color='black', linestyle='--', linewidth=1)
        ax.set_xticks(range(0, int(timestamps[-1]) + 1, 5))

        fig.savefig(f"{data_filename}.png", dpi=300, bbox_inches='tight')
        cprint.iprintf(f"GPU metrics figure saved to {data_filename}.png")
