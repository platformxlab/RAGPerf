#include <string>

#include <absl/log/check.h>

// global helpper constexpr
template <typename T>
constexpr unsigned log2Floor(T x) {
    return (x < 2) ? 0 : 1 + log2Floor(x >> 1);
}

template <typename T>
constexpr unsigned log10Floor(T x) {
    return (x < 10) ? 0 : 1 + log10Floor(x / 10);
}

template <typename T>
constexpr unsigned log2Ceil(T x) {
    return (x < 2) ? 0 : log2Floor(x - 1) + 1;
}

template <typename T>
constexpr unsigned log10Ceil(T x) {
    return (x < 10) ? 0 : log10Floor(x - 1) + 1;
}

template <typename T>
std::string strPad(T value, unsigned width, char fill) {
    std::string str = std::to_string(value);
    std::ostringstream oss;
    oss << std::setw(width) << std::setfill(fill) << str;
    return oss.str();
}

template <std::forward_iterator Iterator>
std::string strJoin(const Iterator &begin, const Iterator &end, const std::string &sep) {
    std::string result;
    for (auto it = begin; it != end; ++it) {
        if (!result.empty()) {
            result += sep;
        }
        result += *it;
    }
    return result;
}

template <absl::LogSeverity severity, typename... Args>
void verbosePrint(bool verbose, const char *format, Args... args) {
    if (verbose) {
        fprintf(stderr, format, args...);
        fputc('\n', stderr);
    } else {
        LOG(LEVEL(severity)) << absl::StrFormat(format, args...);
    }
}
