from common import *

from datetime import datetime, timezone

import os
import itertools

include_path = os.path.join(os.path.dirname(__file__), "..", "..", "src", "proto")
include_path = os.path.abspath(include_path)
print(include_path)
# print(os.abspath(path=include_path))
sys.path.append(include_path)

import cpu_metrics_pb2 as cpu_metrics_pb2
import gpu_metrics_pb2 as gpu_metrics_pb2
import disk_metrics_pb2 as disk_metrics_pb2
import proc_metrics_pb2 as proc_metrics_pb2
import mem_metrics_pb2 as mem_metrics_pb2
import google.protobuf.message
from typing import Type, TypeVar, BinaryIO

import utils.colored_print as cprint
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick

search_dir = os.path.join(os.path.dirname(__file__), "output")
search_dir = os.path.abspath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, os.pardir, "src", "output")
)
print(f"Searching output folders in: {search_dir}")
outputs = {
    dir_name: epoch
    for dir_name, epoch in (
        # (d, datetime.strptime(d, "%Y-%m-%dT%H:%M:%S%z").replace(tzinfo=timezone.utc).timestamp())
        # for d in os.listdir(search_dir)
        # if os.path.isdir(os.path.join(search_dir, d))
        (d, 0)
        for d in os.listdir(search_dir)
    )
}
sorted_outputs = sorted(outputs.items(), key=lambda x: x[1], reverse=True)
assert len(sorted_outputs) > 0, "No output directories found in the specified path."
# print(sorted_outputs)

# x_pos = []
# # REPLACE FILENAME WITH CORRESPONDING GRAPHING OUTPUT
# filename = "src/output/2025-10-18T18:43:27-0500"
# with open(f"../../../{filename}/time_break_down.txt", 'r') as file:
#     for line in file:
#         s = (str)(line)
#         x_pos.append(s)

# start_time = 0


# def draw_lines(ax, x_pos):
#     for i in range(len(x_pos)):
#         s = x_pos[i]
#         index = s.index(",")
#         tag = s[0:index]
#         time = (int)(s[index + 2 : len(s)]) / (10**9)

#         if i == 0:
#             start_time = time


#         ax.axvline(x=time - start_time, color='r', linestyle='--')
#         ax.text(time - start_time, 0, tag, fontsize=6, rotation=90)
def draw_lines(ax, x_pos, min_spacing=0.5):
    """
    Draw red dashed vertical lines with non-overlapping text labels.
    If two lines are close (within min_spacing seconds), their text is shown
    at different y-levels to avoid overlap.
    """
    # --- Parse lines safely ---
    parsed = []
    for s in x_pos:
        try:
            idx = s.index(",")
            tag = s[:idx].strip()
            t = int(s[idx + 1 :].strip()) / 1e9
            parsed.append((tag, t))
        except Exception:
            continue
    if not parsed:
        return
    print(f"Drawing {parsed} event lines.")
    start_time = parsed[0][1]
    y_min, y_max = ax.get_ylim()
    y_range = y_max - y_min

    # Vertical positions to cycle through for close events
    y_levels = [
        y_min + 0.02 * y_range,
        y_min + 0.08 * y_range,
        y_min + 0.14 * y_range,
        y_min + 0.20 * y_range,
    ]

    last_x = -float("inf")
    level_idx = 0

    for tag, t in parsed:
        xpos = t - start_time

        # --- Draw vertical line ---
        ax.axvline(x=xpos, color='red', linestyle='--', linewidth=1.0, alpha=0.8)

        # --- Adjust text vertical level if lines are close ---
        if xpos - last_x < min_spacing:
            level_idx = (level_idx + 1) % len(y_levels)
        else:
            level_idx = 0
        y_text = y_levels[level_idx]
        last_x = xpos
        # print(y_max)
        # --- Draw label ---
        ax.text(
            xpos + 0.05,  # small horizontal offset
            1,
            tag,
            fontsize=7,
            rotation=60,
            color='black',
            va='bottom',
            ha='left',
            backgroundcolor='white',
            bbox=dict(facecolor='white', edgecolor='none', pad=0.4, alpha=0.7),
            clip_on=True,
        )

    # ax.set_ylim(y_min, y_max)


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


