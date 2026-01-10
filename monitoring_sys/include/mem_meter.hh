#pragma once

#include "include/logger.hh"
#include "include/meter.hh"
#include "include/utils.hh"

#include "generated/proto/mem_metrics.pb.h"

namespace MSys {
class MemMeter final : public Meter {
  public:
    MemMeter(
        cr::milliseconds tick_period,
        const std::vector<MemMetadata::Probe> &probes = {MemMetadata::MEM_BASIC});

    bool update(bool testrun) override final;
    std::string getDetailedReport() const override final;

  private:
    const std::vector<MemMetadata::Probe> probes;
    std::unique_ptr<KVRepr> mem_info_repr;

    std::unordered_set<const proto::FieldDescriptor *> mem_info_fields;
};

}  // namespace MSys