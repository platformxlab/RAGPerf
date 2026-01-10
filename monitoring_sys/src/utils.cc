#include <date/tz.h>
#include <limits.h>
#include <unistd.h>
#include <charconv>
#include <regex>
#include <sstream>

#include "include/utils.hh"

static const date::time_zone *current_tz = date::current_zone();

unsigned getSystemNProc() { return sysconf(_SC_NPROCESSORS_ONLN); }

unsigned getSystemPageSize() { return sysconf(_SC_PAGESIZE); }

// Jiffies warp around in 2^32 / HZ / 86400 = 497 days with HZ = 100 (typical)

unsigned getSystemHz() { return sysconf(_SC_CLK_TCK); }

cr::nanoseconds nsSinceEpoch() {
    return cr::duration_cast<cr::nanoseconds>(cr::steady_clock::now().time_since_epoch());
}

fs::path validateDir(const std::string &dir) {
    std::error_code ec;
    fs::path p = fs::weakly_canonical(dir, ec);
    if (ec.value() == 0) return p;
    return fs::path();
}

std::string getCurrentTime(const cr::system_clock::time_point &p, const std::string &time_format) {
    date::zoned_time zoned_time = date::zoned_time(current_tz, p);
    return date::format(time_format, zoned_time);
}
std::string indent(const std::string &input, const std::string &prefix) {
    std::istringstream iss(input);
    std::ostringstream oss;
    std::string line;

    bool first = true;
    while (std::getline(iss, line)) {
        if (!first) oss << '\n';
        oss << prefix << line;
        first = false;
    }

    return oss.str();
}

const std::regex scanf_field_format(
    R"(%[0 #+-]?\d*\.?\d*([hl]{0,2}|[jztL])?([diuoxXeEfgGaAcpsSn%]|\[[^\[\]]+\]))");
const std::regex scanf_string_field_format(R"(%\d*(s|\[[^\[\]]+\]))");

/**
 * @brief Get the number of scanf string fields in a format string.
 * @see https://stackoverflow.com/questions/45215648/regex-capture-type-specifiers-in-format-string
 * @note The regex is adapted to match for scanf formats. The major change includes
 *       1) Ignoring the asterisk (*) in the format string as it means skipping the field in scanf.
 *       2) Add matching for scanset and negated scanset (e.g., %[abc] and %[^abc]) for strings.
 * @param format The format string to analyze.
 * @return The number of scanf string fields found in the string, excluding ignored fields.
 */
static unsigned getNFormatFields(const std::string &format) {
    std::regex re(R"(%[0 #+-]?\d*\.?\d*([hl]{0,2}|[jztL])?([diuoxXeEfgGaAcpsSn%]|\[[^\[\]]+\]))");
    auto begin = std::sregex_iterator(format.begin(), format.end(), re);
    auto end = std::sregex_iterator();
    return std::distance(begin, end);
}

/**
 * @brief Get the number of scanf string fields in a format string.
 * @see https://stackoverflow.com/questions/45215648/regex-capture-type-specifiers-in-format-string
 * @note The regex is adapted to match for scanf formats. The major change includes
 *       1) Only match format options for strings (i.e., %\d*s, scanset, and negated scanset).
 * @param format The format string to analyze.
 * @return The number of scanf string fields found in the string, excluding ignored fields.
 */
static unsigned getNStringFormatFields(const std::string &format) {
    std::regex re(R"(%\d*(s|\[[^\[\]]+\]))");
    auto begin = std::sregex_iterator(format.begin(), format.end(), re);
    auto end = std::sregex_iterator();
    return std::distance(begin, end);
}

/**
 * @brief Generate a fast scanf format string from a given scanf format by ignoring the key field.
 * @param field_scanf_format The original scanf format string.
 * @return A modified scanf format string that only matches the value.
 */
static std::string generateFastScanfFormat(const std::string &field_scanf_format) {
    std::string field_fast_scanf_format = field_scanf_format;
    const std::regex pattern(R"(%\d*(s|\[[^\[\]]+\]))");
    std::smatch match;

    if (!std::regex_search(field_fast_scanf_format, match, pattern) || match.size() < 1) {
        field_fast_scanf_format.clear();
    } else {
        std::string replacement = "%*" + std::string(match[1]);
        field_fast_scanf_format.replace(match.position(0), match.length(0), replacement);
    }

    return field_fast_scanf_format;
}