window_size = 5
smooth_filter = np.ones(window_size, dtype=np.float64) / window_size
smoothing = False

for output_run in sorted_outputs:

    output_folder_name, time_since_epoch = output_run
    output_folder = os.path.join(search_dir, output_folder_name)
    print(f"Preprocessing output folder: {output_folder}")

    data_file_names = [
        filename for filename in os.listdir(output_folder) if filename.endswith(".pb.bin")
    ]
    # data_file_names = [filename for filename in os.listdir(output_folder) if filename.endswith(".data")]
    print(data_file_names)
    timebreak_file = os.path.join(output_folder, "time_break_down.txt")
    x_pos = []
    if not os.path.exists(timebreak_file):
        cprint.iprintf(f"Time break down file not found: {timebreak_file}")
        continue
    with open(timebreak_file, 'r') as file:
        for line in file:
            s = (str)(line)
            x_pos.append(s)

    start_time = 0

    for data_file_name in data_file_names:
        if data_file_name.startswith("CPUMeter"):
            colors = [
                "#57B4E9",
                "#019E73",
                "#E69F00",
                "#FFFFFF",
                "#B11000",
                "#5B2680",
                "#56B449",
                "#329E73",
                "#463F80",
            ]
            cprint.iprintf("Generating figures for CPU metrics...")
            data_file = os.path.join(output_folder, data_file_name)
            msg = extract_time_series(data_file, cpu_metrics_pb2.CPUMetricsTimeSeries)

            nfields = len(cpu_metrics_pb2.CoreStat.DESCRIPTOR.fields)
            ntslices = len(msg.metrics)

            timestamps = np.empty(ntslices, dtype=np.int64)
            result = np.empty((nfields, ntslices), dtype=np.int64)

            for metric_idx, metric in enumerate(msg.metrics):
                timestamps[metric_idx] = metric.timestamp
                for field_idx, field in enumerate(cpu_metrics_pb2.CoreStat.DESCRIPTOR.fields):
                    result[field_idx, metric_idx] = getattr(metric.core_stats[0], field.name)
            result_processed = np.array(
                [result[:, i] - result[:, i - 1] for i in range(1, ntslices)]
            ).T

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

            fig = plt.figure(figsize=(10, 4))
            ax = plt.subplot(111)

            # vertical lines
            draw_lines(ax, x_pos)

            ax.stackplot(timestamps, result, colors=colors, labels=labels)
            fig.legend(loc='upper center', ncol=len(labels) // 2, bbox_to_anchor=(0.5, 1.05))
            ax.set_xlabel("Timestamp (s)")
            ax.set_ylabel("Percentage of CPU Usage (%)")
            ax.set_xlim(0, timestamps[-1])
            ax.set_ylim(0, 100)
            ax.yaxis.set_major_formatter(mtick.PercentFormatter())
            # fig.savefig(f"{data_file_name}_{output_folder_name}.png", dpi=300, bbox_inches='tight')
            save_path = os.path.join(output_folder, f"{data_file_name}.png")
            fig.savefig(save_path, dpi=300, bbox_inches='tight')
            cprint.iprintf(f"CPU metrics figure saved to {data_file_name}.png")
            plt.close(fig)

        if data_file_name.startswith("GPUMeter"):
            cprint.iprintf("Generating figures for GPU metrics...")
            colors = ["#57B4E9", "#019E73", "#E69F00", "#0072B2", "#B21000", "#5B0680"]
            linestyles = ['-', '--', '-.', ':', "-"]
            data_file = os.path.join(output_folder, data_file_name)
            msg = extract_time_series(data_file, gpu_metrics_pb2.GPUMetricsTimeSeries)
            ts = np.array(
                [1757098153657814454, 1757098155015994472, 1757098167621610434, 1757098249092188605]
            )
            # print(msg.metrics[100])
            ntslices = len(msg.metrics)
            if ntslices < 1:
                cprint.iprintf("No GPU metrics data found, skipping...")
                continue
            nfields = len(msg.metrics[0].per_gpu_metrics[0].GPM_metrics_values)
            print(msg.metrics[0])

            timestamps = np.empty(ntslices, dtype=np.int64)
            result = np.empty((nfields, ntslices), dtype=np.float64)
            mem = np.zeros((2, 128, ntslices), dtype=np.int64)
            for metric_idx, metric in enumerate(msg.metrics):
                timestamps[metric_idx] = metric.timestamp
                for field_idx in range(nfields):
                    result[field_idx, metric_idx] = metric.per_gpu_metrics[
                        gpu_id := 0
                    ].GPM_metrics_values[field_idx]
                if metric.per_gpu_metrics[0].per_process_gpu_metrics:
                    for id, proc in enumerate(metric.per_gpu_metrics[0].per_process_gpu_metrics):
                        if id < mem.shape[1]:
                            mem[0, id, metric_idx] = proc.used_gpu_memory
                # else:
                #     mem[0, 0, metric_idx] = 0
                if metric.per_gpu_metrics[1].per_process_gpu_metrics:
                    for id, proc in enumerate(metric.per_gpu_metrics[1].per_process_gpu_metrics):
                        if id < mem.shape[1]:
                            mem[1, id + 2, metric_idx] = proc.used_gpu_memory
            # normalize ntslices
            # result = result / np.sum(result, axis=0) * 100
            # if smoothing:
            #     # apply smoothing filter
            #     result = np.apply_along_axis(
            #         lambda x: np.convolve(x, smooth_filter, mode='same'), axis=1, arr=result
            #     )
            ts_rectified = (ts - ts[0]) / 1e9
            timestamps = (timestamps - timestamps[0]) / 1e9
            labels = [field.name for field in gpu_metrics_pb2.GPUMetrics.DESCRIPTOR.fields]
            fig = plt.figure(figsize=(12, 12))

            cprint.iprintf(f"Last timestamp: {timestamps[-1]}")

            plt.subplots_adjust(hspace=0.3)

            ax = plt.subplot(511)

            # vertical lines
            draw_lines(ax, x_pos)

            ax.locator_params(axis='x', nbins=10)
            ax.plot(timestamps, result[0], label="SM Utilization", color=colors[0], linewidth=1)
            ax.plot(timestamps, result[1], label="SM Occupancy", color=colors[1], linewidth=1)
            # ax.set_xlabel("Timestamp (s)")
            ax.set_ylabel("Utilization (%)")
            ax.legend(loc='upper right', ncols=10)
            ax.set_xlim(0, timestamps[-1])
            ax.set_ylim(0, 100)
            # ax.axhline(y=100, color='black', linestyle='--', linewidth=1)
            ax.yaxis.grid(color='lightgray', linestyle='--', linewidth=0.7)
            # for t in ts_rectified:
            # ax.axvline(x=t, color='black', linestyle='--', linewidth=1)
            ax.set_xticks(range(0, int(timestamps[-1]) + 1, 5))

            ax.xaxis.set_major_locator(mtick.MaxNLocator(nbins=6))

            ax = plt.subplot(512)

            # vertical lines
            draw_lines(ax, x_pos)

            plt.locator_params(axis='x', nbins=10)
            ax.plot(timestamps, result[2], label="PCIe to CPU", color=colors[0], linewidth=1)
            ax.plot(timestamps, result[3], label="PCIe to GPU", color=colors[1], linewidth=1)
            # ax.set_xlabel("Timestamp (s)")
            ax.set_ylabel("Throughput (MB/s)")
            ax.legend(loc='upper right', ncols=10)
            ax.set_xlim(0, timestamps[-1])
            print("max timestamp:", timestamps[-1])
            ax.set_ylim(0, 4000)
            ax.yaxis.grid(color='lightgray', linestyle='--', linewidth=0.7)
            # for t in ts_rectified:
            # ax.axvline(x=t, color='black', linestyle='--', linewidth=1)
            ax.set_xticks(range(0, int(timestamps[-1]) + 1, 5))

            ax.xaxis.set_major_locator(mtick.MaxNLocator(nbins=6))

            ax = plt.subplot(513)

            # vertical lines
            draw_lines(ax, x_pos)

            plt.locator_params(axis='x', nbins=10)
            ax.plot(
                timestamps,
                result[4],
                label="DRAM BW Utilization",
                color=colors[0],
                linestyle=linestyles[0],
            )
            ax.plot(
                timestamps,
                result[5],
                label="INTEGER_UTIL",
                color=colors[1],
                linestyle=linestyles[0],
            )
            ax.plot(
                timestamps,
                result[9],
                label="ANY_TENSOR_UTIL",
                color=colors[2],
                linestyle=linestyles[0],
            )
            ax.plot(
                timestamps,
                result[10],
                label="GRAPHICS_UTIL",
                color=colors[3],
                linestyle=linestyles[0],
            )
            # ax.set_xlabel("Timestamp (s)")
            ax.set_ylabel("Utilization (%)")
            ax.set_xlim(0, timestamps[-1])
            ax.set_ylim(0, 105)
            ax.legend(loc='upper right', ncols=10)
            ax.yaxis.grid(color='lightgray', linestyle='--', linewidth=0.7)
            # for t in ts_rectified:
            # ax.axvline(x=t, color='black', linestyle='--', linewidth=1)
            ax.set_xticks(range(0, int(timestamps[-1]) + 1, 5))

            ax.xaxis.set_major_locator(mtick.MaxNLocator(nbins=6))

            """
            ax = plt.subplot(514)

            # vertical lines
            draw_lines(ax, x_pos)

            ax.plot(
                timestamps, result[5], label="Integer Utilization", color=colors[0], linewidth=1
            )
            ax.plot(timestamps, result[6], label="FP16 Utilization", color=colors[1], linewidth=1)
            ax.plot(timestamps, result[7], label="FP32 Utilization", color=colors[2], linewidth=1)
            ax.plot(timestamps, result[8], label="FP64 Utilization", color=colors[3], linewidth=1)
            # ax.set_xlabel("Timestamp (s)")
            ax.set_ylabel("Utilization (%)")
            ax.legend(loc='upper right', ncols=10)
            ax.set_xlim(0, timestamps[-1])
            ax.set_ylim(0, 100)
            # ax.axhline(y=100, color='black', linestyle='--', linewidth=1)
            ax.yaxis.grid(color='lightgray', linestyle='--', linewidth=0.7)
            # for t in ts_rectified:
                # ax.axvline(x=t, color='black', linestyle='--', linewidth=1)
            ax.set_xticks(range(0, int(timestamps[-1]) + 1, 5))

            ax.xaxis.set_major_locator(mtick.MaxNLocator(nbins=6))

            # fig.savefig(f"{data_file_name}_{output_folder_name}.png", dpi=300, bbox_inches='tight')
            save_path = os.path.join(output_folder, f"{data_file_name}.png")
            fig.savefig(save_path, dpi=300, bbox_inches='tight')
            cprint.iprintf(f"GPU metrics figure saved to {data_file_name}.png")
            """

            ax = plt.subplot(514)

            # vertical lines
            draw_lines(ax, x_pos)

            plt.locator_params(axis='x', nbins=10)
            sum = np.zeros(ntslices, dtype=np.int64)
            for iter in range(mem.shape[1]):
                # skip if all zero
                if np.all(mem[0, iter, :] == 0):
                    continue
                sum = sum + mem[0, iter, :] / (1024 * 1024 * 1024)
                ax.plot(
                    timestamps,
                    sum,
                    # label=f"Process {iter} Mem Usage",
                    linewidth=1,
                )

            ax.set_xlabel("Timestamp (s)")
            ax.set_ylabel("Memory (GB)")
            ax.legend(loc='upper right', ncols=10)
            ax.set_xlim(0, timestamps[-1])
            ax.set_ylim(0, 100)
            ax.axhline(y=94, color='black', linestyle='--', linewidth=1)
            ax.yaxis.grid(color='lightgray', linestyle='--', linewidth=0.7)
            # for t in ts_rectified:
            # ax.axvline(x=t, color='black', linestyle='--', linewidth=1)
            ax.set_xticks(range(0, int(timestamps[-1]) + 1, 5))

            ax.xaxis.set_major_locator(mtick.MaxNLocator(nbins=6))

            ax = plt.subplot(515)

            # vertical lines
            draw_lines(ax, x_pos)

            plt.locator_params(axis='x', nbins=10)
            sum = np.zeros(ntslices, dtype=np.int64)
            for iter in range(mem.shape[1]):
                # skip if all zero
                if np.all(mem[1, iter, :] == 0):
                    continue
                sum = sum + mem[1, iter, :] / (1024 * 1024 * 1024)
                ax.plot(
                    timestamps,
                    sum,
                    # label=f"Process {iter} Mem Usage",
                    linewidth=1,
                )
            # ax.plot(
            #     timestamps,
            #     mem[0] / (1024 * 1024 * 1024),
            #     label="VectorDB",
            #     color=colors[0],
            #     linewidth=1,
            # )
            # ax.plot(
            #     timestamps,
            #     (mem[1] + mem[0] + mem[2]) / (1024 * 1024 * 1024),
            #     label="Generation Model",
            #     color=colors[1],
            #     linewidth=1,
            # )
            # ax.plot(
            #     timestamps,
            #     (mem[2] + mem[0]) / (1024 * 1024 * 1024),
            #     label="Rerank Model",
            #     color=colors[2],
            #     linewidth=1,
            # )
            ax.set_xlabel("Timestamp (s)")
            ax.set_ylabel("Memory (GB)")
            ax.legend(loc='upper right', ncols=10)
            ax.set_xlim(0, timestamps[-1])
            ax.set_ylim(0, 100)
            ax.axhline(y=94, color='black', linestyle='--', linewidth=1)
            ax.yaxis.grid(color='lightgray', linestyle='--', linewidth=0.7)
            # for t in ts_rectified:
            # ax.axvline(x=t, color='black', linestyle='--', linewidth=1)
            ax.set_xticks(range(0, int(timestamps[-1]) + 1, 5))

            ax.xaxis.set_major_locator(mtick.MaxNLocator(nbins=6))

            # fig.savefig(f"{data_file_name}_{output_folder_name}.png", dpi=300, bbox_inches='tight')
            save_path = os.path.join(output_folder, f"{data_file_name}.png")
            fig.savefig(save_path, dpi=300, bbox_inches='tight')
            cprint.iprintf(f"GPU metrics figure saved to {data_file_name}.png")
            plt.close(fig)

        # if data_file_name.startswith("DiskMeter"):

        if data_file_name.startswith("DiskMeter"):
            cprint.iprintf("Generating figures for Disk metrics...")
            colors = ["#57B4E9", "#019E73", "#E69F00", "#0072B2", "#B21000", "#5B0680"]
            linestyles = ['-', '--', '-.', ':', "-"]
            data_file = os.path.join(output_folder, data_file_name)
            msg = extract_time_series(data_file, disk_metrics_pb2.DiskMetricsTimeSeries)
            ts = np.array(
                [1757098153657814454, 1757098155015994472, 1757098167621610434, 1757098249092188605]
            )
            # print(msg.metrics[100])
            # print(msg.metrics[101])
            # print(msg.metrics[1010])
            nfields = 2  # read/write
            ntslices = len(msg.metrics)
            # print(nfields,ntslices)
            # labels = [field.name for field in disk_metrics_pb2.DiskMetrics.disk_metrics.DESCRIPTOR.fields]
            # print(labels)
            print("======================================")
            # print(msg.metrics[0].disk_metrics)
            # print(type(msg.metrics[0].disk_metrics[0]))
            # print(msg.metrics[0].disk_metrics[0].reads_completed)
            # exit(0)
            if ntslices < 1:
                cprint.iprintf("No disk metrics data found, skipping...")
                continue
            dis_count = len(msg.metrics[0].disk_metrics)
            timestamps = np.empty(ntslices, dtype=np.int64)
            temp = np.empty((dis_count, nfields, ntslices), dtype=np.float64)
            result = np.empty((dis_count, nfields, ntslices), dtype=np.float64)
            # start_r = metric.disk_metrics[0].sectors_read
            # start_w = metric.disk_metrics[0].sectors_written
            for metric_idx, metric in enumerate(msg.metrics):
                timestamps[metric_idx] = metric.timestamp
                for disk_id in range(dis_count):
                    temp[disk_id, 0, metric_idx] = metric.disk_metrics[disk_id].sectors_read
                    temp[disk_id, 1, metric_idx] = metric.disk_metrics[disk_id].sectors_written
                    # print(temp[:, metric_idx])
                    if metric_idx == 0:
                        result[disk_id, 0, metric_idx] = 0
                        result[disk_id, 1, metric_idx] = 0
                    else:
                        result[disk_id, 0, metric_idx] = (
                            (temp[disk_id, 0, metric_idx] - temp[disk_id, 0, metric_idx - 1])
                            / (timestamps[metric_idx] - timestamps[metric_idx - 1])
                            * 1e9
                            * 0.5
                            / 1024
                        )
                        result[disk_id, 1, metric_idx] = (
                            (temp[disk_id, 1, metric_idx] - temp[disk_id, 1, metric_idx - 1])
                            / (timestamps[metric_idx] - timestamps[metric_idx - 1])
                            * 1e9
                            * 0.5
                            / 1024
                        )
                # print(result[:, metric_idx])
                # for field_idx in range(nfields):
                #     result[field_idx, metric_idx] = metric.per_gpu_metrics[
                #         gpu_id := 0
                #     ].GPM_metrics_values[field_idx]
            # normalize ntslices
            # result = result / np.sum(result, axis=0) * 100
            # print(result)
            # print(result[1])
            # if smoothing:
            #     # apply smoothing filter
            #     result = np.apply_along_axis(
            #         lambda x: np.convolve(x, smooth_filter, mode='same'), axis=1, arr=result
            #     )
            ts_rectified = (ts - ts[0]) / 1e9
            timestamps = (timestamps - timestamps[0]) / 1e9
            # labels = [field.name for field in gpu_metrics_pb2.GPUMetrics.DESCRIPTOR.fields]
            fig = plt.figure(figsize=(12, 8))

            cprint.iprintf(f"Start times: {timestamps[0]} Last timestamp: {timestamps[-1]}")

            ax = fig.add_subplot(111)

            # vertical lines
            draw_lines(ax, x_pos)
            for id in range(dis_count):
                ax.plot(timestamps, result[id, 0], label="Read", color=colors[0], linewidth=1)
                ax.plot(timestamps, result[id, 1], label="Write", color=colors[1], linewidth=1)
            ax.set_xlabel("Timestamp (s)")
            ax.set_ylabel("Disk IO Bandwidth (MB/s)")
            ax.legend(loc='upper right', ncols=10)
            ax.set_xlim(0, timestamps[-1])
            ax.set_ylim(0, 6000)
            # ax.axhline(y=100, color='black', linestyle='--', linewidth=1)
            ax.yaxis.grid(color='lightgray', linestyle='--', linewidth=0.7)
            # for t in ts_rectified:
            # ax.axvline(x=t, color='black', linestyle='--', linewidth=1)
            ax.set_xticks(range(0, int(timestamps[-1]) + 1, 5))
            ax.xaxis.set_major_locator(mtick.MaxNLocator(nbins=6))
            # fig.savefig(f"{data_file_name}_{output_folder_name}.png", dpi=300, bbox_inches='tight')
            save_path = os.path.join(output_folder, f"{data_file_name}.png")
            fig.savefig(save_path, dpi=300, bbox_inches='tight')
            cprint.iprintf(f"Disk metrics figure saved to {data_file_name}.png")
            plt.close(fig)

        if data_file_name.startswith("MemMeter"):
            cprint.iprintf("Generating figures for Mmeory metrics...")
            colors = ["#57B4E9", "#019E73", "#E69F00", "#0072B2", "#B21000", "#5B0680"]
            linestyles = ['-', '--', '-.', ':', "-"]
            data_file = os.path.join(output_folder, data_file_name)
            msg = extract_time_series(data_file, mem_metrics_pb2.MemMetricsTimeSeries)
            ts = np.array(
                [1757098153657814454, 1757098155015994472, 1757098167621610434, 1757098249092188605]
            )
            # print(msg)
            # exit(0)
            nfields = 4
            ntslices = len(msg.metrics)
            # print(nfields,ntslices)
            print("---------------------------------------------------------")
            # print(ntslices)
            # print(msg.metrics[0])
            # print(msg.metrics[0].meminfo_metrics.basic_metrics.mem_total)
            # exit(0)
            if len(msg.metrics) == 0:
                continue
            timestamps = np.empty(ntslices, dtype=np.int64)
            start_time = msg.metrics[0].timestamp
            result = np.empty((nfields, ntslices), dtype=np.float64)
            for metric_idx, metric in enumerate(msg.metrics):
                timestamps[metric_idx] = metric_idx / 10
                # print(timestamps[metric_idx])
                result[0, metric_idx] = metric.meminfo_metrics.basic_metrics.mem_free / (
                    1024 * 1024
                )
                result[1, metric_idx] = metric.meminfo_metrics.basic_metrics.mem_available / (
                    1024 * 1024
                )
                result[2, metric_idx] = metric.meminfo_metrics.kernel_cache_metrics.buffers / (
                    1024 * 1024
                )
                result[3, metric_idx] = metric.meminfo_metrics.kernel_cache_metrics.cached / (
                    1024 * 1024
                )

            ts_rectified = (ts - ts[0]) / 1e9

            fig = plt.figure(figsize=(12, 3))
            cprint.iprintf(f"Last timestamp: {timestamps[-1]}")
            ax = fig.add_subplot(111)

            # vertical lines
            draw_lines(ax, x_pos)

            ax.plot(timestamps, result[0], label="Free", color=colors[0], linewidth=2)
            ax.plot(timestamps, result[1], label="Available", color=colors[1], linewidth=2)
            ax.plot(timestamps, result[2], label="Buffered", color=colors[2], linewidth=2)
            ax.plot(timestamps, result[3], label="Cached", color=colors[4], linewidth=2)
            ax.set_xlabel("Timestamp (s)")
            ax.set_ylabel("Disk IO (%)")
            ax.legend(loc='upper right', ncols=10)
            ax.set_xlim(0, timestamps[-1])
            ax.set_ylim(100, 1500)
            ax.axhline(y=100, color='black', linestyle='--', linewidth=1)
            ax.yaxis.grid(color='lightgray', linestyle='--', linewidth=0.7)
            # for t in ts_rectified:
            # ax.axvline(x=t, color='black', linestyle='--', linewidth=1)
            ax.set_xticks(range(0, int(timestamps[-1]) + 1, 5))
            ax.xaxis.set_major_locator(mtick.MaxNLocator(nbins=6))
            # fig.savefig(f"{data_file_name}_{output_folder_name}.png", dpi=300, bbox_inches='tight')
            save_path = os.path.join(output_folder, f"{data_file_name}.png")
            fig.savefig(save_path, dpi=300, bbox_inches='tight')
            cprint.iprintf(f"Mem metrics figure saved to {data_file_name}.png")
            plt.close(fig)

        if data_file_name.startswith("ProcMeter"):
            cprint.iprintf("Generating figures for proc metrics...")
            colors = ["#57B4E9", "#019E73", "#E69F00", "#0072B2", "#B21000", "#5B0680"]
            linestyles = ['-', '--', '-.', ':', "-"]
            data_file = os.path.join(output_folder, data_file_name)
            msg = extract_time_series(data_file, proc_metrics_pb2.ProcMetricsTimeSeries)
            # ts = np.array(
            #     [1757098153657814454, 1757098155015994472, 1757098167621610434, 1757098249092188605]
            # )
            print("++++++++++++++++++++++++++++++++++++++++++++++=")
            print(msg.metrics[0])
