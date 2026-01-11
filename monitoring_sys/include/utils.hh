#pragma once

#include <assert.h>
#include <inttypes.h>
#include <chrono>
#include <cstdint>
#include <filesystem>

// cuda monitoring
#include <cupti.h>
#include <nvml.h>

// absl logging
#include <absl/log/check.h>
#include <absl/log/flags.h>
#include <absl/log/initialize.h>
#include <absl/log/log.h>
#include <absl/log/log_entry.h>
#include <absl/log/log_sink.h>
// other absl
#include <absl/strings/str_format.h>

// protobuf
#include <google/protobuf/message.h>

// export functions
#define MSYS_EXPORT __attribute__((__visibility__("default")))
#define MSYS_HIDDEN __attribute__((__visibility__("hidden")))

// global namespace alias
namespace cr = std::chrono;
namespace fs = std::filesystem;
namespace proto = google::protobuf;

// copied from LinuxMachine.h from htop (https://github.com/htop-dev/htop)
#ifndef PROCDIR
#define PROCDIR "/proc"
#endif

#ifndef PROCCPUINFOFILE
#define PROCCPUINFOFILE PROCDIR "/cpuinfo"
#endif

// used in /proc/stat and /proc/<pid>/stat
#ifndef STATFILE
#define STATFILE "/stat"
#endif

#ifndef STATMFILE
#define STATMFILE "/statm"
#endif

#ifndef IOFILE
#define IOFILE "/io"
#endif

#ifndef PROCSTATFILE
#define PROCSTATFILE PROCDIR STATFILE
#endif

#ifndef PROCMEMINFOFILE
#define PROCMEMINFOFILE PROCDIR "/meminfo"
#endif

#ifndef PROCDISKSTATSFILE
#define PROCDISKSTATSFILE PROCDIR "/diskstats"
#endif

// global helpper macro
#define printerr(...) fprintf(stderr, ##__VA_ARGS__)

#define MSYS_EXPAND(x)    x
#define MSYS_STRINGIFY(x) #x
#define MSYS_TOSTRING(x)  MSYS_STRINGIFY(x)

#define UNUSED(x) (void)(x)

#if defined(__GNUC__) || defined(__clang__)
#define unlikely(x) __builtin_expect(!!(x), 0)
#define likely(x)   __builtin_expect(!!(x), 1)
#else
#define unlikely(x) (x)
#define likely(x)   (x)
#endif

#define nvmlCall(ret)                                                                              \
    do {                                                                                           \
        if (ret != NVML_SUCCESS) {                                                                 \
            LOG(ERROR) << absl::StrFormat(                                                         \
                "NVML call failed with return value %d (%s)", (int)ret, nvmlErrorString(ret));     \
        }                                                                                          \
    } while (false)

// global helpper constexpr
template <typename T>
constexpr unsigned log2Floor(T x);

template <typename T>
constexpr unsigned log10Floor(T x);

template <typename T>
constexpr unsigned log2Ceil(T x);

template <typename T>
constexpr unsigned log10Ceil(T x);

// concepts
template <typename T>
concept IsProtoMessage = std::is_base_of<proto::Message, T>::value;

// global helpper function
unsigned getSystemNProc();
unsigned getSystemHz();
cr::nanoseconds nsSinceEpoch();

/**
 * @brief Indent each line of a string with a given prefix.
 * @note This function is expensive because it format strings in a pretty way.
 * @param input The input string to indent.
 * @param prefix The prefix to add to each line.
 * @return A new string with each line indented by the prefix.
 */
std::string indent(const std::string &input, const std::string &prefix);

/**
 * @brief Pad a value with designated character to a specified width.
 * @param value The value to printed and padded.
 * @param width The desired width.
 * @param fill The character to use for padding.
 * @return A string representation of the padded value.
 */
template <typename T>
std::string strPad(T value, unsigned width, char fill = ' ');

/**
 * @brief Join a range of strings with a separator.
 * @note This function is expensive because it format strings in a pretty way.
 * @param begin The beginning of the range.
 * @param end The end of the range.
 * @param sep The separator to use between elements.
 * @return A single string with all elements joined by the separator.
 */
template <std::input_iterator Iterator>
std::string strJoin(const Iterator &begin, const Iterator &end, const std::string &sep);

/**
 * Validate whether a given path exists in current filesystem and return a
 * fs::path object corresponding to it.
 *
 * @param dir target directory to be examined
 * @return realpath of dir if the directory exists, and empty path if not
 */
fs::path validateDir(const std::string &dir);

template <absl::LogSeverity severity = absl::LogSeverity::kInfo, typename... Args>
void verbosePrint(bool verbose, const char *format, Args... args);

