#include "include/disk_meter.hh"

namespace MSys {

namespace Detail {

// FIXME: the number of characters in device_cstr is limited to 64
static constexpr unsigned device_cstr_size = 64;

static const char *proc_diskstats_header_format =
    "%*d "  // (1)  [NT] major %d
    "%*d "  // (2)  [NT] minor %d
    "%s "   // (3)  [1]  device %s
    ;

static const char *proc_diskstats_format =
    "%lu "  // (4)  [1]  reads_completed %lu
    "%lu "  // (5)  [2]  reads_merged %lu
    "%lu "  // (6)  [3]  sectors_read %lu
    "%lu "  // (7)  [4]  time_spent_reading_ms %lu
    "%lu "  // (8)  [5]  writes_completed %lu
    "%lu "  // (9)  [6]  writes_merged %lu
    "%lu "  // (10) [7]  sectors_written %lu
    "%lu "  // (11) [8]  time_spent_writing_ms %lu
    "%lu "  // (12) [9]  io_in_progress %lu
    "%lu "  // (13) [10] time_spent_io_ms %lu
    "%lu "  // (14) [11] weighted_time_spent_io_ms %lu
    "%lu "  // (15) [12] discard_completed %lu
    "%lu "  // (16) [13] discard_merged %lu
    "%lu "  // (17) [14] discard_sectors %lu
    "%lu "  // (18) [15] time_spent_discarding_ms %lu
    "%lu "  // (19) [16] flush_completed %lu
    "%lu "  // (20) [17] time_spent_flushing_ms %lu
    ;

static inline bool parseProcDiskstats(
    const std::unordered_set<std::string> &devices, DiskMetrics *metrics) {
    FILE *fp = fopen(PROCDISKSTATSFILE, "r");
    if (unlikely(!fp)) {
        LOG(ERROR) << absl::StrFormat(
            "[DiskMeter] Failed to open %s: %s", PROCDISKSTATSFILE, strerror(errno));
        fclose(fp);
        return false;
    }

    std::unordered_set<std::string> remaining_devices(devices);

    // time stamp
    metrics->set_timestamp(cr::steady_clock::now().time_since_epoch().count());

    while (remaining_devices.size() > 0) {
        char device_cstr[device_cstr_size];
        int nfields = fscanf(fp, proc_diskstats_header_format, &device_cstr);
        if (nfields == EOF) {
            // EOF reached before the stat for all the devices are read
            LOG(WARNING) << absl::StrFormat(
                "[DiskMeter] EOF reached while reading %s, remaining devices: %zu",
                PROCDISKSTATSFILE, remaining_devices.size());
            fclose(fp);
            return false;
        }
        std::string device(device_cstr);
        if (remaining_devices.find(device) == remaining_devices.end()) {
            // Skip the rest of the line
            // FIXME: discarding return result for a function that is marked as
            // [[nodiscard]]
            int discard = fscanf(fp, "%*[^\n] ");
            (void)discard;
            continue;
        }

        unsigned long reads_completed, reads_merged, sectors_read, time_spent_reading;
        unsigned long writes_completed, writes_merged, sectors_written, time_spent_writing;
        unsigned long io_in_progress, time_spent_io, weighted_time_spent_io;
        unsigned long discard_completed, discard_merged, discard_sectors, time_spent_discarding;
        unsigned long flush_completed, time_spent_flushing;

        PerDiskMetrics *disk_stat = metrics->add_disk_metrics();
        nfields = fscanf(
            fp, proc_diskstats_format, &reads_completed, &reads_merged, &sectors_read,
            &time_spent_reading, &writes_completed, &writes_merged, &sectors_written,
            &time_spent_writing, &io_in_progress, &time_spent_io, &weighted_time_spent_io,
            &discard_completed, &discard_merged, &discard_sectors, &time_spent_discarding,
            &flush_completed, &time_spent_flushing);
        if (unlikely(nfields < 17)) {
            LOG(WARNING) << absl::StrFormat(
                "[DiskMeter] Expected 18 fields in %s, got %d. Some metrics may be missing.",
                PROCDISKSTATSFILE, nfields);
        }

        disk_stat->set_reads_completed(reads_completed);
        disk_stat->set_reads_merged(reads_merged);
        disk_stat->set_sectors_read(sectors_read);
        disk_stat->set_time_spent_reading(time_spent_reading);
        disk_stat->set_writes_completed(writes_completed);
        disk_stat->set_writes_merged(writes_merged);
        disk_stat->set_sectors_written(sectors_written);
        disk_stat->set_time_spent_writing(time_spent_writing);
        disk_stat->set_io_in_progress(io_in_progress);
        disk_stat->set_time_spent_io(time_spent_io);
        disk_stat->set_weighted_time_spent_io(weighted_time_spent_io);
        disk_stat->set_discard_completed(discard_completed);
        disk_stat->set_discard_merged(discard_merged);
        disk_stat->set_discard_sectors(discard_sectors);
        disk_stat->set_time_spent_discarding(time_spent_discarding);
        disk_stat->set_flush_completed(flush_completed);
        disk_stat->set_time_spent_flushing(time_spent_flushing);

        remaining_devices.erase(device);
    }

    fclose(fp);
    return true;
}

bool checkDiskExistence(const std::unordered_set<std::string> &devices) {
    std::unordered_multiset<std::string> disks;

    FILE *fp = fopen(PROCDISKSTATSFILE, "r");
    if (!fp) {
        LOG(WARNING) << absl::StrFormat("[DiskMeter] Failed to open %s", PROCDISKSTATSFILE);
        return false;
    }

    std::unordered_set<std::string> remaining_devices = devices;
    while (remaining_devices.size() > 0) {
        char device_cstr[device_cstr_size];
        int nfields = fscanf(fp, proc_diskstats_header_format, &device_cstr);
        if (nfields == EOF) {
            std::string warning_msg =
                "[DiskMeter] Not all devices required exist, list of nonexistent devices:";
            for (const std::string &device : remaining_devices) {
                warning_msg += absl::StrFormat(" %s", device);
            }
            LOG(WARNING) << warning_msg;
            fclose(fp);
            return false;
        }
        std::string device(device_cstr);
        auto it = remaining_devices.find(device);
        if (it != remaining_devices.end()) remaining_devices.erase(it);

        // discard the rest of the line
        int discard = fscanf(fp, "%*[^\n] ");
        (void)discard;
    }

    fclose(fp);
    return true;
}

}  // namespace Detail

DiskMeter::DiskMeter(cr::milliseconds tick_period, const std::vector<std::string> &devices)
    : Meter("DiskMeter", tick_period, [] { return new DiskMetricsTimeSeries(); }),
      devices(devices.begin(), devices.end()) {
    if (!Detail::checkDiskExistence(this->devices)) {
        LOG(ERROR) << absl::StrFormat(
            "[DiskMeter] Some devices do not exist in %s", PROCDISKSTATSFILE);
        return;
    }

    markValid();
}

bool DiskMeter::update(bool testrun) {
    UNUSED(testrun);

    DiskMetrics *metrics = getCurrentBuffer<DiskMetricsTimeSeries>()->add_metrics();
    return Detail::parseProcDiskstats(devices, metrics);
}

std::string DiskMeter::getDetailedReport() const {
    std::string report;
    report += absl::StrFormat("Monitored devices:");
    for (const auto &dev : devices) {
        report += absl::StrFormat("\n  - %s", dev);
    }
    return report;
}

}  // namespace MSys