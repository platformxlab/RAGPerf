#include "include/meter.hh"

#include <fcntl.h>

namespace MSys {

Meter::Meter(
    const std::string &name, cr::milliseconds tick_period,
    std::function<proto::Message *()> stat_tser_factory, const std::string &file_suffix)
    : name(name),
      file_suffix(file_suffix),
      tick_period(tick_period),
      stat_tser(stat_tser_factory()),
      stat_tser_dbuffer(stat_tser_factory()) {
    if (!stat_tser || !stat_tser_dbuffer) {
        LOG(FATAL) << absl::StrFormat(
            "[Meter] %s stat_tser or stat_tser_dbuffer is null", name.c_str());
    }
}

Meter::~Meter() {
    // make sure writes are completed before destruction
    std::default_delete deleter = async_write_ret.get_deleter();
    std::future<void> *async_write_ret_ptr = async_write_ret.release();
    if (async_write_ret_ptr && async_write_ret_ptr->valid()) {
        async_write_ret_ptr->wait();
    }
    deleter(async_write_ret_ptr);

    // release all resources
    close(fd);
    google::protobuf::Message *stat_tser_dbuffer_inst =
        stat_tser_dbuffer.exchange(nullptr, std::memory_order_acquire);
    delete stat_tser;
    delete stat_tser_dbuffer_inst;
    LOG(INFO) << absl::StrFormat("[Meter] %s destructed", name.c_str());
}

void Meter::resetBuffer() noexcept {
    stat_tser->Clear();
    stat_tser_dbuffer.load()->Clear();
}

ssize_t Meter::writeDataToFile(bool sync) noexcept {
    if (unlikely(!stat_tser || stat_tser->ByteSizeLong() == 0)) return 0;
    if (unlikely(!sync && fd < 0)) {
        LOG(FATAL) << absl::StrFormat(
            "[Meter] %s file descriptor is not set, cannot write data", name.c_str());
        return -1;
    }

    if (unlikely(sync && fd < 0)) return -1;

    proto::Message *cur_dbuffer = stat_tser_dbuffer.exchange(nullptr, std::memory_order_acquire);
    if (unlikely(!cur_dbuffer)) {
        LOG(WARNING) << absl::StrFormat(
            "[Meter] %s stat_tser_dbuffer is null, "
            "last write have not yet returned",
            name.c_str());
        return -1;
    }

    proto::Message *cur_stat_tser = stat_tser;
    stat_tser = cur_dbuffer;

    size_t current_msg_wire_size = cur_stat_tser->ByteSizeLong();

    // Write the current stat_tser to the file descriptor asynchronously
    // This is to avoid blocking the current thread
    async_write_ret = std::make_unique<std::future<void>>(
        std::async(std::launch::async, [this, cur_stat_tser, current_msg_wire_size]() -> void {
            // Do !!!NOT!!! touch stat_tser in this function, it is used by current
            // thread

            // write header, which is the size of the current message in wire format
            ssize_t msg_size_written_size =
                write(fd, &current_msg_wire_size, sizeof(current_msg_wire_size));
            // write the message itself
            bool success = cur_stat_tser->SerializeToFileDescriptor(fd);

            written_times++;
            written_size += msg_size_written_size + current_msg_wire_size;

            // clear the buffer after the write is done
            cur_stat_tser->Clear();

            if (msg_size_written_size < 0 || !success) {
                LOG(ERROR) << absl::StrFormat(
                    "[Meter] %s failed to write data to file descriptor %d "
                    "[error: %d (%s), proto error: %c]",
                    name.c_str(), fd, errno, strerror(errno), success ? 'y' : 'n');
            }

            // store the current stat_tser back to the atomic buffer to signal write
            // completion
            stat_tser_dbuffer.store(cur_stat_tser, std::memory_order_release);
        }));
    if (sync) {
        // wait for the async write to finish if sync is true
        LOG(INFO) << absl::StrFormat("[Meter] %s waiting for async func to finish", name.c_str());
        async_write_ret->wait();
    }

    return current_msg_wire_size;
}

void Meter::fsyncDataToFile() noexcept {
    if (fd < 0) return;

    if (fsync(fd) < 0) {
        LOG(ERROR) << absl::StrFormat(
            "[Meter] %s failed to fsync file descriptor %d, error: %d (%s)", name.c_str(), fd,
            errno, strerror(errno));
    }
}

void Meter::assignOutputDir(const fs::path &output_dir) {
    file_path = output_dir / (name + file_suffix);
    fd = open(file_path.c_str(), O_WRONLY | O_CREAT | O_TRUNC, 0644);
    if (fd < 0) {
        LOG(FATAL) << absl::StrFormat(
            "[Meter] %s failed to open file %s for writing, error: %d (%s)", name.c_str(),
            file_path.string().c_str(), errno, strerror(errno));
        return;
    }

    // convert the file path to a canonical path
    std::error_code ec;
    file_path = fs::weakly_canonical(file_path, ec);
}

const fs::path &Meter::getOutputPath() const { return file_path; }

size_t Meter::getWrittenTimes() const { return written_times; }

size_t Meter::getWrittenSize() const { return written_size; }

const std::string_view Meter::getName() const { return std::string_view(name); }

const cr::milliseconds Meter::getTickPeriod() const { return tick_period; }

size_t Meter::getCurrentMessageMemorySize() {
    if (!stat_tser) return 0;
    return stat_tser->SpaceUsedLong();
}

size_t Meter::getCurrentMessageSerializedSize() {
    if (!stat_tser) return 0;
    return stat_tser->ByteSizeLong();
}

std::string Meter::getDetailedReport() const { return ""; }

bool Meter::isValid() const { return is_valid; }

void Meter::markValid() { is_valid = true; }

}  // namespace MSys
