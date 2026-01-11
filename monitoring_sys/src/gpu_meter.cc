#include "include/gpu_meter.hh"

namespace MSys {

namespace Detail {

/**
 * Retrieve the support status of GPM capabilities for given GPU
 * NOTE: NVML GPM is supported on Hopper or newer fully supported devices, refer
 * to NVIDIA GPM documentations at
 * https://docs.nvidia.com/deploy/nvml-api/group__nvmlGpmFunctions.html
 *
 * @param nvml_dev target device to query
 * @return whether the device supports GPM
 */
static inline bool isGPMSupported(const nvmlDevice_t &nvml_dev) {
    nvmlGpmSupport_t ret;
    ret.version = NVML_GPM_SUPPORT_VERSION;
    nvmlCall(nvmlGpmQueryDeviceSupport(nvml_dev, &ret));
    return ret.isSupportedDevice;
}

// NOTE: with (potential) expensive string formation cost
static inline std::string getDeviceName(const nvmlDevice_t &nvml_dev) {
    constexpr unsigned name_length = NVML_DEVICE_NAME_V2_BUFFER_SIZE;
    char name[name_length];
    nvmlCall(nvmlDeviceGetName(nvml_dev, name, name_length));
    return std::string(name);
}

// NOTE: with (potential) expensive string formation cost
static inline std::string getDeviceBusID(const nvmlDevice_t &nvml_dev) {
    nvmlPciInfo_t nvml_pci_info;
    nvmlCall(nvmlDeviceGetPciInfo(nvml_dev, &nvml_pci_info));
    return std::string(nvml_pci_info.busId);
}

static inline std::pair<int, int> getCUDAComputeCapability(const nvmlDevice_t &nvml_dev) {
    int major = 0, minor = 0;
    nvmlCall(nvmlDeviceGetCudaComputeCapability(nvml_dev, &major, &minor));
    return std::make_pair(major, minor);
}

static inline unsigned getDevicePCIeLinkGeneration(const nvmlDevice_t &nvml_dev) {
    unsigned link_gen;
    nvmlCall(nvmlDeviceGetCurrPcieLinkGeneration(nvml_dev, &link_gen));
    return link_gen;
}

static inline unsigned getDevicePCIeLinkWidth(const nvmlDevice_t &nvml_dev) {
    unsigned link_width;
    nvmlCall(nvmlDeviceGetCurrPcieLinkGeneration(nvml_dev, &link_width));
    return link_width;
}

static inline void parseGPUProperties(const nvmlDevice_t &nvml_dev, GPUProperties *metadata) {
    // metadata->dev_name
    metadata->set_dev_name(getDeviceName(nvml_dev));
    // metadata->bus_id
    metadata->set_bus_id(getDeviceBusID(nvml_dev));
    // metadata->compute_capability
    std::pair<int, int> device_CC = getCUDAComputeCapability(nvml_dev);
    CUDACC *cc = metadata->mutable_compute_capability();
    cc->set_major(device_CC.first);
    cc->set_minor(device_CC.second);
    // metadata->link_generation
    metadata->set_link_generation(getDevicePCIeLinkGeneration(nvml_dev));
    // metadata->link_width
    metadata->set_link_width(getDevicePCIeLinkWidth(nvml_dev));
}

static inline bool parseGPUNVML(
    unsigned gpu_id, const nvmlDevice_t &nvml_dev, const std::vector<unsigned> &nvml_metrics,
    PerGPUMetrics *metrics) {
    // FIXME: not implemented for now
    UNUSED(gpu_id);
    UNUSED(nvml_dev);
    UNUSED(nvml_metrics);
    UNUSED(metrics);
    return true;
}

static inline bool parseGPUGPM(
    unsigned gpu_id, const nvmlDevice_t &nvml_dev, nvmlGpmMetricsGet_t &mg,
    nvmlGpmSample_t &sample1, nvmlGpmSample_t &sample2, PerGPUMetrics *metrics) {
    mg.sample1 = sample1;
    mg.sample2 = sample2;
    nvmlCall(nvmlGpmSampleGet(nvml_dev, sample2));
    nvmlCall(nvmlGpmMetricsGet(&mg));

    std::swap(sample1, sample2);
    if (mg.metrics->nvmlReturn != NVML_SUCCESS) {
        LOG(ERROR) << absl::StrFormat(
            "[GPUMeter] NVML GPM metrics get failed for GPU %d: %d (%s)", gpu_id,
            mg.metrics->nvmlReturn, nvmlErrorString(mg.metrics->nvmlReturn));
        return false;
    }

    // get all metrics values from mg
    for (unsigned metrics_id = 0; metrics_id < mg.numMetrics; metrics_id++) {
        metrics->add_gpm_metrics_values(mg.metrics[metrics_id].value);
    }
    return true;
}

static inline bool parseGPUProcesses(
    unsigned gpu_id, const nvmlDevice_t &nvml_dev, PerGPUMetrics *metrics) {
    UNUSED(gpu_id);

    unsigned info_count = 0;
    nvmlDeviceGetComputeRunningProcesses(nvml_dev, &info_count, nullptr);

    nvmlProcessInfo_t *infos = new nvmlProcessInfo_t[info_count];
    nvmlCall(nvmlDeviceGetComputeRunningProcesses(nvml_dev, &info_count, infos));

    for (unsigned i = 0; i < info_count; i++) {
        const nvmlProcessInfo_t &info = infos[i];
        PerProcessGPUMetrics *process_metrics = metrics->add_per_process_gpu_metrics();
        process_metrics->set_pid(info.pid);
        process_metrics->set_used_gpu_memory(info.usedGpuMemory);
    }

    delete[] infos;
    return true;
}

}  // namespace Detail

static constexpr cr::milliseconds min_tick_period{100};

GPUMeter::GPUMeter(
    cr::milliseconds tick_period, const std::vector<unsigned> &gpu_ids,
    const std::vector<unsigned> &nvml_metrics, const std::vector<unsigned> &gpm_metrics)
    : Meter("GPUMeter", tick_period, [] { return new GPUMetricsTimeSeries(); }),
      gpu_ids(gpu_ids),
      nvml_metrics(nvml_metrics),
      gpm_metrics(gpm_metrics),
      nvml_devs(gpu_ids.size()),
      gpm_samples(gpu_ids.size()) {
    if (tick_period < min_tick_period) {
        LOG(WARNING) << absl::StrFormat(
            "[GPUMeter] GPM tick period should be greater than %d, get %d, "
            "enforcing %d",
            min_tick_period.count(), tick_period.count(), min_tick_period.count());
        tick_period = min_tick_period;
    }

    // initialize nvml for corresponding devices
    nvmlCall(nvmlInit());
    for (unsigned gpu_idx = 0; gpu_idx < gpu_ids.size(); gpu_idx++) {
        unsigned gpu_id = gpu_ids[gpu_idx];

        nvmlDevice_t nvml_dev;
        nvmlReturn_t ret = nvmlDeviceGetHandleByIndex(gpu_id, &nvml_dev);
        if (ret != NVML_SUCCESS) {
            LOG(ERROR) << absl::StrFormat(
                "[GPUMeter] NVML cannot be attached to GPU with ID: %d, dropping", gpu_id);
            continue;
        }

        NVMLProperties nvml_prop = {};
        // check if GPM is supported on the device
        nvml_prop.gpm_supported = Detail::isGPMSupported(nvml_dev);
        if (!nvml_prop.gpm_supported)
            LOG(ERROR) << absl::StrFormat(
                "[GPUMeter] GPU with ID: %d does not support GPM", gpu_id);

        // add to tracing candidates
        nvml_devs[gpu_idx] = std::make_pair(nvml_dev, nvml_prop);
        nvmlCall(nvmlGpmSampleAlloc(&gpm_samples[gpu_idx].first));
        nvmlCall(nvmlGpmSampleAlloc(&gpm_samples[gpu_idx].second));
    }

    gpm_mg_format.version = NVML_GPM_METRICS_GET_VERSION;
    gpm_mg_format.numMetrics = (unsigned)gpm_metrics.size();
    for (size_t metrics_idx = 0; metrics_idx < gpm_metrics.size(); metrics_idx++) {
        unsigned metric_id = gpm_metrics[metrics_idx];
        gpm_mg_format.metrics[metrics_idx].metricId = static_cast<nvmlGpmMetricId_t>(metric_id);
    }

    markValid();
}

GPUMeter::~GPUMeter() { nvmlCall(nvmlShutdown()); }

bool GPUMeter::update(bool testrun) {
    /*
     * NVML GPM metrics need two samples to calculate the metrics, so the first
     * time we call this function, the first sample is retrieved without
     * getting te metrics.
     */

    if (unlikely(testrun)) {
        for (unsigned gpu_idx = 0; gpu_idx < gpu_ids.size(); gpu_idx++)
            nvmlCall(nvmlGpmSampleGet(nvml_devs[gpu_idx].first, gpm_samples[gpu_idx].first));
    }

    if (unlikely(!testrun && !started)) {
        for (unsigned gpu_idx = 0; gpu_idx < gpu_ids.size(); gpu_idx++)
            nvmlCall(nvmlGpmSampleGet(nvml_devs[gpu_idx].first, gpm_samples[gpu_idx].first));
        started = true;
        return true;
    }

    GPUMetrics *gpu_metrics = getCurrentBuffer<GPUMetricsTimeSeries>()->add_metrics();
    gpu_metrics->set_timestamp(cr::steady_clock::now().time_since_epoch().count());

    int ret = true;
    for (unsigned gpu_idx = 0; gpu_idx < gpu_ids.size(); gpu_idx++) {
        unsigned gpu_id = gpu_ids[gpu_idx];

        PerGPUMetrics *per_gpu_metrics = gpu_metrics->add_per_gpu_metrics();

        // parse NVML metrics
        ret &=
            Detail::parseGPUNVML(gpu_id, nvml_devs[gpu_idx].first, nvml_metrics, per_gpu_metrics);

        // parse GPM metrics
        nvmlGpmMetricsGet_t mg;
        memcpy(&mg, &gpm_mg_format, sizeof(nvmlGpmMetricsGet_t));
        ret &= Detail::parseGPUGPM(
            gpu_id, nvml_devs[gpu_idx].first, mg, gpm_samples[gpu_idx].first,
            gpm_samples[gpu_idx].second, per_gpu_metrics);

        ret &= Detail::parseGPUProcesses(gpu_id, nvml_devs[gpu_idx].first, per_gpu_metrics);
    }

    return ret;
}

std::string GPUMeter::getDetailedReport() const {
    std::string report = absl::StrFormat(
        "GPUMeter: recording %d GPU(s), #NVML metrics: %d, #GPM metrics: %d", gpu_ids.size(),
        nvml_metrics.size(), gpm_metrics.size());
    report += "\nGPU details:";
    for (unsigned gpu_idx = 0; gpu_idx < gpu_ids.size(); gpu_idx++) {
        unsigned gpu_id = gpu_ids[gpu_idx];
        report += absl::StrFormat(
            "\n - GPU %d (%s)", gpu_id,
            nvml_devs[gpu_idx].second.gpm_supported ? "GPM supported" : "GPM NOT supported");
    }

    if (nvml_metrics.size() > 0) {
        report += "\nNVML enabled probe(s):";
        const proto::EnumDescriptor *nvml_enum_desc =
            proto::GetEnumDescriptor<GPUMetadata::NVMLProbe>();
        for (const auto &metric : nvml_metrics) {
            unsigned metric_value = static_cast<unsigned int>(metric);
            const proto::EnumValueDescriptor *value_desc =
                nvml_enum_desc->FindValueByNumber(metric_value);
            report += absl::StrFormat(
                "\n  - %s.%s (%d)", nvml_enum_desc->full_name().data(), value_desc->name().data(),
                metric_value);
        }
    }

    if (gpm_metrics.size() > 0) {
        report += "\nGPM enabled probe(s):";
        const proto::EnumDescriptor *gpm_enum_desc =
            proto::GetEnumDescriptor<GPUMetadata::GPMProbe>();
        for (const auto &metric : gpm_metrics) {
            unsigned metric_value = static_cast<unsigned int>(metric);
            const proto::EnumValueDescriptor *value_desc =
                gpm_enum_desc->FindValueByNumber(metric_value);
            report += absl::StrFormat(
                "\n  - %s.%s (%d)", gpm_enum_desc->full_name().data(), value_desc->name().data(),
                metric_value);
        }
    }
    return report;
}

}  // namespace MSys