// pool_client.h - Stratum Mining Protocol Client
// RED TEAM RESEARCH USE ONLY - Detection methodology development
//
// Purpose: Implements Stratum v1 mining protocol with TLS support
// Research Context: Analysis of pool communication patterns for blue team detection

#pragma once

#include <string>
#include <vector>
#include <memory>
#include <functional>
#include <atomic>
#include <mutex>
#include <condition_variable>
#include <nlohmann/json.hpp>

namespace redteam {

using json = nlohmann::json;

// ============================================================================
// Stratum Message Types (for detection research)
// ============================================================================
enum class StratumMethod {
    MINING_SUBSCRIBE,
    MINING_AUTHORIZE,
    MINING_SET_DIFFICULTY,
    MINING_NOTIFY,
    MINING_SUBMIT,
    CLIENT_RECONNECT,
    CLIENT_GET_VERSION,
    UNKNOWN
};

// ============================================================================
// Stratum Message Structure
// ============================================================================
struct StratumMessage {
    uint64_t id;
    StratumMethod method;
    json params;
    json result;
    json error;
    bool is_response;

    std::string to_json() const;
    static StratumMessage from_json(const std::string& raw);
};

// ============================================================================
// Mining Job Data
// ============================================================================
struct MiningJob {
    std::string job_id;
    std::string prev_hash;
    std::string coinb1;
    std::string coinb2;
    std::vector<std::string> merkle_branches;
    std::string version;
    std::string nbits;
    std::string ntime;
    bool clean_jobs;
    uint64_t height;
};

// ============================================================================
// Share Submission Data
// ============================================================================
struct ShareSubmission {
    std::string worker_name;
    std::string job_id;
    std::string extranonce2;
    std::string ntime;
    std::string nonce;

    json to_params() const;
};

// ============================================================================
// Stratum Client Configuration
// ============================================================================
struct StratumConfig {
    std::string pool_url;
    uint16_t pool_port;
    bool use_tls;
    std::string worker_name;
    std::string password;

    // Connection management
    uint32_t connect_timeout_ms = 10000;
    uint32_t read_timeout_ms = 30000;
    uint32_t reconnect_delay_ms = 5000;
    uint32_t max_reconnect_attempts = 10;

    // Protocol settings
    std::string user_agent = "RedTeam-Miner/2.0";
    bool enable_keepalive = true;
    uint32_t keepalive_interval_s = 60;

    // Research-specific: Traffic obfuscation
    bool randomize_message_timing = true;
    uint32_t jitter_ms_min = 50;
    uint32_t jitter_ms_max = 200;
};

// ============================================================================
// Stratum Client Callbacks
// ============================================================================
struct StratumCallbacks {
    std::function<void(const MiningJob&)> on_new_job;
    std::function<void(double)> on_difficulty_changed;
    std::function<void(bool, const std::string&)> on_share_result;
    std::function<void(const std::string&)> on_connection_error;
    std::function<void()> on_reconnect;
};

// ============================================================================
// Stratum Client Implementation
// ============================================================================
class StratumClient {
public:
    StratumClient(const StratumConfig& config, const StratumCallbacks& callbacks);
    ~StratumClient();

    // Connection management
    bool connect();
    void disconnect();
    bool is_connected() const;

    // Protocol operations
    bool subscribe();
    bool authorize();
    bool submit_share(const ShareSubmission& share);

    // Job management
    MiningJob get_current_job() const;
    double get_current_difficulty() const;

    // Statistics
    struct Stats {
        uint64_t shares_submitted;
        uint64_t shares_accepted;
        uint64_t shares_rejected;
        uint64_t stale_shares;
        uint64_t reconnect_count;
        uint64_t bytes_sent;
        uint64_t bytes_received;
        double current_hashrate;
    };
    Stats get_stats() const;

    // Thread control
    void start_receive_loop();
    void stop_receive_loop();

private:
    // Configuration
    StratumConfig config_;
    StratumCallbacks callbacks_;

    // Connection state
    std::unique_ptr<class TLSWrapper> tls_wrapper_;
    int socket_fd_;
    std::atomic<bool> connected_;
    std::atomic<bool> running_;

    // Protocol state
    uint64_t message_id_counter_;
    std::string session_id_;
    std::string extranonce1_;
    uint32_t extranonce2_size_;

    // Mining state
    MiningJob current_job_;
    std::atomic<double> current_difficulty_;
    mutable std::mutex job_mutex_;

    // Statistics
    Stats stats_;
    mutable std::mutex stats_mutex_;

    // Receive loop
    std::unique_ptr<std::thread> receive_thread_;
    std::condition_variable receive_cv_;

    // Internal methods
    bool connect_socket();
    void close_socket();
    bool send_message(const StratumMessage& msg);
    std::string receive_line();
    void process_message(const StratumMessage& msg);

    // Message handlers
    void handle_mining_notify(const json& params);
    void handle_set_difficulty(const json& params);
    void handle_client_reconnect(const json& params);

    // Utility
    void add_timing_jitter();
    uint64_t next_message_id();
};

// ============================================================================
// TLS Wrapper (OpenSSL abstraction)
// ============================================================================
class TLSWrapper {
public:
    TLSWrapper();
    ~TLSWrapper();

    bool connect(const std::string& hostname, uint16_t port, int socket_fd);
    void disconnect();

    ssize_t send(const void* data, size_t length);
    ssize_t receive(void* buffer, size_t length);

    bool is_connected() const;
    std::string get_cipher_name() const;
    std::string get_protocol_version() const;

private:
    struct Impl;
    std::unique_ptr<Impl> pimpl_;
};

} // namespace redteam
