#pragma once

#include "include/utils.hh"

namespace MSys {

bool loggerInitialize(const std::string &log_dir);
const fs::path &getLoggerFolder();
const fs::path &getLoggerFile();
void loggerDeinitialize();

}  // namespace MSys
