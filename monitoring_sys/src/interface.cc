#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#ifdef PYBIND11_RICH_INTERFACE
#include "generated/interface/pybind11_defs.h"
#endif
#include "include/msys.hh"

namespace py = pybind11;

/**
 * NOTE: [Write Path Validation] All of the path exists inputted into the
 * system will only be validated at input checking time. Any changes to the
 * in-filesystem state for the inputted paths and any parent paths (
 * including moving, renaming, and other actions that can possibly make the
 * inputted path invalid) are considered undefined behavior and will not be
 * actively checked by the system at runtime.
 *
 * TODO: Make sure all required path for the system are validated at system
 * initialization phase, so that the external FS change will only be causing
 * undefined behavior when they are done during initialization phase.
 */

// Contains all the interface functions that should be registered with pybind11
namespace MSys::Interface {

namespace Detail {

/**
 * Get appropiate sampling period given a monitoring sys and external user input
 * @note system share_ptr is taken by reference, caller need to ensure the
 *       shared_ptr is not destroyed during this function call
 * @param system system the meter is being added to
 * @param period_ms sampling period specified by user, equal to 0 if the user
 *        leave the option empty
 * @return appropiate sampling period for the meter
 */
inline cr::milliseconds getSamplePeriod(std::shared_ptr<System> &system, unsigned period_ms) {
    return period_ms == 0 ? system->getDefaultSamplePeriod() : cr::milliseconds{period_ms};
}

inline bool addMeterToSystem(std::shared_ptr<System> &system, std::unique_ptr<Meter> &&meter) {
    std::string_view meter_name = meter->getName();
    bool status = system->addMeter(std::move(meter));
    if (!status)
        LOG(WARNING) << absl::StrFormat(
            "[Interface] Try adding %s meter to system %d failed", meter_name,
            system->getSystemID());
    return status;
}

}  // namespace Detail

/**
 * Initialize the underlying monitoring system
 *
 * @param log_dir directory to place log, must exist and writeable, otherwise
 *        the initialization will fail
 * @return whether the initialization is successful
 */
bool initialize(const std::string &log_dir) { return msysInitialize(log_dir); }

/**
 * Construct a monitoring system and return its index as an identifier to access
 * that instance. An individual thread will be spawned to handle one meter
 *
 * @param default_sample_period_ms default sample period for all the meters
 *        added to the system if a explicit sample period is not given at meter
 *        creation time
 * @return an ID associated with the system
 */
SystemID getMonitoringSystem(
    const std::string &output_dir, unsigned default_sample_period_ms = 500) {
    return constructNewSystem(output_dir, default_sample_period_ms);
}

/**
 * Add a monitor probe to CPU
 *
 * @param id target SystemID to add the probe
 * @param sample_period_ms sample period, same as system if not specified
 * @return whether adding the probe is successful
 */
bool addCPUMeterToSystem(SystemID id, unsigned sample_period_ms = 0) {
    std::shared_ptr<System> system = retrieveSystemUsingIndex(id);
    if (!system) return false;

    return Detail::addMeterToSystem(
        system, std::make_unique<CPUMeter>(Detail::getSamplePeriod(system, sample_period_ms)));
}

/**
 * Add a monitor probe to some GPUs
 *
 * @param id target SystemID to add the probe
 * @param gpu_ids list of GPUs to probe
 * @param nvml_metrics list of NVML metrics
 * @param gpm_metrics list of GPM metrics
 * @param sample_period_ms sample period, same as system if not specified
 * @return whether adding the probe is successful
 */
bool addGPUMeterToSystem(
    SystemID id, std::vector<unsigned> gpu_ids, std::vector<unsigned> nvml_metrics,
    std::vector<unsigned> gpm_metrics, unsigned sample_period_ms = 0) {
    std::shared_ptr<System> system = retrieveSystemUsingIndex(id);
    if (!system) return false;

    return Detail::addMeterToSystem(
        system,
        std::make_unique<GPUMeter>(
            Detail::getSamplePeriod(system, sample_period_ms), gpu_ids, nvml_metrics, gpm_metrics));
}

/**
 * Add a monitor probe to some block devices
 *
 * @param id target SystemID to add the probe
 * @param devices list of devices to monitor
 * @param sample_period_ms sample period, same as system if not specified
 * @return whether adding the probe is successful
 */
bool addDiskMeterToSystem(
    SystemID id, std::vector<std::string> devices, unsigned sample_period_ms = 0) {
    std::shared_ptr<System> system = retrieveSystemUsingIndex(id);
    if (!system) return false;

    std::unique_ptr<DiskMeter> meter =
        std::make_unique<DiskMeter>(Detail::getSamplePeriod(system, sample_period_ms), devices);
    return system->addMeter(std::move(meter));
}

/**
 * Add a monitor probe to some processes
 *
 * @param id target SystemID to add the probe
 * @param pids list of processes to monitor
 * @param probes list of probes to monitor, refer to ProcMetadata::Probe
 * @param sample_period_ms sample period, same as system if not specified
 * @return whether adding the probe is successful
 */
bool addProcMeterToSystem(
    SystemID id, const std::vector<pid_t> &pids, const std::vector<unsigned> &probes,
    unsigned sample_period_ms = 0) {
    std::shared_ptr<System> system = retrieveSystemUsingIndex(id);
    if (!system) return false;

    std::vector<ProcMetadata::Probe> input_probes;
    for (auto probe : probes)
        input_probes.push_back(static_cast<ProcMetadata::Probe>(probe));

    std::unique_ptr<ProcMeter> meter = std::make_unique<ProcMeter>(
        Detail::getSamplePeriod(system, sample_period_ms), pids, input_probes);
    return system->addMeter(std::move(meter));
}

/**
 * Add a memory monitor probe to the system
 *
 * @param id target SystemID to add the probe
 * @param probes list of probes to monitor, refer to MemMetadata::Probe
 * @param sample_period_ms sample period, same as system if not specified
 * @return whether adding the probe is successful
 */
bool addMemMeterToSystem(
    SystemID id, const std::vector<unsigned> &probes, unsigned sample_period_ms = 0) {
    std::shared_ptr<System> system = retrieveSystemUsingIndex(id);
    if (!system) return false;

    std::vector<MemMetadata::Probe> input_probes;
    for (auto probe : probes)
        input_probes.push_back(static_cast<MemMetadata::Probe>(probe));

    std::unique_ptr<MemMeter> meter =
        std::make_unique<MemMeter>(Detail::getSamplePeriod(system, sample_period_ms), input_probes);
    return system->addMeter(std::move(meter));
}

bool startRecording(SystemID id) {
    std::shared_ptr<System> system = retrieveSystemUsingIndex(id);
    if (!system) return false;
    return system->startRecording();
}

bool stopRecording(SystemID id) {
    std::shared_ptr<System> system = retrieveSystemUsingIndex(id);
    if (!system) return false;
    return system->stopRecording();
}

void reportStatus(SystemID id, bool verbose = false, bool detail = false) {
    std::shared_ptr<System> system = retrieveSystemUsingIndex(id);
    if (!system) {
        verbosePrint(verbose, "System with ID %d does not exist", id);
        return;
    }
    system->reportStatus(verbose, detail);
}

bool testRun(SystemID id, bool fail_on_error = false) {
    std::shared_ptr<System> system = retrieveSystemUsingIndex(id);
    if (!system) return false;

    // Perform a test run, which will update all meters in the system
    bool ret = system->testRun();
    if (!ret) {
        absl::LogSeverity severity =
            fail_on_error ? absl::LogSeverity::kFatal : absl::LogSeverity::kError;
        LOG(LEVEL(severity)) << absl::StrFormat(
            "[Interface] System %d (%s) Test run FAILED", id, system->getSystemName().data());
    }
    return ret;
}

}  // namespace MSys::Interface

