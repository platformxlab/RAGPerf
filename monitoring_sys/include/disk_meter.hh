#pragma once

#include "include/logger.hh"
#include "include/meter.hh"
#include "include/utils.hh"

#include "generated/proto/disk_metrics.pb.h"

namespace MSys {

class DiskMeter final : public Meter {
  public:
    DiskMeter(cr::milliseconds tick_period, const std::vector<std::string> &devices);

    bool update(bool testrun) override final;
    std::string getDetailedReport() const override final;

  private:
    const std::unordered_set<std::string> devices;
};

}  // namespace MSys