/**
 * @brief Get hint information for a message and its key list.
 * @note This function is expensive because it format strings in a pretty way.
 * @param msg The protobuf message.
 * @param key_list The list of keys associated with the message.
 * @return {full name of the message, a string representation of the key list}.
 */
static std::pair<std::string, std::string> getHintInfo(
    const proto::Descriptor *msg_desc, const std::vector<std::string> &key_list) {
    std::vector<std::string> field_names;
    for (int i = 0; i < msg_desc->field_count(); ++i) {
        const proto::FieldDescriptor *field_desc = msg_desc->field(i);
        field_names.push_back(field_desc->name().data());
    }
    const std::string message_hint =
        "(" + std::string(msg_desc->full_name()) + "): " +
        (field_names.size() ? strJoin(field_names.begin(), field_names.end(), ", ") : "<N/A>");
    const std::string key_hint =
        key_list.size() ? strJoin(key_list.begin(), key_list.end(), ", ") : "<N/A>";
    return {std::string(message_hint), key_hint};
}

KVRepr::KVRepr(
    const fs::path &stat_file_path, const std::vector<const proto::Descriptor *> &message_descs,
    const std::vector<std::vector<std::string>> &key_lists, const std::string &field_scanf_format,
    const unsigned key_field_max_length, const unsigned val_field_max_length)
    : stat_file_path(stat_file_path),
      message_descs(message_descs),
      key_lists(key_lists),
      field_scanf_format(field_scanf_format),
      key_field_max_length(key_field_max_length),
      val_field_max_length(val_field_max_length) {
    // exactly two string fields and no other type of fields are expected in the scanf format
    unsigned scanf_nfields = getNFormatFields(field_scanf_format);
    unsigned scanf_n_string_fields = getNStringFormatFields(field_scanf_format);
    if (scanf_nfields != scanf_n_string_fields || scanf_nfields != 2) {
        LOG(ERROR) << absl::StrFormat(
            "[KVRepr] Expect exactly two string fields in scanf format, get \"%s\" (%u fields, %u "
            "string fields)",
            field_scanf_format, scanf_nfields, scanf_n_string_fields);
        return;
    }

    // newline characters are not allowed in the scanf format
    if (field_scanf_format.find('\n') != std::string::npos) {
        LOG(ERROR) << absl::StrFormat(
            "[KVRepr] Newline characters are not allowed in scanf format \"%s\"",
            field_scanf_format);
        return;
    }

    if (message_descs.size() != key_lists.size()) {
        const auto [message_hint, key_hint] = getHintInfo(message_descs[0], key_lists[0]);
        LOG(ERROR) << absl::StrFormat(
            "[KVRepr] Number of messages (%zu) and key_lists (%zu) do not match. Initialized with\n"
            "  messages[0]:  %s\n"
            "  key_lists[0]: %s",
            message_descs.size(), key_lists.size(), message_hint, key_hint);
        return;
    }
    for (unsigned msg_idx = 0; msg_idx < message_descs.size(); ++msg_idx) {
        const proto::Descriptor *msg_desc = message_descs[msg_idx];
        const std::vector<std::string> &key_list = key_lists[msg_idx];

        size_t msg_nfields = msg_desc->field_count();
        size_t key_list_nfields = key_list.size();
        if (msg_nfields != key_list_nfields) {
            const auto [message_hint, key_hint] = getHintInfo(msg_desc, key_list);
            LOG(ERROR) << absl::StrFormat(
                "[KVRepr] Length of message (%zu) and key_list (%zu) do not match at message index "
                "%u. Initialized with\n"
                "  messages[%u]:  %s\n"
                "  key_lists[%u]: %s",
                msg_nfields, key_list_nfields, msg_idx, msg_idx, message_hint, msg_idx, key_hint);
            return;
        }
    }

    FILE *const fp = fopen(stat_file_path.c_str(), "r");
    if (!fp) {
        LOG(ERROR) << absl::StrFormat(
            "[KVRepr] Failed to open file %s: %s", stat_file_path.string(), strerror(errno));
        return;
    }

    std::unordered_map<std::string, unsigned> key_to_line_idx;
    int line_idx = 0;
    do {
        char key_buffer[key_field_max_length + 1];
        char val_buffer[val_field_max_length + 1];
        int nfields = fscanf(fp, field_scanf_format.c_str(), key_buffer, val_buffer);
        UNUSED(val_buffer);

        std::string key_string(key_buffer, strnlen(key_buffer, key_field_max_length));
        if (unlikely(nfields != 2)) {
            LOG(ERROR) << absl::StrFormat(
                "[KVRepr] Failed to parse line in file %s with format \"%s\". "
                "Expected 2 fields, got %d. Key: \"%s\"",
                stat_file_path.c_str(), field_scanf_format.c_str(), nfields, key_string.c_str());
        }

        key_to_line_idx[key_string] = line_idx;
        line_idx++;
    } while (!feof(fp));

    for (size_t msg_idx = 0; msg_idx < message_descs.size(); ++msg_idx) {
        const proto::Descriptor *msg_desc = message_descs[msg_idx];
        const std::vector<std::string> &key_list = key_lists[msg_idx];

        unsigned nfields = msg_desc->field_count();
        for (unsigned field_idx = 0; field_idx < nfields; ++field_idx) {
            const std::string &key = key_list[field_idx];
            auto it = key_to_line_idx.find(key);
            if (it == key_to_line_idx.end()) {
                // tolerate missing keys
                LOG(WARNING) << absl::StrFormat(
                    "[KVRepr] Key \"%s\" not found in file %s for message \"%s\" at index %zu", key,
                    stat_file_path.string(), msg_desc->full_name(), msg_idx);
                missing_fields.emplace_back(msg_idx, field_idx);
                continue;
            }
            unsigned line_idx = it->second;
            kv_map.emplace(line_idx, std::make_pair(msg_idx, field_idx));
        }
    }

    // generate fast scanf format by converting the first %s in the format to %*s
    field_fast_scanf_format = generateFastScanfFormat(field_scanf_format);
    if (field_fast_scanf_format.empty()) {
        LOG(ERROR) << absl::StrFormat(
            "[KVRepr] Failed to generate fast scanf format from \"%s\". Cannot proceed with "
            "parsing.",
            field_scanf_format);
        fclose(fp);
        return;
    }

    valid = true;
}

