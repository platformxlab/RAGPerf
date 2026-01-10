#pragma once

#include <sys/types.h>
#include <vector>

#include "include/logger.hh"
#include "include/meter.hh"
#include "include/utils.hh"

#include "generated/proto/proc_metrics.pb.h"

namespace MSys {

class ProcMeter final : public Meter {
  public:
    ProcMeter(
        cr::milliseconds tick_period, const std::vector<pid_t> &pids,
        const std::vector<ProcMetadata::Probe> &probes);

    bool update(bool testrun) override final;
    std::string getDetailedReport() const override final;

  private:
    const std::vector<pid_t> pids;
    const std::unordered_set<ProcMetadata::Probe> probes;
};

}  // namespace MSys