// === Internal details BEGIN ===
// Expose a function to python using the same function name in c++
// NOTE: The function to be registered must resides in namespace MSys::Interface
// TODO: Extract interface namespace into new macro to allow quick modification
#if defined(PYBIND11_RICH_INTERFACE) && defined(PYBIND11_ARG_INFO_GEN)
// Use a modified pybind11-mkdoc with arg info in macros
/* FIXME: This does not work with overloaded functions because the macro
 *`PYBIND11_ARG_TYPE(...)` cannot resolve correctly, should call
 * `PYBIND11_ARG_TYPE(MSys, Interface, func)(&MSys::Interface::func)` on
 * function registration if the macro resolves correctly */
#define MSYS_BIND(m, func, ...)                                                                    \
    m.def(                                                                                         \
        #func, &MSys::Interface::func, PYBIND11_ARG_NAME(MSys, Interface, func),                   \
        PyDoc_STR(PYBIND11_DOC(MSys, Interface, func)), ##__VA_ARGS__)
// TODO: this still cannot resolve PYBIND11_ARG_NAME & PYBIND11_DOC ambiguity
// #define MSYS_OVERLOAD_BIND(m, func, ...) m.def(#func,
//     pybind11::overload_cast<__VA_ARGS__>(&MSys::Interface::func),
//     PYBIND11_ARG_NAME(MSys, Interface, func),
//     PyDoc_STR(PYBIND11_DOC(MSys, Interface, func)))
#define INTERFACE_DOCSTR PyDoc_STR(PYBIND11_DOC(PYBIND11, MODULE))
#elif defined(PYBIND11_RICH_INTERFACE)
// Use a unmodified version of pybind11-mkdoc
// FIXME: This also does not work with overloaded functions
#define MSYS_BIND(m, func, ...)                                                                    \
    m.def(#func, &MSys::Interface::func, PyDoc_STR(DOC(MSys, Interface, func)), ##__VA_ARGS__)
#define INTERFACE_DOCSTR (PyDoc_STR(DOC(PYBIND11, MODULE)))
#else
// No pybind11-mkdoc is found
// Fallback to simple binding of function name only
#define MSYS_BIND(m, func, ...) m.def(#func, &MSys::Interface::func, ##__VA_ARGS__)
#define INTERFACE_DOCSTR        ""
#endif

// Relies on external MSYS_MODNAME passed to build system
#ifndef MSYS_MODNAME
#error monitoring system name (MSYS_MODNAME) is not set
#endif
// wrapper to PYBIND11_MODULE that allows macro as name
#define PYBIND11_MODULE_WRAPPED(name, variable) PYBIND11_MODULE(name, variable)
// === Internal details END ===

/**
 * Interface for System Performance Monitor
 */
PYBIND11_MODULE_WRAPPED(MSYS_MODNAME, m) {
    m.doc() = INTERFACE_DOCSTR;

    // === Interface functions ===
    MSYS_BIND(m, initialize);
    MSYS_BIND(m, getMonitoringSystem);
    MSYS_BIND(m, addCPUMeterToSystem);
    MSYS_BIND(m, addGPUMeterToSystem);
    MSYS_BIND(m, addProcMeterToSystem);
    MSYS_BIND(m, addDiskMeterToSystem);
    MSYS_BIND(m, addMemMeterToSystem);

    MSYS_BIND(m, startRecording);
    MSYS_BIND(m, stopRecording);
    MSYS_BIND(m, reportStatus);
    MSYS_BIND(m, testRun);
}
