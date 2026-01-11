#include "include/mem_meter.hh"

namespace MSys {

namespace Detail {

/**
 * Memory information keys.
 * @note Follow proto file definition order, not the field number order.
 */

// Basic memory information keys.
static const std::vector<std::string> mem_basic_info_keys = {
    "MemTotal",
    "MemFree",
    "MemAvailable",
};

static const std::vector<std::string> mem_kernel_cache_keys = {
    "Buffers",
    "Cached",
    "SwapCached",
};

static const std::vector<std::string> mem_active_inactive_keys = {
    "Active", "Inactive", "Active(anon)", "Inactive(anon)", "Active(file)", "Inactive(file)",
};

static const std::vector<std::string> mem_non_evictable_keys = {
    "Unevictable",
    "Mlocked",
};

static const std::vector<std::string> mem_swap_keys = {
    "SwapTotal",
    "SwapFree",
    "Zswap",
    "Zswapped",
};

static const std::vector<std::string> mem_dirty_writeback_keys = {
    "Dirty",
    "Writeback",
};

static const std::vector<std::string> mem_type_keys = {
    "AnonPages",
    "Mapped",
    "Shmem",
};

static const std::vector<std::string> mem_kernel_keys = {
    "KReclaimable", "Slab", "SReclaimable", "SUnreclaim", "KernelStack", "PageTables",
};

static const std::vector<std::string> mem_tmp_buffer_keys = {
    "NFS_Unstable",
    "Bounce",
    "WritebackTmp",
};

static const std::vector<std::string> mem_virtual_keys = {
    "CommitLimit", "Committed_AS", "VmallocTotal", "VmallocUsed", "VmallocChunk",
};

static const std::vector<std::string> mem_huge_page_keys = {
    "AnonHugePages",  "ShmemHugePages",  "ShmemPmdMapped", "FileHugePages",
    "FilePmdMapped",  "HugePages_Total", "HugePages_Free", "HugePages_Rsvd",
    "HugePages_Surp", "Hugepagesize",    "Hugetlb",
};

static const std::vector<std::string> mem_direct_map_keys = {
    "DirectMap4k",
    "DirectMap2M",
    "DirectMap4M",
    "DirectMap1G",
};

static const std::vector<std::string> mem_misc_keys = {"Percpu", "HardwareCorrupted"};

/*
 * TODO: Due to proto3 cannot have constant specified in the file, the probe keys are listed in
 * this file. This is somewhat not perfect as the keys are not visible to another languages.
 * However, only the c++ code will parse through the actual files, so at this stage, just remember
 * to change/add the field correspondence in this file when the corresponding proto file is changed.
 */
static const std::unordered_map<MemMetadata::Probe, std::vector<std::string>> mem_info_keys_map = {
    {MemMetadata::MEM_BASIC, mem_basic_info_keys},
    {MemMetadata::MEM_KERNEL_CACHE, mem_kernel_cache_keys},
    {MemMetadata::MEM_ACTIVE_INACTIVE, mem_active_inactive_keys},
    {MemMetadata::MEM_NON_EVICTABLE, mem_non_evictable_keys},
    {MemMetadata::MEM_SWAP, mem_swap_keys},
    {MemMetadata::MEM_DIRTY_WRITEBACK, mem_dirty_writeback_keys},
    {MemMetadata::MEM_TYPE, mem_type_keys},
    {MemMetadata::MEM_KERNEL, mem_kernel_keys},
    {MemMetadata::MEM_TMP_BUFFER, mem_tmp_buffer_keys},
    {MemMetadata::MEM_VIRTUAL, mem_virtual_keys},
    {MemMetadata::MEM_HUGE_PAGE, mem_huge_page_keys},
    {MemMetadata::MEM_DIRECT_MAP, mem_direct_map_keys},
    {MemMetadata::MEM_MISC, mem_misc_keys},
};

class MemInfoMap {
  public:
    using KeyType = MemMetadata::Probe;
    using ValueType = std::pair<const proto::Descriptor *, const std::vector<std::string>>;

    MemInfoMap() {
        const proto::Descriptor *mem_info_metrics_desc = MemInfoMetrics::descriptor();

        probe_info_map.reserve(mem_info_keys_map.size());
        for (const auto &pair : mem_info_keys_map) {
            MemMetadata::Probe probe = pair.first;
            const std::vector<std::string> &keys = pair.second;
            const proto::FieldDescriptor *field_desc =
                mem_info_metrics_desc->FindFieldByNumber(static_cast<int>(probe));
            if (!field_desc) return;
            probe_info_map.emplace(probe, std::make_pair(field_desc->message_type(), keys));
        }
        valid = true;
    }

