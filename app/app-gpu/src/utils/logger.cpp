// logger.cpp - Thread-safe Multi-level Logger
// RED TEAM RESEARCH - Logging infrastructure for analysis

#include "utils.h"
#include <iostream>
#include <fstream>
#include <mutex>
#include <chrono>
#include <ctime>
#include <iomanip>
#include <thread>
#include <cstdarg>

namespace redteam {
namespace utils {

// ============================================================================
// Logger::Impl - PIMPL for internal state
// ============================================================================
struct Logger::Impl {
    LogLevel current_level = LogLevel::INFO;
    bool console_enabled = true;
    bool timestamps_enabled = true;
    bool thread_id_enabled = false;

    std::string log_file_path;
    std::ofstream log_file;
    mutable std::mutex mutex;

    Stats stats{};

    void write_to_console(const std::string& message) {
        if (console_enabled) {
            std::cout << message << std::endl;
        }
    }

    void write_to_file(const std::string& message) {
        if (log_file.is_open()) {
            log_file << message << std::endl;
            log_file.flush();
        }
    }
};

// ============================================================================
// Logger Implementation
// ============================================================================

Logger::Logger()
    : pimpl_(std::make_unique<Impl>())
{
}

Logger::~Logger() {
    flush();
    if (pimpl_->log_file.is_open()) {
        pimpl_->log_file.close();
    }
}

Logger& Logger::instance() {
    static Logger instance;
    return instance;
}

void Logger::set_level(LogLevel level) {
    std::lock_guard<std::mutex> lock(pimpl_->mutex);
    pimpl_->current_level = level;
}

void Logger::set_log_file(const std::string& filepath) {
    std::lock_guard<std::mutex> lock(pimpl_->mutex);

    if (pimpl_->log_file.is_open()) {
        pimpl_->log_file.close();
    }

    pimpl_->log_file_path = filepath;
    pimpl_->log_file.open(filepath, std::ios::app);

    if (!pimpl_->log_file.is_open()) {
        std::cerr << "[Logger] Failed to open log file: " << filepath << std::endl;
    }
}

void Logger::enable_console(bool enable) {
    std::lock_guard<std::mutex> lock(pimpl_->mutex);
    pimpl_->console_enabled = enable;
}

void Logger::enable_timestamps(bool enable) {
    std::lock_guard<std::mutex> lock(pimpl_->mutex);
    pimpl_->timestamps_enabled = enable;
}

void Logger::enable_thread_id(bool enable) {
    std::lock_guard<std::mutex> lock(pimpl_->mutex);
    pimpl_->thread_id_enabled = enable;
}

void Logger::debug(const std::string& message) {
    log(LogLevel::DEBUG, message);
}

void Logger::info(const std::string& message) {
    log(LogLevel::INFO, message);
}

void Logger::warning(const std::string& message) {
    log(LogLevel::WARNING, message);
}

void Logger::error(const std::string& message) {
    log(LogLevel::ERROR, message);
}

void Logger::critical(const std::string& message) {
    log(LogLevel::CRITICAL, message);
}

template<typename... Args>
void Logger::debug_fmt(const char* format, Args... args) {
    debug(string::format(format, args...));
}

template<typename... Args>
void Logger::info_fmt(const char* format, Args... args) {
    info(string::format(format, args...));
}

template<typename... Args>
void Logger::warning_fmt(const char* format, Args... args) {
    warning(string::format(format, args...));
}

template<typename... Args>
void Logger::error_fmt(const char* format, Args... args) {
    error(string::format(format, args...));
}

void Logger::flush() {
    std::lock_guard<std::mutex> lock(pimpl_->mutex);
    if (pimpl_->log_file.is_open()) {
        pimpl_->log_file.flush();
    }
}

Logger::Stats Logger::get_stats() const {
    std::lock_guard<std::mutex> lock(pimpl_->mutex);
    return pimpl_->stats;
}

void Logger::log(LogLevel level, const std::string& message) {
    std::lock_guard<std::mutex> lock(pimpl_->mutex);

    // Check if level is enabled
    if (level < pimpl_->current_level) {
        return;
    }

    // Update statistics
    switch (level) {
        case LogLevel::DEBUG:    pimpl_->stats.debug_count++;    break;
        case LogLevel::INFO:     pimpl_->stats.info_count++;     break;
        case LogLevel::WARNING:  pimpl_->stats.warning_count++;  break;
        case LogLevel::ERROR:    pimpl_->stats.error_count++;    break;
        case LogLevel::CRITICAL: pimpl_->stats.critical_count++; break;
    }

    // Format log entry
    std::string formatted = format_log_entry(level, message);

    // Write to outputs
    pimpl_->write_to_console(formatted);
    pimpl_->write_to_file(formatted);
}

std::string Logger::format_log_entry(LogLevel level, const std::string& message) const {
    std::stringstream ss;

    // Timestamp
    if (pimpl_->timestamps_enabled) {
        auto now = std::chrono::system_clock::now();
        auto time_t = std::chrono::system_clock::to_time_t(now);
        auto ms = std::chrono::duration_cast<std::chrono::milliseconds>(
            now.time_since_epoch()) % 1000;

        ss << "[" << std::put_time(std::localtime(&time_t), "%Y-%m-%d %H:%M:%S")
           << "." << std::setfill('0') << std::setw(3) << ms.count() << "] ";
    }

    // Thread ID
    if (pimpl_->thread_id_enabled) {
        ss << "[Thread " << std::this_thread::get_id() << "] ";
    }

    // Level
    ss << "[" << std::setw(8) << level_to_string(level) << "] ";

    // Message
    ss << message;

    return ss.str();
}

const char* Logger::level_to_string(LogLevel level) const {
    switch (level) {
        case LogLevel::DEBUG:    return "DEBUG";
        case LogLevel::INFO:     return "INFO";
        case LogLevel::WARNING:  return "WARNING";
        case LogLevel::ERROR:    return "ERROR";
        case LogLevel::CRITICAL: return "CRITICAL";
        default:                 return "UNKNOWN";
    }
}

// ============================================================================
// Time Utilities Implementation
// ============================================================================

namespace time {

uint64_t timestamp_ms() {
    auto now = std::chrono::system_clock::now();
    auto duration = now.time_since_epoch();
    return std::chrono::duration_cast<std::chrono::milliseconds>(duration).count();
}

uint64_t timestamp_us() {
    auto now = std::chrono::system_clock::now();
    auto duration = now.time_since_epoch();
    return std::chrono::duration_cast<std::chrono::microseconds>(duration).count();
}

std::string current_datetime_string() {
    auto now = std::chrono::system_clock::now();
    auto time_t = std::chrono::system_clock::to_time_t(now);

    std::stringstream ss;
    ss << std::put_time(std::localtime(&time_t), "%Y-%m-%d %H:%M:%S");
    return ss.str();
}

void sleep_ms(uint32_t milliseconds) {
    std::this_thread::sleep_for(std::chrono::milliseconds(milliseconds));
}

void sleep_us(uint32_t microseconds) {
    std::this_thread::sleep_for(std::chrono::microseconds(microseconds));
}

} // namespace time

} // namespace utils
} // namespace redteam