/* Fixed size vector that size can be determined dynamically at runtime by
   marking every size-changing function as private */
template <class T, class Allocator = std::allocator<T>>
class FixedSizeVector : private std::vector<T, Allocator> {
  public:
    using std::vector<T>::vector;
    using std::vector<T>::size;
    using std::vector<T>::operator[];
    using std::vector<T>::begin;
    using std::vector<T>::end;
};

/* Fixed size unordered map that size can be determined dynamically at runtime
   by marking every size-changing function as private */
template <
    class Key, class T, class Hash = std::hash<Key>, class KeyEqual = std::equal_to<Key>,
    class Allocator = std::allocator<std::pair<const Key, T>>>
class FixedSizeUnorderedMap : private std::unordered_map<Key, T, Hash, KeyEqual, Allocator> {
  public:
    using std::unordered_map<Key, T, Hash, KeyEqual, Allocator>::unordered_map;
    using std::unordered_map<Key, T, Hash, KeyEqual, Allocator>::size;
    using std::unordered_map<Key, T, Hash, KeyEqual, Allocator>::operator[];
    using std::unordered_map<Key, T, Hash, KeyEqual, Allocator>::find;
    using std::unordered_map<Key, T, Hash, KeyEqual, Allocator>::begin;
    using std::unordered_map<Key, T, Hash, KeyEqual, Allocator>::end;
};

/* Fixed size unordered set that size can be determined dynamically at runtime
   by marking every size-changing function as private */
template <
    class Key, class Hash = std::hash<Key>, class KeyEqual = std::equal_to<Key>,
    class Allocator = std::allocator<Key>>
class FixedSizeUnorderedSet : private std::unordered_set<Key, Hash, KeyEqual, Allocator> {
  public:
    using std::unordered_set<Key, Hash, KeyEqual, Allocator>::unordered_set;
    using std::unordered_set<Key, Hash, KeyEqual, Allocator>::size;
    using std::unordered_set<Key, Hash, KeyEqual, Allocator>::find;
    using std::unordered_set<Key, Hash, KeyEqual, Allocator>::begin;
    using std::unordered_set<Key, Hash, KeyEqual, Allocator>::end;
};

/**
 * @brief Class to parse key-value representation from a file and give results in the form of
 * protobuf messages.
 * @note This function assumes the format of the stat file is not changed during the subsequent
 * reads.
 * @warning This function only supports the case where the key field take precedence over the value
 * field, i.e., the first field is the key and the second field is the value
 * This class reads a file containing key-value pairs and parses them into protobuf messages
 * based on the provided descriptors and key lists.
 */
class KVRepr {
  public:
    /**
     * @brief Constructor for KVRepr for a file.
     * @param stat_file_path Path to the file containing key-value pairs.
     * @param message_descs Vector of protobuf message descriptors.
     * @param key_lists Vector of key lists corresponding to each message descriptor.
     * @param field_scanf_format Format string for scanf to parse each line in the file.
     * @param key_field_max_length Maximum length of the key field.
     * @note Rules for scanf format:
     *       1) Newline characters are not allowed in the format because line counting will be used
     *       to determine the position of each key-value pair in the file.
     *       2) The format must contain exactly two fields, one for the key and one for the value.
     *       3) The key and value should be strings specified using %s, scanset, or negated scanset.
     *       4) The key field must take precedence over the value field.
     */
    KVRepr(
        const fs::path &stat_file_path, const std::vector<const proto::Descriptor *> &message_descs,
        const std::vector<std::vector<std::string>> &key_lists,
        const std::string &field_scanf_format = "%64s %32s ",
        const unsigned key_field_max_length = 64, const unsigned val_field_max_length = 32);
    bool parseOnce(std::vector<proto::Message *> &messages) const;
    bool isValid() const;

    const fs::path &getStatFilePath() const;
    std::string generateStatusReport() const;

  private:
    const fs::path stat_file_path;
    const std::vector<const proto::Descriptor *> message_descs;
    const std::vector<std::vector<std::string>> key_lists;
    const std::string field_scanf_format;
    std::string field_fast_scanf_format;
    const unsigned key_field_max_length;
    const unsigned val_field_max_length;

    /**
     * @brief (line_number) -> <message_idx, field_idx>
     * @note The container is ordered by line number to allow ordered traversal when scanning the
     * file.
     */
    std::map<unsigned, std::pair<unsigned, unsigned>> kv_map;
    /**
     * @brief [<message_idx, field_idx>]
     * @note Only used on generating status report.
     */
    std::vector<std::pair<unsigned, unsigned>> missing_fields;
    bool valid = false;
};

#include "include/utils.ipp"
