// utils.h - Utility Functions for Red Team GPU Miner
// RED TEAM RESEARCH - Utilities for configuration, logging, and signal handling

#pragma once

#include <string>
#include <memory>
#include <functional>
#include <nlohmann/json.hpp>

namespace redteam {
namespace utils {

using json = nlohmann::json;

// ============================================================================
// Configuration Loader
// ============================================================================
class ConfigLoader {
public:
    explicit ConfigLoader(const std::string& config_path);
    ~ConfigLoader();

    // Load configuration from JSON file
    bool load();

    // Get configuration sections
    json get_mining_config() const;
    json get_pool_config() const;
    json get_evasion_config() const;
    json get_gpu_config() const;

    // Get specific values with defaults
    template<typename T>
    T get(const std::string& key, const T& default_value) const;

    // Validation
    bool validate() const;
    std::string get_validation_errors() const;

private:
    std::string config_path_;
    json config_data_;
    mutable std::string validation_errors_;

    bool validate_pool_config() const;
    bool validate_mining_config() const;
    bool validate_evasion_config() const;
};

// ============================================================================
// Logger (Thread-safe, multi-level logging)
// ============================================================================
enum class LogLevel {
    DEBUG,
    INFO,
    WARNING,
    ERROR,
    CRITICAL
};

class Logger {
public:
    static Logger& instance();

    // Configuration
    void set_level(LogLevel level);
    void set_log_file(const std::string& filepath);
    void enable_console(bool enable);
    void enable_timestamps(bool enable);
    void enable_thread_id(bool enable);

    // Logging methods
    void debug(const std::string& message);
    void info(const std::string& message);
    void warning(const std::string& message);
    void error(const std::string& message);
    void critical(const std::string& message);

    // Formatted logging
    template<typename... Args>
    void debug_fmt(const char* format, Args... args);

    template<typename... Args>
    void info_fmt(const char* format, Args... args);

    template<typename... Args>
    void warning_fmt(const char* format, Args... args);

    template<typename... Args>
    void error_fmt(const char* format, Args... args);

    // Flush logs
    void flush();

    // Statistics
    struct Stats {
        uint64_t debug_count;
        uint64_t info_count;
        uint64_t warning_count;
        uint64_t error_count;
        uint64_t critical_count;
    };
    Stats get_stats() const;

private:
    Logger();
    ~Logger();
    Logger(const Logger&) = delete;
    Logger& operator=(const Logger&) = delete;

    struct Impl;
    std::unique_ptr<Impl> pimpl_;

    void log(LogLevel level, const std::string& message);
    std::string format_log_entry(LogLevel level, const std::string& message) const;
    const char* level_to_string(LogLevel level) const;
};

// ============================================================================
// Signal Handler (Graceful shutdown)
// ============================================================================
class SignalHandler {
public:
    using ShutdownCallback = std::function<void(int signal)>;

    static SignalHandler& instance();

    // Register shutdown callback
    void register_callback(const ShutdownCallback& callback);

    // Install signal handlers
    void install_handlers();

    // Check if shutdown requested
    bool shutdown_requested() const;

    // Wait for signal
    void wait_for_shutdown();

private:
    SignalHandler();
    ~SignalHandler();
    SignalHandler(const SignalHandler&) = delete;
    SignalHandler& operator=(const SignalHandler&) = delete;

    struct Impl;
    std::unique_ptr<Impl> pimpl_;

    static void signal_handler(int signal);
};

// ============================================================================
// File Utilities
// ============================================================================
namespace file {
    bool exists(const std::string& path);
    bool is_readable(const std::string& path);
    bool is_writable(const std::string& path);
    std::string read_file(const std::string& path);
    bool write_file(const std::string& path, const std::string& content);
    std::string get_absolute_path(const std::string& path);
} // namespace file

// ============================================================================
// String Utilities
// ============================================================================
namespace string {
    std::string trim(const std::string& str);
    std::vector<std::string> split(const std::string& str, char delimiter);
    std::string to_lower(const std::string& str);
    std::string to_upper(const std::string& str);
    bool starts_with(const std::string& str, const std::string& prefix);
    bool ends_with(const std::string& str, const std::string& suffix);
    std::string format(const char* fmt, ...);
} // namespace string

// ============================================================================
// Time Utilities
// ============================================================================
namespace time {
    uint64_t timestamp_ms();
    uint64_t timestamp_us();
    std::string current_datetime_string();
    void sleep_ms(uint32_t milliseconds);
    void sleep_us(uint32_t microseconds);
} // namespace time

// ============================================================================
// System Utilities
// ============================================================================
namespace system {
    std::string get_hostname();
    uint32_t get_cpu_count();
    uint64_t get_total_memory_mb();
    uint64_t get_available_memory_mb();
    std::string get_os_version();
    bool is_running_in_container();
    bool has_root_privileges();
} // namespace system

} // namespace utils
} // namespace redteam