static bool setProtoFieldFromString(
    const char *value_str, proto::Message *const message, unsigned field_idx) {
    const proto::FieldDescriptor *field_desc = message->GetDescriptor()->field(field_idx);
    const proto::Reflection *reflection = message->GetReflection();

    std::from_chars_result result;
    const char *start = value_str;
    const char *end = value_str + strlen(value_str);
    switch (field_desc->cpp_type()) {
        case proto::FieldDescriptor::CPPTYPE_INT64: {
            int64_t value;
            result = std::from_chars(start, end, value);
            reflection->SetInt64(message, field_desc, value);
            break;
        }
        case proto::FieldDescriptor::CPPTYPE_INT32: {
            int32_t value;
            result = std::from_chars(start, end, value);
            reflection->SetInt32(message, field_desc, value);
            break;
        }
        case proto::FieldDescriptor::CPPTYPE_UINT64: {
            uint64_t value;
            result = std::from_chars(start, end, value);
            reflection->SetUInt64(message, field_desc, value);
            break;
        }
        case proto::FieldDescriptor::CPPTYPE_UINT32: {
            uint32_t value;
            result = std::from_chars(start, end, value);
            reflection->SetUInt32(message, field_desc, value);
            break;
        }
        case proto::FieldDescriptor::CPPTYPE_DOUBLE: {
            double value;
            result = std::from_chars(start, end, value);
            reflection->SetDouble(message, field_desc, value);
            break;
        }
        case proto::FieldDescriptor::CPPTYPE_FLOAT: {
            float value;
            result = std::from_chars(start, end, value);
            reflection->SetFloat(message, field_desc, value);
            break;
        }
        default: {
            LOG(ERROR) << absl::StrFormat(
                "Unsupported field type %s for message \"%s\" field #%u \"%s\". "
                "Only numeric fields are supported.",
                proto::FieldDescriptor::CppTypeName(field_desc->cpp_type()),
                message->GetDescriptor()->full_name(), field_idx, field_desc->name());
            return false;
        }
    }

    if (unlikely(result.ec != std::errc())) {
        LOG(ERROR) << absl::StrFormat(
            "Failed to parse value \"%s\" for message \"%s\" field #%u \"%s\". "
            "Error: %s",
            value_str, message->GetDescriptor()->full_name(), field_idx, field_desc->name(),
            std::make_error_code(result.ec).message());
        return false;
    }
    return true;
}

