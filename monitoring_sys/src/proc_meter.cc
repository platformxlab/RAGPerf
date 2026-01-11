#include <fstream>
#include <sstream>
#include <string>

#include "include/proc_meter.hh"

namespace MSys {

enum class Probes {
    STAT,   // /proc/<pid>/stat
    STATM,  // /proc/<pid>/statm
    IO,     // /proc/<pid>/io
};

namespace Detail {

/**
 * Open a file for reading with the given filename format and process ID.
 *
 * @note snprintf insufficient buf length is translated to failed open
 * @tparam Buflen length of the buffer to hold the file path
 * @param filename_format format string for the filename, should be
 * @param pid process ID to substitute into the filename format
 * @return FILE pointer to the opened file, can be nullptr if open failed
 */
template <int Buflen>
FILE *openFileForRead(const char *filename_format, int pid) {
    char path[Buflen];
    snprintf(path, sizeof(path), filename_format, pid);
    FILE *fp = fopen(path, "r");
    return fp;
}

/**
 * Open a file in /proc/<pid> for reading.
 *
 * @param file file name to open, should contain the leading slash
 * @param pid process ID to substitute into the file path
 */
#define OPEN_PROC_PID_FILE_FOR_READ(file, pid)                                                     \
    openFileForRead<sizeof(PROCDIR "/" file) + log10Ceil((1UL << (sizeof(pid_t) << 3)) - 1)>(      \
        PROCDIR "/%d" file, pid)

// Refer to https://man7.org/linux/man-pages/man5/proc_pid_stat.5.html
static const char *proc_pid_stat_format =
    "%*d "       // (1)  [NT] pid %d
    "(%*[^)]) "  // (2)  [NT] comm %s
    "%c "        // (3)  [1]  state %c
    "%*d "       // (4)  [NT] ppid %d
    "%*d "       // (5)  [NT] pgrp %d
    "%*d "       // (6)  [NT] session %d
    "%*d "       // (7)  [NT] tty_nr %d
    "%*d "       // (8)  [NT] tpgid %d
    "%*u "       // (9)  [NT] flags %u
    "%lu "       // (10) [2]  minflt %lu
    "%lu "       // (11) [3]  cminflt %lu
    "%lu "       // (12) [4]  majflt %lu
    "%lu "       // (13) [5]  cmajflt %lu
    "%lu "       // (14) [6]  utime %lu
    "%lu "       // (15) [7]  stime %lu
    "%ld "       // (16) [8]  cutime %ld
    "%ld "       // (17) [9]  cstime %ld
    "%ld "       // (18) [10] priority %ld
    "%ld "       // (19) [11] nice %ld
    "%ld "       // (20) [12] num_threads %ld
    "%*ld "      // (21) [NT] itrealvalue %ld
    "%*llu "     // (22) [NT] starttime %llu
    "%lu "       // (23) [13] vsize %lu
    ;            /** fields after vsize are NT because they are not relevant for
          process resource monitoring */

static inline bool parseProcPIDStat(int pid, google::protobuf::Message *const pid_stat_msg) {
    ProcPIDStatMetrics *const pid_stat_metrics = dynamic_cast<ProcPIDStatMetrics *>(pid_stat_msg);
    if (unlikely(!pid_stat_metrics)) {
        LOG(ERROR) << absl::StrFormat(
            "[ProcMeter] Invalid ProcPIDStatMetrics pointer for pid %d", pid);
        return false;
    }

    FILE *fp = OPEN_PROC_PID_FILE_FOR_READ(STATFILE, pid);
    if (unlikely(!fp)) {
        LOG(ERROR) << absl::StrFormat(
            "[ProcMeter] Failed to open %s for pid %d: %s", STATFILE, pid, strerror(errno));
        return false;
    }

    char state;
    unsigned long minflt, cminflt, majflt, cmajflt, utime, stime;
    long cutime, cstime, priority, nice, num_threads;
    unsigned long vsize;

    int ret = fscanf(
        fp, proc_pid_stat_format, &state, &minflt, &cminflt, &majflt, &cmajflt, &utime, &stime,
        &cutime, &cstime, &priority, &nice, &num_threads, &vsize);
    if (unlikely(ret < 12)) {
        LOG(WARNING) << absl::StrFormat(
            "[ProcMeter] Failed to parse %s for pid %d: expected 12 fields, got %d", STATFILE, pid,
            ret);
    }

    pid_stat_metrics->set_state(state);
    pid_stat_metrics->set_minflt(minflt);
    pid_stat_metrics->set_cminflt(cminflt);
    pid_stat_metrics->set_majflt(majflt);
    pid_stat_metrics->set_cmajflt(cmajflt);
    pid_stat_metrics->set_utime(utime);
    pid_stat_metrics->set_stime(stime);
    pid_stat_metrics->set_cutime(cutime);
    pid_stat_metrics->set_cstime(cstime);
    pid_stat_metrics->set_priority(priority);
    pid_stat_metrics->set_nice(nice);
    pid_stat_metrics->set_num_threads(num_threads);
    pid_stat_metrics->set_vsize(vsize);

    fclose(fp);
    return true;
}

static const char *proc_pid_statm_format =
    "%lu "  // (1) [1] size %lu
    "%lu "  // (2) [2] resident %lu
    "%lu "  // (3) [3] share %lu
    "%lu "  // (4) [4] text %lu
    "%lu "  // (5) [5] lib %lu
    "%lu "  // (6) [6] data %lu
    "%lu "  // (7) [7] dt %lu
    ;       /** fields after dt are NT because they are not relevant for
          process resource monitoring */

static inline bool parseProcPIDStatm(int pid, ProcPIDStatmMetrics *const pid_statm_msg) {
    ProcPIDStatmMetrics *const pid_statm_metrics =
        dynamic_cast<ProcPIDStatmMetrics *>(pid_statm_msg);
    if (unlikely(!pid_statm_metrics)) {
        LOG(ERROR) << absl::StrFormat(
            "[ProcMeter] Invalid ProcPIDStatmMetrics pointer for pid %d", pid);
        return false;
    }

    FILE *fp = OPEN_PROC_PID_FILE_FOR_READ(STATMFILE, pid);
    if (unlikely(!fp)) {
        LOG(ERROR) << absl::StrFormat(
            "[ProcMeter] Failed to open %s for pid %d: %s", STATMFILE, pid, strerror(errno));
        return false;
    }

    unsigned long size, resident, shared, text, lib, data, dt;
    int nfields =
        fscanf(fp, proc_pid_statm_format, &size, &resident, &shared, &text, &lib, &data, &dt);
    if (unlikely(nfields < 7)) {
        LOG(WARNING) << absl::StrFormat(
            "[ProcMeter] Failed to parse %s for pid %d: expected 7 fields, got %d", STATMFILE, pid,
            nfields);
    }

    pid_statm_metrics->set_size(size);
    pid_statm_metrics->set_resident(resident);
    pid_statm_metrics->set_share(shared);
    pid_statm_metrics->set_text(text);
    pid_statm_metrics->set_lib(lib);
    pid_statm_metrics->set_data(data);
    pid_statm_metrics->set_dt(dt);

    fclose(fp);
    return true;
}

static const char *proc_pid_io_format =
    "rchar: %lu "                  // (1) [1] read chars %lu
    "wchar: %lu "                  // (2) [2] written chars %lu
    "syscr: %lu "                  // (3) [3] read syscalls %lu
    "syscw: %lu "                  // (4) [4] write syscalls %lu
    "read_bytes: %lu "             // (5) [5] read bytes %lu
    "write_bytes: %lu "            // (6) [6] written bytes %lu
    "cancelled_write_bytes: %lu "  // (7) [7] cancelled write bytes %lu
    ;

static inline bool parseProcPIDIO(int pid, ProcPIDIOMetrics *const pid_io_msg) {
    ProcPIDIOMetrics *const pid_io_metrics = dynamic_cast<ProcPIDIOMetrics *>(pid_io_msg);
    if (unlikely(!pid_io_metrics)) {
        LOG(ERROR) << absl::StrFormat(
            "[ProcMeter] Invalid ProcPIDIOMetrics pointer for pid %d", pid);
        return false;
    }

    FILE *fp = OPEN_PROC_PID_FILE_FOR_READ(IOFILE, pid);
    if (unlikely(!fp)) {
        LOG(ERROR) << absl::StrFormat(
            "[ProcMeter] Failed to open %s for pid %d: %s", IOFILE, pid, strerror(errno));
        return false;
    }

    unsigned long rchar, wchar, syscr, syscw, read_bytes, write_bytes, cancelled_write_bytes;
    int nfields = fscanf(
        fp, proc_pid_io_format, &rchar, &wchar, &syscr, &syscw, &read_bytes, &write_bytes,
        &cancelled_write_bytes);
    if (unlikely(nfields < 7)) {
        LOG(WARNING) << absl::StrFormat(
            "[ProcMeter] Failed to parse %s for pid %d: expected 7 fields, got %d", IOFILE, pid,
            nfields);
    }

    pid_io_metrics->set_rchar(rchar);
    pid_io_metrics->set_wchar(wchar);
    pid_io_metrics->set_syscr(syscr);
    pid_io_metrics->set_syscw(syscw);
    pid_io_metrics->set_read_bytes(read_bytes);
    pid_io_metrics->set_write_bytes(write_bytes);
    pid_io_metrics->set_cancelled_write_bytes(cancelled_write_bytes);

    fclose(fp);
    return true;
}

}  // namespace Detail

ProcMeter::ProcMeter(
    cr::milliseconds tick_period, const std::vector<pid_t> &pids,
    const std::vector<ProcMetadata::Probe> &probes)
    : Meter("ProcMeter", tick_period, [] { return new ProcMetricsTimeSeries(); }),
      pids(pids),
      probes(probes.begin(), probes.end()) {
    if (pids.empty()) {
        LOG(ERROR) << "[ProcMeter] No PIDs provided for ProcMeter";
        return;
    }

    if (probes.empty()) {
        LOG(ERROR) << "[ProcMeter] No probes provided for ProcMeter";
        return;
    }

    markValid();
}

bool ProcMeter::update(bool testrun) {
    UNUSED(testrun);

    ProcMetrics *proc_metrics = getCurrentBuffer<ProcMetricsTimeSeries>()->add_metrics();
    bool ret = true;
    for (const pid_t pid : pids) {
        PerProcMetrics *per_proc_metrics = proc_metrics->add_per_proc_metrics();
        // FIXME: current way of iterating is not efficient enough
        // STAT
        if (probes.find(ProcMetadata::STAT) != probes.end())
            ret &= Detail::parseProcPIDStat(pid, per_proc_metrics->mutable_pid_stat_metrics());
        // STATM
        if (probes.find(ProcMetadata::STATM) != probes.end())
            ret &= Detail::parseProcPIDStatm(pid, per_proc_metrics->mutable_pid_statm_metrics());
        // IO
        if (probes.find(ProcMetadata::IO) != probes.end())
            ret &= Detail::parseProcPIDIO(pid, per_proc_metrics->mutable_pid_io_metrics());
    }
    return ret;
}

std::string ProcMeter::getDetailedReport() const {
    std::string report;
    report += absl::StrFormat("Monitored PIDs:");
    for (const auto &pid : pids) {
        report += absl::StrFormat("\n  - %d", pid);
    }

    report += "\nEnabled probe(s):";
    const proto::EnumDescriptor *probe_enum_desc = proto::GetEnumDescriptor<ProcMetadata::Probe>();
    for (const auto &probe : probes) {
        unsigned probe_value = static_cast<unsigned int>(probe);
        const proto::EnumValueDescriptor *value_desc =
            probe_enum_desc->FindValueByNumber(probe_value);
        report += absl::StrFormat(
            "\n  - %s.%s (%d)", probe_enum_desc->full_name().data(), value_desc->name().data(),
            probe_value);
    }
    return report;
}

}  // namespace MSys