    bool isValid() const { return valid; }

    const std::unordered_map<KeyType, ValueType> &getProbeInfoMap() const { return probe_info_map; }

  private:
    std::unordered_map<KeyType, ValueType> probe_info_map;
    bool valid = false;
};

MemInfoMap mem_info_map;

bool parseMemStat(
    const std::vector<MemMetadata::Probe> &probes, std::unique_ptr<KVRepr> &mem_info_repr,
    MemInfoMetrics *mem_info_metrics) {
    const proto::Reflection *reflection = mem_info_metrics->GetReflection();
    const proto::Descriptor *desc = mem_info_metrics->descriptor();

    std::vector<proto::Message *> parsed_messages;
    for (size_t probe_idx = 0; probe_idx < probes.size(); ++probe_idx) {
        MemMetadata::Probe probe = probes[probe_idx];
        const proto::FieldDescriptor *probe_field_desc =
            desc->FindFieldByNumber(static_cast<int>(probe));
        parsed_messages.push_back(reflection->MutableMessage(mem_info_metrics, probe_field_desc));
    }

    bool ret = mem_info_repr->parseOnce(parsed_messages);
    if (unlikely(!ret)) {
        LOG(ERROR) << absl::StrFormat(
            "[MemMeter] Failed to parse %s", mem_info_repr->getStatFilePath().c_str());
        return false;
    }
    return true;
}

static std::string getProbeReport(const std::vector<MemMetadata::Probe> &probes) {
    std::string report = "Enabled probe(s):";

    if (probes.empty()) {
        report += "\n  N/A";
        return report;
    }

    const proto::EnumDescriptor *probe_enum_desc = proto::GetEnumDescriptor<MemMetadata::Probe>();
    for (const MemMetadata::Probe &probe : probes) {
        unsigned probe_value = static_cast<unsigned int>(probe);
        const proto::EnumValueDescriptor *value_desc =
            probe_enum_desc->FindValueByNumber(probe_value);
        report += absl::StrFormat(
            "\n  - %s.%s (%d)", probe_enum_desc->full_name().data(), value_desc->name().data(),
            probe_value);
    }
    return report;
}

}  // namespace Detail

MemMeter::MemMeter(cr::milliseconds tick_period, const std::vector<MemMetadata::Probe> &probes)
    : Meter("MemMeter", tick_period, [] { return new MemMetricsTimeSeries(); }), probes(probes) {
    const auto &mem_info_map = Detail::mem_info_map.getProbeInfoMap();
    if (!Detail::mem_info_map.isValid()) {
        LOG(ERROR) << "[MemMeter] MemInfoMap failed to initialize";
        return;
    }

    const proto::EnumDescriptor *probe_enum_desc = proto::GetEnumDescriptor<MemMetadata::Probe>();
    std::vector<const proto::Descriptor *> message_descs(probes.size());
    std::vector<std::vector<std::string>> key_lists(probes.size());
    for (size_t probe_idx = 0; probe_idx < probes.size(); ++probe_idx) {
        MemMetadata::Probe probe = probes[probe_idx];

        auto it = mem_info_map.find(probes[probe_idx]);
        if (it == mem_info_map.end()) {
            unsigned int probe_value = static_cast<unsigned int>(probe);
            const proto::EnumValueDescriptor *probe_field_desc =
                probe_enum_desc->FindValueByNumber(probe_value);
            LOG(ERROR) << absl::StrFormat(
                "[MemMeter] Unsupported probe type: %s.%s (%d)",
                probe_enum_desc->full_name().data(),
                probe_field_desc ? probe_field_desc->name().data() : "<unknown>", probe_value);
            return;
        }
        message_descs[probe_idx] = it->second.first;
        key_lists[probe_idx] = it->second.second;
    }

    mem_info_repr = std::make_unique<KVRepr>(
        PROCMEMINFOFILE, message_descs, key_lists, "%64[^:]: %32s kB ", 64, 32);

    markValid();
}

bool MemMeter::update(bool testrun) {
    UNUSED(testrun);

    MemMetrics *mem_info_metrics = getCurrentBuffer<MemMetricsTimeSeries>()->add_metrics();
    return Detail::parseMemStat(probes, mem_info_repr, mem_info_metrics->mutable_meminfo_metrics());
}

std::string MemMeter::getDetailedReport() const {
    std::string report;
    if (!mem_info_repr) {
        report += "MemMeter not properly initialized.";
        return report;
    }
    report += Detail::getProbeReport(probes);
    report += "\n" + mem_info_repr->generateStatusReport();
    return report;
}

}  // namespace MSys