bool KVRepr::parseOnce(std::vector<proto::Message *> &parsed_messages) const {
    if (unlikely(!valid)) {
        LOG(ERROR) << "KVRepr is not valid. Cannot parse messages.";
        return false;
    }

    if (unlikely(parsed_messages.size() != message_descs.size())) {
        LOG(ERROR) << absl::StrFormat(
            "Number of parsed messages (%zu) does not match number of message descriptors (%zu). "
            "Cannot parse messages.",
            parsed_messages.size(), message_descs.size());
        return false;
    }

    FILE *const fp = fopen(stat_file_path.c_str(), "r");
    if (!fp) {
        LOG(ERROR) << absl::StrFormat(
            "Failed to open file %s: %s", stat_file_path.string(), strerror(errno));
        return false;
    }

    unsigned current_line = 0;
    for (auto &next_field : kv_map) {
        unsigned line_idx = next_field.first;
        unsigned msg_idx = next_field.second.first;
        unsigned field_idx = next_field.second.second;

        // skip lines until we reach the desired line index
        while (current_line < line_idx) {
            // NOTE: Ignoring the return value of a function labeled with [[nodiscard]]
            int result = fscanf(fp, "%*[^\n] ");
            if (unlikely(result == EOF)) {
                LOG(ERROR) << absl::StrFormat(
                    "Unexpected end of file while reading line %u for message \"%s\" field #%u",
                    current_line, parsed_messages[msg_idx]->GetDescriptor()->full_name(),
                    field_idx);
                fclose(fp);
                return false;
            }
            current_line++;
        }

        char val_buffer[val_field_max_length + 1];
        int nfields = fscanf(fp, field_fast_scanf_format.c_str(), val_buffer);
        // report error on EOF
        if (unlikely(nfields == EOF)) {
            LOG(ERROR) << absl::StrFormat(
                "Failed to read line %u for message \"%s\" field #%u", current_line,
                parsed_messages[msg_idx]->GetDescriptor()->full_name(), field_idx);
            fclose(fp);
            return false;
        }

        bool ret = setProtoFieldFromString(val_buffer, parsed_messages[msg_idx], field_idx);
        if (unlikely(!ret)) {
            LOG(ERROR) << absl::StrFormat(
                "Failed to parse line %u for message \"%s\" field #%u", current_line,
                parsed_messages[msg_idx]->GetDescriptor()->full_name(), field_idx);
            fclose(fp);
            return false;
        }
        current_line++;
    }

    fclose(fp);
    return true;
}

bool KVRepr::isValid() const { return valid; }

const fs::path &KVRepr::getStatFilePath() const { return stat_file_path; }

std::string KVRepr::generateStatusReport() const {
    std::string ret;
    if (!isValid()) {
        absl::StrAppendFormat(&ret, "Invalid KVRepr instance.");
    } else {
        absl::StrAppendFormat(
            &ret,
            "KVRepr on input file %s"
            "\n  Generic:"
            "\n  - Generated fast scanf format: \"%s\" (adapted from original format \"%s\")"
            "\n  - Number of messages: %zu"
            "\n  Fields (%zu found, %zu missing):",
            stat_file_path.string(), field_fast_scanf_format.c_str(), field_scanf_format.c_str(),
            message_descs.size(), kv_map.size(), missing_fields.size());
        for (const auto &kv : kv_map) {
            unsigned line_idx = kv.first;
            unsigned msg_idx = kv.second.first;
            unsigned field_idx = kv.second.second;
            const std::string_view message_name = message_descs[msg_idx]->full_name();
            const std::string_view proto_field_name =
                message_descs[msg_idx]->field(field_idx)->name();
            const std::string &key = key_lists[msg_idx][field_idx];
            absl::StrAppendFormat(
                &ret, "\n  - Message <%s:%d> Field \"%s\" (Key \"%s\") found at line %u",
                message_name.data(), field_idx, proto_field_name.data(), key.c_str(), line_idx);
        }
        for (const auto &missing_field : missing_fields) {
            unsigned msg_idx = missing_field.first;
            unsigned field_idx = missing_field.second;
            const std::string_view message_name = message_descs[msg_idx]->full_name();
            const std::string_view proto_field_name =
                message_descs[msg_idx]->field(field_idx)->name();
            const std::string &key = key_lists[msg_idx][field_idx];
            absl::StrAppendFormat(
                &ret, "\n  - Message <%s:%d> Field \"%s\" (Key \"%s\") is missing",
                message_name.data(), field_idx, proto_field_name.data(), key.c_str());
        }
    }
    return ret;
}
