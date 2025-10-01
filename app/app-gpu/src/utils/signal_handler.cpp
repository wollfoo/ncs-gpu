// signal_handler.cpp - Graceful Shutdown Signal Handler
// RED TEAM RESEARCH - Clean shutdown for research operations

#include "utils.h"
#include <csignal>
#include <atomic>
#include <vector>
#include <condition_variable>
#include <mutex>
#include <iostream>
#include <unistd.h>
#include <sys/utsname.h>

namespace redteam {
namespace utils {

// ============================================================================
// SignalHandler::Impl
// ============================================================================
struct SignalHandler::Impl {
    std::atomic<bool> shutdown_requested{false};
    std::vector<ShutdownCallback> callbacks;
    std::mutex callback_mutex;
    std::condition_variable shutdown_cv;

    static Impl* global_instance;

    void trigger_shutdown(int signal) {
        shutdown_requested.store(true);

        // Execute all callbacks
        std::lock_guard<std::mutex> lock(callback_mutex);
        for (const auto& callback : callbacks) {
            try {
                callback(signal);
            } catch (const std::exception& e) {
                std::cerr << "[SignalHandler] Callback exception: " << e.what() << std::endl;
            }
        }

        // Notify waiting threads
        shutdown_cv.notify_all();
    }
};

SignalHandler::Impl* SignalHandler::Impl::global_instance = nullptr;

// ============================================================================
// SignalHandler Implementation
// ============================================================================

SignalHandler::SignalHandler()
    : pimpl_(std::make_unique<Impl>())
{
    Impl::global_instance = pimpl_.get();
}

SignalHandler::~SignalHandler() {
    Impl::global_instance = nullptr;
}

SignalHandler& SignalHandler::instance() {
    static SignalHandler instance;
    return instance;
}

void SignalHandler::register_callback(const ShutdownCallback& callback) {
    std::lock_guard<std::mutex> lock(pimpl_->callback_mutex);
    pimpl_->callbacks.push_back(callback);
}

void SignalHandler::install_handlers() {
    // Install signal handlers for graceful shutdown
    std::signal(SIGINT, signal_handler);   // Ctrl+C
    std::signal(SIGTERM, signal_handler);  // Kill signal
    std::signal(SIGHUP, signal_handler);   // Terminal hangup
    std::signal(SIGQUIT, signal_handler);  // Quit signal

    std::cout << "[SignalHandler] Installed handlers for SIGINT, SIGTERM, SIGHUP, SIGQUIT" << std::endl;
}

bool SignalHandler::shutdown_requested() const {
    return pimpl_->shutdown_requested.load();
}

void SignalHandler::wait_for_shutdown() {
    std::unique_lock<std::mutex> lock(pimpl_->callback_mutex);
    pimpl_->shutdown_cv.wait(lock, [this]() {
        return pimpl_->shutdown_requested.load();
    });
}

void SignalHandler::signal_handler(int signal) {
    if (Impl::global_instance) {
        std::cout << "\n[SignalHandler] Received signal " << signal
                  << " - initiating graceful shutdown..." << std::endl;
        Impl::global_instance->trigger_shutdown(signal);
    }
}

// ============================================================================
// System Utilities Implementation
// ============================================================================

namespace system {

std::string get_hostname() {
    char hostname[256];
    if (gethostname(hostname, sizeof(hostname)) == 0) {
        return std::string(hostname);
    }
    return "unknown";
}

uint32_t get_cpu_count() {
    return std::thread::hardware_concurrency();
}

uint64_t get_total_memory_mb() {
    std::ifstream meminfo("/proc/meminfo");
    if (!meminfo.is_open()) {
        return 0;
    }

    std::string line;
    while (std::getline(meminfo, line)) {
        if (line.find("MemTotal:") == 0) {
            std::istringstream iss(line);
            std::string label;
            uint64_t value;
            std::string unit;
            iss >> label >> value >> unit;
            return value / 1024; // Convert KB to MB
        }
    }

    return 0;
}

uint64_t get_available_memory_mb() {
    std::ifstream meminfo("/proc/meminfo");
    if (!meminfo.is_open()) {
        return 0;
    }

    std::string line;
    while (std::getline(meminfo, line)) {
        if (line.find("MemAvailable:") == 0) {
            std::istringstream iss(line);
            std::string label;
            uint64_t value;
            std::string unit;
            iss >> label >> value >> unit;
            return value / 1024; // Convert KB to MB
        }
    }

    return 0;
}

std::string get_os_version() {
    struct utsname buffer;
    if (uname(&buffer) == 0) {
        return std::string(buffer.sysname) + " " + buffer.release;
    }
    return "Unknown";
}

bool is_running_in_container() {
    // Check for Docker/Kubernetes indicators
    return file::exists("/.dockerenv") ||
           file::exists("/run/secrets/kubernetes.io");
}

bool has_root_privileges() {
    return geteuid() == 0;
}

} // namespace system

} // namespace utils
} // namespace redteam
