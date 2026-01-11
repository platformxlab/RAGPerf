#pragma once

#include <barrier>
#include <condition_variable>
#include <thread>

#include "include/utils.hh"

#include "include/cpu_meter.hh"
#include "include/disk_meter.hh"
#include "include/gpu_meter.hh"
#include "include/mem_meter.hh"
#include "include/proc_meter.hh"

namespace MSys {

namespace Detail {

void processTerminationHandler(bool);

}  // namespace Detail

typedef int SystemID;
constexpr SystemID invalidSystemID = static_cast<SystemID>(-1);

// Forward declaration
class WorkerInfo;

static constexpr size_t default_msg_write_size_threshold = 1 * 1024 * 1024;  // 2 MiB

class System final {
  public:
    System(
        SystemID id, const std::string &system_name, const fs::path &output_dir,
        cr::milliseconds default_sample_period, const size_t msg_write_size_threshold);

    // disable copy constructor
    System(const System &) = delete;
    System &operator=(const System &) = delete;

    // disable move constructors
    System(System &&) = delete;
    System &operator=(System &&) = delete;

    ~System();

  public:
    /* NOTE: The following functions are used to manage the operation status of the system when the
     * system is not running. The functions that are not explicitly marked as noexcept may throw
     * exceptions if some conditions are not met. Refer to the documentation of each function for
     * more details. */

    /**
     * Add a meter to the system.
     *
     * @param m Meter to be added
     * @return Whether the meter is added successfully
     *
     * @note Will attempt to grab operation status mutex and check for system idleness.
     */
    bool addMeter(std::unique_ptr<Meter> &&m) noexcept;

    /**
     * Start the system recording, start all the meter threads and begin to record data.
     *
     * @exception assertion_error thrown if the system is not correctly initialized.
     * @return Whether the system is started successfully.
     *
     * @note Will attempt to grab operation status mutex and check for system idleness.
     * @note An exception will be thrown if the system is not correctly initialized to avoid silent
     *       failures, so false is only returned when the system is already in operation.
     */
    bool startRecording();

    /**
     * Stop the system recording, stop all the meter threads and persist all the data to disk.
     *
     * @return Whether the system is stopped successfully
     *
     * @note Will attempt to grab operation status mutex and check for system idleness.
     */
    bool stopRecording() noexcept;

    /**
     * Report the current status of the system in human-readable format
     *
     * @param verbose If true, print to stdout, print use logger otherwise
     *
     * @note Will attempt to grab operation status mutex and check for system idleness.
     */
    void reportStatus(bool verbose = false, bool detail = false) noexcept;

    /**
     * Perform a test run of the system, this will update all the meters in the system and return
     * true if all the meters are updated successfully, false otherwise.
     *
     * @return True if all meters are tested and are are updated successfully without any errors,
     *         false otherwise
     *
     * @note Will attempt to grab operation status mutex and check for system idleness.
     * @note This function will reset all the buffers of the meters before and after the test run.
     *       If the system is already in operation, the function will bail and return false.
     */
    bool testRun();

    /**
     * Reset all the buffers of the meters in the system
     *
     * @note Will attempt to grab operation status mutex and check for system idleness.
     * @note This function will bail if the system is in operation, and will not reset the buffers
     */
    void resetAllBuffers() noexcept;

  private:
    /**
     * Reset all the buffers of the meters in the system without checking if the system is in
     * operation
     */
    void resetAllBuffersInternal() noexcept;

  public:
    /* NOTE: The following functions are used to update the system while the
     * system is running. The functions that are not explicitly marked as
     * noexcept may throw exceptions if some conditions are not met. Refer
     * to the documentation of each function for more details. */

    /**
     * Update the system, this will call the update function of all the meters in the system, and
     * return true if all the meters are updated successfully, false otherwise.
     *
     * @return True if all meters are updated successfully, false otherwise
     */
    bool update() noexcept;

  private:
    /**
     * Check if the system is currently recording
     *
     * @return True if the system is recording, false otherwise
     *
     * @note Will attempt to grab operation status mutex and check for system idleness.
     */
    bool isRecording();

  public:
    static constexpr std::string_view system_default_name = "<Anonymous>";
    SystemID getSystemID() const;
    const std::string_view getSystemName() const;
    const fs::path &getOutputDir() const;
    size_t getMsgWriteSizeThreshold() const;
    const cr::milliseconds &getDefaultSamplePeriod() const;
    /**
     * Check if all the meters in the system is valid
     *
     * @return True if the all meters are valid, false otherwise
     *
     * @note This function assumes the operation status mutex is locked
     */
    bool isValid() const;

  private:
    /**
     * Halt the system and all worker threads, this will stop all the recording and persist all the
     * data to disk.
     *
     * @note This function assumes the operation status mutex is locked
     */
    void halt() noexcept;

  private:
    const SystemID system_id;
    const std::string system_name;

    const fs::path output_dir;
    const size_t msg_write_size_threshold;
    const cr::milliseconds default_sample_period;

    // state of the system running info
    mutable std::mutex operation_status_mutex;
    bool in_operation = false;

    // affiliated threads info
    std::unique_ptr<WorkerInfo> worker_info = nullptr;

    // meters
    std::vector<std::unique_ptr<Meter>> meter_list;

  public:
    friend class WorkerInfo;
    // termination handler needs monitoring system internal states
    friend void Detail::processTerminationHandler(bool);
};

class WorkerInfo {
  public:
    WorkerInfo() = delete;
    WorkerInfo(System *, unsigned nmeters);
    ~WorkerInfo();

  private:
    void coordinator_thread_func();
    void worker_thread_func(const unsigned thread_idx);

    System *system;
    std::barrier<> worker_sync_point;
    std::atomic<bool> worker_stop;

    FixedSizeVector<std::deque<uint64_t>> meter_update_durations;
    FixedSizeVector<uint64_t> meter_thread_finish_times;

    const cr::time_point<cr::steady_clock> system_creation_time;

    std::thread coordinator_thread;
    std::vector<std::thread> worker_threads;
};

bool msysInitialize(const std::string &log_dir);

// template <typename... Args>
// SystemID constructNewSystem(Args &&...args);
SystemID constructNewSystem(
    const std::string &output_dir, unsigned default_sample_period_ms,
    const std::string &system_name = "",
    const size_t msg_write_size_threshold = default_msg_write_size_threshold);
std::shared_ptr<System> retrieveSystemUsingIndex(SystemID id);
bool msysTestRun();

}  // namespace MSys
