#include <math.h>
#include <mutex>

#include <fcntl.h>
#include <signal.h>
#include <stdarg.h>
#include <string.h>
#include <barrier>
#include <cerrno>
#include <csignal>
#include <memory>
#include <random>
#include <unordered_map>

#include "include/msys.hh"

namespace MSys {

namespace Detail {

// === Monitoring system registering
// RNG used to assign system IDs
static std::mt19937
#ifdef STABLE_RANDOM
    rng(0);
#else
    rng((std::random_device())());
#endif
std::uniform_int_distribution<int> uni_dist(0, INT32_MAX);
// records all existing systems, not thread-safe
static std::unordered_map<SystemID, std::shared_ptr<System>> existing_systems;
// determine if full system shutdown is needed
static bool systemOnceInitialized = false;

#ifdef SCRAMBLE_SYSTEM_ID
inline int getNewSystemID() {
    SystemID id;

    do {
        id = uni_dist(rng);
    } while (existing_systems.find(id) != existing_systems.end());

    return id;
}
#else
static SystemID current_system_id = 0;
inline SystemID getNewSystemID() { return current_system_id++; }
#endif

// === Process termination handler ===
/**
 * Exit all the running monitoring system gracefully and persist any in-memory
 * records to avoid data loss
 *
 * @param normal whether the termination is normal
 */
inline void processTerminationHandler(bool normal) {
    // nothing is initialized, so teardown is also not needed
    if (!systemOnceInitialized) return;

    absl::LogSeverity severity = normal ? absl::LogSeverity::kInfo : absl::LogSeverity::kWarning;

    // halt all existing systems
    LOG(LEVEL(severity)) << absl::StrFormat(
        "[ProcTermHandler] Performing graceful termination, halting all existing MSys (count: %zu)",
        existing_systems.size());
    for (auto pair : existing_systems) {
        LOG(LEVEL(severity)) << absl::StrFormat(
            "[ProcTermHandler] Halting MSys #%u (%s)", pair.first, pair.second->getSystemName());
        pair.second->halt();
    }
    LOG(LEVEL(severity)) << "[ProcTermHandler] System Halted";

    // Write termination report

    LOG(LEVEL(severity)) << "[ProcTermHandler] Termination complete";

    // Everything involving logger is completed, deinitialize logger
    loggerDeinitialize();
}

/**
 * Graceful termination callback on signal caught
 *
 * @param signum signal number received by the program
 */
void processSigTerminationHandler(int signum) {
    const char *signal_name = strsignal(signum);
    LOG(ERROR) << absl::StrFormat(
        "[SigHandler] Caught signal: %s (signum %d), "
        "performing monitor termination",
        signal_name ? signal_name : "<CANNOT_RESOLVE>", signum);

    // call for final termination
    processTerminationHandler(false);

    // mark the signal as not handled and re-raise the signal
    struct sigaction sa;
    sa.sa_handler = SIG_DFL;
    sigaction(signum, &sa, nullptr);
    raise(signum);
}

/**
 * Graceful termination callback on normal system exit
 */
void processNormalTerminationHandler() {
    // call for final termination
    processTerminationHandler(true);
}

constexpr auto terminable_signals =
    std::array{SIGHUP,  SIGINT,  SIGQUIT, SIGILL, SIGABRT, SIGFPE,  SIGSEGV, SIGPIPE, SIGALRM,
               SIGTERM, SIGUSR1, SIGUSR2, SIGBUS, SIGTRAP, SIGXCPU, SIGXFSZ, SIGSYS};

struct TerminationHandlerStaticInitializer final {
    TerminationHandlerStaticInitializer() {
        for (int sig : terminable_signals) {
            struct sigaction sa {};
            sa.sa_handler = processSigTerminationHandler;
            sigemptyset(&sa.sa_mask);
            sa.sa_flags = 0;
            sigaction(sig, &sa, nullptr);
        }

        atexit(processNormalTerminationHandler);
    }
};
TerminationHandlerStaticInitializer handler_static_init;

}  // namespace Detail

System::System(
    SystemID id, const std::string &system_name, const fs::path &output_dir,
    cr::milliseconds default_sample_period, size_t msg_write_size_threshold)
    : system_id(id),
      system_name(system_name),
      output_dir(output_dir),
      msg_write_size_threshold(msg_write_size_threshold),
      default_sample_period(default_sample_period) {
    LOG(INFO) << absl::StrFormat(
        "[MSys] #%u (%s) initialized with "
        "default sample period %ld ms, output dir %s",
        system_id, getSystemName().data(), default_sample_period.count(),
        output_dir.string().c_str());
}

System::~System() { LOG(INFO) << absl::StrFormat("[MSys] #%u destructed", system_id); }

SystemID System::getSystemID() const { return system_id; }

const std::string_view System::getSystemName() const {
    return system_name.empty() ? system_default_name : std::string_view(system_name);
}

bool System::addMeter(std::unique_ptr<Meter> &&m) noexcept {
    std::unique_lock<std::mutex> lock(operation_status_mutex);
    if (!in_operation) {
        meter_list.push_back(std::move(m));
        return true;
    }
    return false;
}

bool System::startRecording() {
    std::unique_lock<std::mutex> lock(operation_status_mutex);
    if (!in_operation) {
        // start the worker threads

        if (!isValid()) {
            LOG(FATAL) << absl::StrFormat(
                "[MSys] #%u (%s) has at least one invalid meter", system_id,
                getSystemName().data());
        }

        // FIXME: currently we only support meters with the same sample period as
        // the system default
        for (const std::unique_ptr<Meter> &meter : meter_list) {
            if (meter->getTickPeriod() != default_sample_period) {
                LOG(FATAL) << absl::StrFormat(
                    "[MSys] For system #%d (%s), meter %s has a tick period %d ms, "
                    "which is not equal to the system default sample period %d ms, "
                    "currently only supports meters with the same sample period as the "
                    "system default",
                    system_id, meter->getName().data(), meter->getTickPeriod().count(),
                    default_sample_period.count());
                // cannot reach here
            }
        }

        std::unordered_set<std::string> output_files;
        for (unsigned meter_idx = 0; meter_idx < meter_list.size(); meter_idx++) {
            const std::unique_ptr<Meter> &meter = meter_list[meter_idx];

            meter->assignOutputDir(output_dir);
            fs::path file_path = meter->getOutputPath();
            if (!output_files.insert(file_path.string()).second) {
                LOG(FATAL) << absl::StrFormat(
                    "[MSys] Meter %s at index %d has the "
                    "same output file path as another meter",
                    meter->getName().data(), meter_idx);
                // cannot reach here
            }
        }

        // create the worker info, which will spawn the worker threads
        worker_info = std::make_unique<WorkerInfo>(this, meter_list.size());

        in_operation = true;
        return true;
    }
    return false;
}

bool System::stopRecording() noexcept {
    std::unique_lock<std::mutex> lock(operation_status_mutex);
    if (in_operation) {
        // halt the system and all worker threads
        halt();

        in_operation = false;
        return true;
    }
    return false;
}

bool System::isRecording() {
    std::unique_lock<std::mutex> lock(operation_status_mutex);
    return in_operation;
}

const fs::path &System::getOutputDir() const { return output_dir; }

void System::reportStatus(bool verbose, bool detail) noexcept {
    std::string report = "";

    std::unique_lock<std::mutex> lock(operation_status_mutex);

    absl::StrAppendFormat(
        &report, "# === System Status Report on Instance #%u (%s) ===\n", system_id,
        in_operation ? "In Operation" : "Not In Operation");

    absl::StrAppendFormat(&report, "  System Name: %s\n", getSystemName().data());
    absl::StrAppendFormat(&report, "  Output Dir:  %s\n", output_dir.string());
    absl::StrAppendFormat(&report, "  Has #meter:  %zu\n", meter_list.size());
    for (unsigned meter_idx = 0; meter_idx < meter_list.size(); meter_idx++) {
        const std::unique_ptr<Meter> &meter = meter_list[meter_idx];

        size_t written_times = meter->getWrittenTimes();
        size_t written_size = meter->getWrittenSize();
        size_t cur_msg_wire_size = meter->getCurrentMessageSerializedSize();
        size_t cur_msg_mem_size = meter->getCurrentMessageMemorySize();

        absl::StrAppendFormat(&report, "  Meter #%-4d: %s\n", meter_idx, meter->getName().data());
        absl::StrAppendFormat(
            &report, "    Tick Period:   %d ms\n", meter->getTickPeriod().count());
        absl::StrAppendFormat(&report, "    Written times: %d times\n", written_times);
        absl::StrAppendFormat(
            &report, "    Written size:  %zu B (%.1f MB)\n", written_size,
            (double)written_size / (1024 * 1024));
        absl::StrAppendFormat(
            &report, "    Msg wire size: %zu B (%.1f MB)\n", cur_msg_wire_size,
            (double)cur_msg_wire_size / (1024 * 1024));
        // Show the memory size of the current message
        absl::StrAppendFormat(
            &report, "    Msg mem size:  %u B (%.1f MB)\n", cur_msg_mem_size,
            (double)cur_msg_mem_size / (1024 * 1024));
        if (detail) {
            std::string detail_report = meter->getDetailedReport();
            if (!detail_report.empty()) {
                absl::StrAppendFormat(
                    &report, "    Detailed Report:\n%s\n", indent(detail_report, "      ").c_str());
            } else {
                absl::StrAppendFormat(&report, "    No detailed report available\n");
            }
        }
    }
    absl::StrAppendFormat(&report, "# === Report END ===");

    verbosePrint(verbose, "%s", report.c_str());
}

void System::resetAllBuffers() noexcept {
    std::unique_lock<std::mutex> lock(operation_status_mutex);
    if (in_operation) {
        LOG(ERROR) << absl::StrFormat(
            "[MSys] #%u unexpected buffer reset called while in operation, refuse to take action",
            system_id);
        return;
    }

    resetAllBuffersInternal();
}

void System::resetAllBuffersInternal() noexcept {
    for (std::unique_ptr<Meter> &meter : meter_list) {
        meter->resetBuffer();
    }
}

size_t System::getMsgWriteSizeThreshold() const { return msg_write_size_threshold; }

const cr::milliseconds &System::getDefaultSamplePeriod() const { return default_sample_period; }

bool System::isValid() const {
    for (const std::unique_ptr<Meter> &meter : meter_list)
        if (!meter->isValid()) return false;
    return true;
}

bool System::testRun() {
    {
        std::unique_lock<std::mutex> lock(operation_status_mutex);
        if (in_operation) {
            LOG(ERROR) << absl::StrFormat(
                "[MSys] #%u (%s) cannot perform a test run when the system is already in operation",
                system_id, getSystemName().data());
            return false;
        }
        in_operation = true;
    }

    // Call this function before bails out, in_operation flag will not be reset properly otherwise.
    auto terminate_test_run = [this]() -> void {
        std::unique_lock<std::mutex> lock(operation_status_mutex);
        in_operation = false;
    };

    if (meter_list.empty()) {
        LOG(ERROR) << absl::StrFormat(
            "[MSys] #%u (%s) cannot perform a test run with no meters", system_id,
            getSystemName().data());
        terminate_test_run();
        return false;
    }

    if (!isValid()) {
        std::vector<std::string> meter_names;
        constexpr std::string_view idx_header = "Idx";
        unsigned pad_length =
            std::max(idx_header.size(), (size_t)std::ceil(std::log10(meter_list.size()) + 1));
        for (unsigned meter_idx = 0; meter_idx < meter_list.size(); meter_idx++) {
            const std::unique_ptr<Meter> &m = meter_list[meter_idx];
            meter_names.push_back(
                strPad(meter_idx, pad_length) + ": " + std::string(m->getName().data()) +
                (m->isValid() ? "" : " <= Invalid Meter"));
        }
        LOG(ERROR) << absl::StrFormat(
            "[MSys] #%u (%s) has at least one invalid meter, cannot perform a test run. Detailed "
            "reports:\n  %s: MeterName\n  %s",
            system_id, getSystemName().data(), idx_header.data(),
            strJoin(meter_names.begin(), meter_names.end(), "\n  ").c_str());
        terminate_test_run();
        return false;
    }

    for (unsigned meter_idx = 0; meter_idx < meter_list.size(); meter_idx++) {
        const std::unique_ptr<Meter> &meter = meter_list[meter_idx];
        if (!meter->isValid()) {
            std::vector<std::string> meter_names;
            meter_names[meter_idx] += " <= Invalid Meter";
            const std::string meter_hints = strJoin(meter_names.begin(), meter_names.end(), "\n  ");
            LOG(ERROR) << absl::StrFormat(
                "[MSys] #%u (%s) has invalid meter %s at index %d, cannot perform a test run",
                system_id, getSystemName().data(), meter->getName().data(), meter_idx);
            terminate_test_run();
            return false;
        }
    }

    bool ret = true;
    LOG(INFO) << absl::StrFormat(
        "[MSys] #%u (%s) test run started, will update all %zu meters", system_id,
        getSystemName().data(), meter_list.size());
    resetAllBuffersInternal();

    size_t msg_write_size_threshold = getMsgWriteSizeThreshold();
    size_t sample_period_ms = getDefaultSamplePeriod().count();
    size_t total_wire_size = 0;
    for (unsigned meter_idx = 0; meter_idx < meter_list.size(); meter_idx++) {
        std::unique_ptr<Meter> &meter = meter_list[meter_idx];

        LOG(INFO) << absl::StrFormat(
            "[MSys] System #%u (%s) Meter #%u (%s) test run started", system_id,
            getSystemName().data(), meter_idx, meter->getName().data());
        cr::time_point<cr::steady_clock> start = cr::steady_clock::now();
        bool meter_ret = meter->update(true);
        cr::time_point<cr::steady_clock> end = cr::steady_clock::now();
        // calculate the duration of the update
        cr::microseconds duration = cr::duration_cast<cr::microseconds>(end - start);

        // get a rough idea of the meter write interval
        size_t current_wire_size = meter->getCurrentMessageSerializedSize();
        size_t nwrites =
            current_wire_size == 0
                ? 0
                : (msg_write_size_threshold + current_wire_size - 1) / current_wire_size;
        double avg_write_interval_ms =
            (double)sample_period_ms * msg_write_size_threshold / current_wire_size;
        total_wire_size += current_wire_size;

        if (current_wire_size == 0) {
            LOG(ERROR) << absl::StrFormat(
                "[MSys] System #%u (%s) Meter #%u (%s) message wire size 0", system_id,
                getSystemName().data(), meter_idx, meter->getName().data());
            meter_ret = false;
        }

        if (meter_ret) {
            LOG(INFO) << absl::StrFormat(
                "[MSys] System #%u (%s) Meter #%u (%s) test run succeeded.\n"
                "  - Write threshold: %zu B (%.2f MB), Single write size: %zu B (%.2f "
                "kB)\n"
                "    Avg write interval: %.2f ms (%.2f s, %.2f h), %zu writes "
                "expected\n"
                "  - Update period: %ld ms, Actual update duration: %.3f ms (%.2f%%)",
                system_id, getSystemName().data(), meter_idx, meter->getName().data(),
                msg_write_size_threshold, (double)msg_write_size_threshold / (1024 * 1024),
                current_wire_size, (double)current_wire_size / 1024, avg_write_interval_ms,
                avg_write_interval_ms / 1000.0, avg_write_interval_ms / (1000 * 3600.0), nwrites,
                sample_period_ms, duration.count() / 1000.0,
                duration.count() / 1000.0 / sample_period_ms * 100.0);
        } else {
            LOG(ERROR) << absl::StrFormat(
                "[MSys] System #%u (%s) Meter #%u (%s) test run FAILED", system_id,
                getSystemName().data(), meter_idx, meter->getName().data());
        }
        ret &= meter_ret;
    }
    double write_size_per_sec = (double)total_wire_size / sample_period_ms * 1000.0;
    LOG(INFO) << absl::StrFormat(
        "[MSys] System #%u (%s) test run finished, total wire size: %zu B (%.2f "
        "MB), "
        "write size per second: %.2f B/s (%.2f MB/s %.2f MB/h)",
        system_id, getSystemName().data(), total_wire_size, (double)total_wire_size / (1024 * 1024),
        write_size_per_sec, write_size_per_sec / (1024 * 1024),
        write_size_per_sec / (1024 * 1024) * 3600);

    resetAllBuffersInternal();
    for (std::unique_ptr<Meter> &meter : meter_list) {
        if (meter->getCurrentMessageSerializedSize() > 0) {
            LOG(FATAL) << absl::StrFormat(
                "[MSys] Meter %s has non-empty message after test run", meter->getName().data());
            ret = false;
        }
    }

    terminate_test_run();
    return ret;
}

bool System::update() noexcept {
    bool ret = true;
    for (std::unique_ptr<Meter> &meter : meter_list) {
        bool r = meter->update();
        if (!r) {
            fprintf(stderr, "[MSys] Meter %s update FAILED\n", meter->getName().data());
            ret = false;
        }
        // ret &= meter->update();
    }
    return ret;
}

void System::halt() noexcept {
    // Instantly wake up all the worker threads spawned and tell them to exit
    // gracefully by calling the destructor of WorkerInfo
    worker_info.reset();

    // Persist all remaining data that registered in memory
    for (const std::unique_ptr<Meter> &meter : meter_list) {
        // make the async function wait for completion before return
        meter->writeDataToFile(true);
        meter->fsyncDataToFile();
    }

    if (in_operation)
        LOG(INFO) << absl::StrFormat("[MSys] #%u halted", system_id);
    else
        LOG(INFO) << absl::StrFormat("[MSys] #%u not in operation", system_id);
}

WorkerInfo::WorkerInfo(System *system, unsigned nmeters)
    : system(system),
      worker_sync_point(nmeters + 1),  // +1 for the coordinator thread
      worker_stop(false),
      meter_update_durations(nmeters, std::deque<uint64_t>()),
      meter_thread_finish_times(nmeters, 0),
      system_creation_time(cr::steady_clock::now()),
      coordinator_thread(&WorkerInfo::coordinator_thread_func, this) {
    // create the worker threads, each thread will handle a subset of meters
    for (unsigned meter_idx = 0; meter_idx < nmeters; meter_idx++) {
        worker_threads.emplace_back(&WorkerInfo::worker_thread_func, this, meter_idx);
    }
    LOG(INFO) << absl::StrFormat(
        "[MSys WorkerPool] Worker pool for MSys #%u constructed with %zu meters",
        system->getSystemID(), nmeters);
}

WorkerInfo::~WorkerInfo() {
    // send a signal to attempt to stop all worker threads
    worker_stop.store(true);

    LOG(INFO) << absl::StrFormat(
        "[MSys WorkerPool] Stopping spawned threads for "
        "MSys #%u, waiting for threads to join...",
        system->system_id);
    // wait for all worker threads to finish
    coordinator_thread.join();
    for (std::thread &t : worker_threads) {
        t.join();
    }
    worker_threads.clear();

    LOG(INFO) << absl::StrFormat(
        "[MSys WorkerPool] Worker pool for MSys #%u destructed", system->getSystemID());
}

void WorkerInfo::coordinator_thread_func() {
    unsigned long msg_write_size_threshold = system->getMsgWriteSizeThreshold();
    cr::time_point<cr::steady_clock> next_round_time =
        system_creation_time + system->default_sample_period;
    while (true) {
        // wait for the signal to stop
        std::this_thread::sleep_until(next_round_time);

        // exit the thread if stop signal is received
        if (worker_stop.load()) {
            // FIXME: discard a function labeled with [[nodiscard]]
            (void)worker_sync_point.arrive_and_drop();
            break;
        }

        // notify all worker threads to start a new round of profiling
        worker_sync_point.arrive_and_wait();

        // wait for all worker threads to finish their work in this round
        worker_sync_point.arrive_and_wait();

        for (const std::unique_ptr<Meter> &meter : system->meter_list) {
            if (meter->getCurrentMessageSerializedSize() >= msg_write_size_threshold) {
                meter->writeDataToFile();
            }
        }

        cr::time_point<cr::steady_clock> round_finish_time = cr::steady_clock::now();
        next_round_time += system->default_sample_period;

        cr::milliseconds time_remaining =
            cr::duration_cast<cr::milliseconds>(next_round_time - round_finish_time);

        const double warning_frac = 0.1;  // 10% of the sample period
        int time_remaining_ms = cr::duration_cast<cr::milliseconds>(time_remaining).count();
        unsigned default_sample_period_ms =
            cr::duration_cast<cr::milliseconds>(system->default_sample_period).count();

        if (time_remaining_ms < warning_frac * default_sample_period_ms) {
            LOG(WARNING) << absl::StrFormat(
                "[MSys WorkerPool] Coordinator thread for MSys #%u (%s): "
                "Next round time %ld ms is too close to the current round finish time %ld ms. "
                "Only %ld ms remaining, less than %.2f%% of the sample period (%ld ms). "
                "Consider increasing the sample period.",
                system->getSystemID(), system->getSystemName().data(),
                cr::duration_cast<cr::milliseconds>(next_round_time.time_since_epoch()).count(),
                cr::duration_cast<cr::milliseconds>(round_finish_time.time_since_epoch()).count(),
                time_remaining_ms, (double)time_remaining_ms / default_sample_period_ms * 100.0,
                default_sample_period_ms);
        }
    }
}

void WorkerInfo::worker_thread_func(const unsigned meter_idx) {
    const std::unique_ptr<Meter> &meter = system->meter_list[meter_idx];

    while (true) {
        // wait for coordination signal
        worker_sync_point.arrive_and_wait();

        // exit the thread if stop signal is received
        if (worker_stop.load()) {
            worker_sync_point.arrive_and_drop();
            break;
        }

        cr::time_point start = cr::high_resolution_clock::now();
        meter->update();
        cr::time_point end = cr::high_resolution_clock::now();

        meter_update_durations[meter_idx].push_back(
            std::chrono::duration_cast<cr::nanoseconds>(end - start).count());

        meter_thread_finish_times[meter_idx] =
            cr::high_resolution_clock::now().time_since_epoch().count();

        // notify the coordinator thread that this worker thread has finished
        worker_sync_point.arrive_and_wait();
    }
}

bool msysInitialize(const std::string &log_dir) {
    Detail::systemOnceInitialized = true;
    return loggerInitialize(log_dir);
}

// FIXME: currently it seems with templated function called from interface an
// undefined symbol error will be raised when importing the library. Hide this
// templated implementation now and use a explicit one.
// template <typename... Args>
// SystemID constructNewSystem(Args &&...args) {
//     using Detail::existing_systems, Detail::system_index_generator;

//     SystemID idx;
//     do {
//         idx = system_index_generator();
//     } while (existing_systems.find(idx) != existing_systems.end());
//     existing_systems.emplace(
//         idx, std::make_shared<System>(std::forward<Args>(args)...)
//     );
//     return idx;
// }

/**
 * Construct a monitoring system and return its index as an identifier to access
 * that instance
 *
 * @note this method is NOT thread-safe
 * @return an ID associated with the system
 */
SystemID constructNewSystem(
    const std::string &output_dir, unsigned default_sample_period_ms,
    const std::string &system_name, const size_t msg_write_size_threshold) {
    using Detail::existing_systems;

    SystemID id = Detail::getNewSystemID();

    fs::path output_dir_path = validateDir(output_dir);
    if (output_dir_path.empty()) return invalidSystemID;

    existing_systems.emplace(
        id, std::make_shared<System>(
                id, system_name, output_dir_path, cr::milliseconds{default_sample_period_ms},
                msg_write_size_threshold));
    return id;
}

std::shared_ptr<System> retrieveSystemUsingIndex(SystemID id) {
    using Detail::existing_systems;

    auto result = existing_systems.find(id);
    if (result == existing_systems.end()) {
        return nullptr;
    }
    return result->second;
}

bool msysTestRun(SystemID id) {
    std::shared_ptr<System> system = retrieveSystemUsingIndex(id);
    if (!system) return false;

    bool ret = system->update();
    system->resetAllBuffers();
    return ret;
}

}  // namespace MSys
