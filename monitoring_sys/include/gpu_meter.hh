#pragma once

#include <cupti.h>
#include <nvml.h>
#include <vector>

#include "include/logger.hh"
#include "include/meter.hh"
#include "include/utils.hh"

#include "generated/proto/gpu_metrics.pb.h"

namespace MSys {

struct NVMLProperties {
    bool gpm_supported;
};

class GPUMeter final : public Meter {
  public:
    GPUMeter(
        cr::milliseconds tick_period, const std::vector<unsigned> &gpu_ids,
        const std::vector<unsigned> &nvml_metrics, const std::vector<unsigned> &gpm_metrics);
    ~GPUMeter();

    bool update(bool testrun) override final;
    std::string getDetailedReport() const override final;

  private:
    const std::vector<unsigned> gpu_ids;
    const std::vector<unsigned> nvml_metrics;
    const std::vector<unsigned> gpm_metrics;

  private:
    /**
     * Records if the meter has started to record data. This is used to
     * determine if the first sample should be retrieved without getting the
     * metrics.
     */
    bool started = false;
    /**
     * Format for NVML GPM metrics get, used to retrieve GPM metrics. This
     * variable should !!!NOT!!! be modified after the initialization
     */
    nvmlGpmMetricsGet_t gpm_mg_format;
    FixedSizeVector<std::pair<nvmlDevice_t, NVMLProperties>> nvml_devs;
    FixedSizeVector<std::pair<nvmlGpmSample_t, nvmlGpmSample_t>> gpm_samples;
};

}  // namespace MSys