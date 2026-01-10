#pragma once

#include <future>
#include <mutex>

#include "include/utils.hh"

namespace MSys {

constexpr cr::milliseconds period_step{100};

class Meter {
  public:
    Meter(
        const std::string &name, cr::milliseconds tick_period,
        std::function<proto::Message *()> stat_tser_factory,
        const std::string &file_suffix = std::string(file_default_suffix));

    /* Disable copy constructor */
    Meter(const Meter &) = delete;

    virtual ~Meter();

    /**
     * Probe once for statistics specified in the probe
     * @return true if the probe was successful, false otherwise
     */
    virtual bool update(bool testrun = false) = 0;

    virtual void resetBuffer() noexcept final;

  public:
    const std::string_view getName() const;
    const cr::milliseconds getTickPeriod() const;

  public:
    /**
     * Get the estimated memory consumption of current stat protobuf, calls
     * internal <protobuf>.SpaceUsedLong()
     *
     * @return approximate memory consumption for the message in bytes
     */
    virtual size_t getCurrentMessageMemorySize() final;

    /**
     * Get the exact binary wire format size of current stat protobuf, calls
     * internal <protobuf>.ByteSizeLong()
     *
     * @return exact binary wire format size for the message in bytes
     */
    virtual size_t getCurrentMessageSerializedSize() final;

    virtual std::string getDetailedReport() const;

  public:
    static constexpr std::string_view file_default_suffix = ".pb.bin";

  protected:
    /** Name of the meter, used in human-readable reports */
    const std::string name;
    /** Suffix of the file, used in file output */
    const std::string file_suffix;
    /** Meter record interval, in miliseconds */
    const cr::milliseconds tick_period;

  protected:
    template <IsProtoMessage T>
    T *getCurrentBuffer() const;

  private:
    /** Result protobuf time series */
    proto::Message *stat_tser;
    std::atomic<proto::Message *> stat_tser_dbuffer;

  public:
    // === File I/O ===
    /**
     * Write the current stat_tser to the file descriptor asynchronously,
     * this function will return immediately and the actual writing is done
     * in a separate thread using std::async.
     *
     * @note sync option does NOT mean the file content will be synced
     * @param sync if true, wait for the write to finish before returning
     * @return the size of expected written data in bytes, or -1 on error
     */
    virtual ssize_t writeDataToFile(bool sync = false) noexcept final;

    /**
     * Force the file descriptor to sync to disk, this will ensure that all
     * the data written to the file descriptor is flushed to disk.
     *
     * @note this function does NOT write any data to the file descriptor,
     * it only flushes the data already written.
     */
    virtual void fsyncDataToFile() noexcept final;

  public:
    virtual void assignOutputDir(const fs::path &output_dir) final;
    virtual const fs::path &getOutputPath() const final;
    virtual size_t getWrittenTimes() const final;
    virtual size_t getWrittenSize() const final;

  private:
    fs::path file_path;
    int fd = -1;
    std::unique_ptr<std::future<void>> async_write_ret;
    std::atomic<size_t> written_times = 0;
    std::atomic<size_t> written_size = 0;

  public:
    bool isValid() const;

  protected:
    void markValid();

  private:
    bool is_valid = false;
};

}  // namespace MSys

#include "include/meter.ipp"
