#include <fstream>
#include <functional>
#include <mutex>

#include <absl/base/log_severity.h>
#include <absl/log/globals.h>
#include <absl/log/log_sink_registry.h>

#include "date/date.h"
#include "date/tz.h"
#include "include/logger.hh"

namespace MSys {

namespace Detail {

constexpr cr::duration flush_interval_seconds = cr::seconds(60);

class FileLogSink : public absl::LogSink {
  public:
    explicit FileLogSink(const std::string &filename) : filename(filename) {
        last_flush_time = cr::steady_clock::now();
    }

    ~FileLogSink() override {
        if (log_file_.is_open()) {
            log_file_.flush();
            log_file_.close();
            std::chrono::system_clock::time_point now = std::chrono::system_clock::now();
            fprintf(
                stderr, "[FileLogSink] Log file saved to %s:0 (at %s)\n", filename.c_str(),
                date::format("%Y-%m-%d %H:%M:%S %z", date::make_zoned(date::current_zone(), now))
                    .c_str());
        }
    }

    void Send(const absl::LogEntry &entry) override {
        std::lock_guard<std::mutex> lock(mu_);
        // lazy file allocation
        if (!log_file_.is_open()) {
            log_file_.open(filename, std::ios::out | std::ios::app);
            assert(log_file_.is_open());
        }
        log_file_ << entry.text_message_with_prefix_and_newline_c_str();

        cr::steady_clock::time_point current_time = cr::steady_clock::now();
        if (current_time - last_flush_time >= flush_interval_seconds) {
            log_file_.flush();
            last_flush_time = current_time;
        }
    }

  private:
    const std::string filename;
    std::ofstream log_file_;
    std::mutex mu_;

    cr::steady_clock::time_point last_flush_time;
};

class Logger {
  public:
    static constexpr std::string_view log_filename = "libmsys.log";
    static constexpr std::string_view term_report_filename = "libmsys.term.log";

    /**
     * Assumes the input log path is a valid directory.
     *
     * @param log_dir directory to store logs
     */
    Logger(const fs::path &log_dir)
        : log_dir(log_dir),
          log_file_path(log_dir / log_filename.data()),
          term_report_file_path(log_dir / term_report_filename.data()) {
        absl::InitializeLog();
        if (log_dir.empty()) {
            absl::SetStderrThreshold(absl::LogSeverityAtLeast::kInfo);
            LOG(INFO) << "[Logger] Initialized with no log directory, logging to stderr.";
        } else {
            file_sink = new FileLogSink(log_file_path);
            absl::AddLogSink(file_sink);
            absl::SetStderrThreshold(absl::LogSeverityAtLeast::kError);
        }
    }

    ~Logger() {
        if (log_dir.empty()) return;
        absl::RemoveLogSink(file_sink);
        delete file_sink;
    }

    const fs::path &getLoggerFolder() { return log_dir; }

    const fs::path &getLoggerFile() { return log_file_path; }

    const fs::path &getTermReportFile() { return term_report_file_path; }

  private:
    const fs::path log_dir;
    const fs::path log_file_path;
    const fs::path term_report_file_path;
    FileLogSink *file_sink = nullptr;
};

static Logger *logger = nullptr;

}  // namespace Detail

// this is not thread safe
bool loggerInitialize(const std::string &log_dir) {
    if (Detail::logger) return false;

    if (log_dir.empty()) {
        Detail::logger = new Detail::Logger(fs::path());
    } else {
        fs::path p = validateDir(log_dir);
        if (p.empty()) {
            LOG(ERROR) << absl::StrFormat("[Logger] Invalid log dir %s", log_dir.c_str());
            return false;
        }
        if (access(p.c_str(), W_OK)) {
            LOG(ERROR) << absl::StrFormat("[Logger] Cannot write to log dir %s", p.c_str());
            return false;
        }

        Detail::logger = new Detail::Logger(p);
    }
    return true;
}

const fs::path &getLoggerFolder() { return Detail::logger->getLoggerFolder(); }

const fs::path &getLoggerFile() { return Detail::logger->getLoggerFile(); }

void loggerDeinitialize() {
    if (Detail::logger) {
        delete Detail::logger;
        Detail::logger = nullptr;
    }
}

}  // namespace MSys
