#pragma once

#include "include/logger.hh"
#include "include/meter.hh"
#include "include/utils.hh"

#include "generated/proto/cpu_metrics.pb.h"

namespace MSys {

class CPUMeter final : public Meter {
  public:
    CPUMeter(cr::milliseconds tick_period);

    bool update(bool testrun) override final;
    std::string getDetailedReport() const override final;

  private:
    const unsigned ncores;
};

}  // namespace MSys
