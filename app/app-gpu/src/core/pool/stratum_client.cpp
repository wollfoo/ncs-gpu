// stratum_client.cpp - Stratum Mining Protocol Implementation
// RED TEAM RESEARCH - Pool communication analysis for detection research

#include "pool_client.h"
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <netdb.h>
#include <unistd.h>
#include <fcntl.h>
#include <cstring>
#include <chrono>
#include <random>
#include <sstream>
#include <iostream>

namespace redteam {

// ============================================================================
// StratumMessage Implementation
// ============================================================================

std::string StratumMessage::to_json() const {
    json j;
    j["id"] = id;
    j["jsonrpc"] = "2.0";

    if (!is_response) {
        // Request format
        switch (method) {
            case StratumMethod::MINING_SUBSCRIBE:
                j["method"] = "mining.subscribe";
                break;
            case StratumMethod::MINING_AUTHORIZE:
                j["method"] = "mining.authorize";
                break;
            case StratumMethod::MINING_SUBMIT:
                j["method"] = "mining.submit";
                break;
            case StratumMethod::CLIENT_GET_VERSION:
                j["method"] = "client.get_version";
                break;
            default:
                j["method"] = "unknown";
        }
        j["params"] = params;
    } else {
        // Response format
        if (!error.is_null()) {
            j["error"] = error;
        }
        j["result"] = result;
    }

    return j.dump() + "\n";
}

StratumMessage StratumMessage::from_json(const std::string& raw) {
    StratumMessage msg;
    auto j = json::parse(raw);

    msg.id = j.value("id", 0);
    msg.is_response = !j.contains("method");

    if (msg.is_response) {
        msg.result = j.value("result", json());
        msg.error = j.value("error", json());
    } else {
        std::string method_str = j.value("method", "");
        if (method_str == "mining.notify") {
            msg.method = StratumMethod::MINING_NOTIFY;
        } else if (method_str == "mining.set_difficulty") {
            msg.method = StratumMethod::MINING_SET_DIFFICULTY;
        } else if (method_str == "client.reconnect") {
            msg.method = StratumMethod::CLIENT_RECONNECT;
        } else {
            msg.method = StratumMethod::UNKNOWN;
        }
        msg.params = j.value("params", json::array());
    }

    return msg;
}

// ============================================================================
// ShareSubmission Implementation
// ============================================================================

json ShareSubmission::to_params() const {
    return json::array({
        worker_name,
        job_id,
        extranonce2,
        ntime,
        nonce
    });
}

// ============================================================================
// StratumClient Implementation
// ============================================================================

StratumClient::StratumClient(const StratumConfig& config, const StratumCallbacks& callbacks)
    : config_(config)
    , callbacks_(callbacks)
    , socket_fd_(-1)
    , connected_(false)
    , running_(false)
    , message_id_counter_(1)
    , extranonce2_size_(0)
    , current_difficulty_(1.0)
{
    if (config_.use_tls) {
        tls_wrapper_ = std::make_unique<TLSWrapper>();
    }

    // Initialize stats
    std::memset(&stats_, 0, sizeof(stats_));
}

StratumClient::~StratumClient() {
    stop_receive_loop();
    disconnect();
}

bool StratumClient::connect() {
    if (connected_.load()) {
        return true;
    }

    // Connect socket
    if (!connect_socket()) {
        return false;
    }

    // Perform TLS handshake if needed
    if (config_.use_tls && tls_wrapper_) {
        if (!tls_wrapper_->connect(config_.pool_url, config_.pool_port, socket_fd_)) {
            close_socket();
            return false;
        }
        std::cout << "[Stratum] TLS connection established: "
                  << tls_wrapper_->get_protocol_version()
                  << " with " << tls_wrapper_->get_cipher_name() << std::endl;
    }

    connected_.store(true);
    return true;
}

void StratumClient::disconnect() {
    if (!connected_.load()) {
        return;
    }

    connected_.store(false);

    if (tls_wrapper_) {
        tls_wrapper_->disconnect();
    }

    close_socket();
}

bool StratumClient::is_connected() const {
    return connected_.load();
}

bool StratumClient::subscribe() {
    StratumMessage msg;
    msg.id = next_message_id();
    msg.method = StratumMethod::MINING_SUBSCRIBE;
    msg.is_response = false;
    msg.params = json::array({config_.user_agent});

    return send_message(msg);
}

bool StratumClient::authorize() {
    StratumMessage msg;
    msg.id = next_message_id();
    msg.method = StratumMethod::MINING_AUTHORIZE;
    msg.is_response = false;
    msg.params = json::array({config_.worker_name, config_.password});

    return send_message(msg);
}

bool StratumClient::submit_share(const ShareSubmission& share) {
    StratumMessage msg;
    msg.id = next_message_id();
    msg.method = StratumMethod::MINING_SUBMIT;
    msg.is_response = false;
    msg.params = share.to_params();

    if (send_message(msg)) {
        std::lock_guard<std::mutex> lock(stats_mutex_);
        stats_.shares_submitted++;
        return true;
    }
    return false;
}

MiningJob StratumClient::get_current_job() const {
    std::lock_guard<std::mutex> lock(job_mutex_);
    return current_job_;
}

double StratumClient::get_current_difficulty() const {
    return current_difficulty_.load();
}

StratumClient::Stats StratumClient::get_stats() const {
    std::lock_guard<std::mutex> lock(stats_mutex_);
    return stats_;
}

void StratumClient::start_receive_loop() {
    if (running_.load()) {
        return;
    }

    running_.store(true);
    receive_thread_ = std::make_unique<std::thread>([this]() {
        while (running_.load()) {
            if (!connected_.load()) {
                std::this_thread::sleep_for(std::chrono::milliseconds(100));
                continue;
            }

            try {
                std::string line = receive_line();
                if (line.empty()) {
                    continue;
                }

                auto msg = StratumMessage::from_json(line);
                process_message(msg);

            } catch (const std::exception& e) {
                std::cerr << "[Stratum] Receive error: " << e.what() << std::endl;
                if (callbacks_.on_connection_error) {
                    callbacks_.on_connection_error(e.what());
                }
            }
        }
    });
}

void StratumClient::stop_receive_loop() {
    if (!running_.load()) {
        return;
    }

    running_.store(false);
    if (receive_thread_ && receive_thread_->joinable()) {
        receive_thread_->join();
    }
}

// ============================================================================
// Private Methods
// ============================================================================

bool StratumClient::connect_socket() {
    // Resolve hostname
    struct addrinfo hints, *result;
    std::memset(&hints, 0, sizeof(hints));
    hints.ai_family = AF_UNSPEC;
    hints.ai_socktype = SOCK_STREAM;

    std::string port_str = std::to_string(config_.pool_port);
    int ret = getaddrinfo(config_.pool_url.c_str(), port_str.c_str(), &hints, &result);
    if (ret != 0) {
        std::cerr << "[Stratum] DNS resolution failed: " << gai_strerror(ret) << std::endl;
        return false;
    }

    // Try to connect
    for (auto rp = result; rp != nullptr; rp = rp->ai_next) {
        socket_fd_ = socket(rp->ai_family, rp->ai_socktype, rp->ai_protocol);
        if (socket_fd_ == -1) {
            continue;
        }

        // Set socket timeout
        struct timeval tv;
        tv.tv_sec = config_.connect_timeout_ms / 1000;
        tv.tv_usec = (config_.connect_timeout_ms % 1000) * 1000;
        setsockopt(socket_fd_, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv));
        setsockopt(socket_fd_, SOL_SOCKET, SO_SNDTIMEO, &tv, sizeof(tv));

        if (::connect(socket_fd_, rp->ai_addr, rp->ai_addrlen) == 0) {
            break; // Success
        }

        ::close(socket_fd_);
        socket_fd_ = -1;
    }

    freeaddrinfo(result);

    if (socket_fd_ == -1) {
        std::cerr << "[Stratum] Connection failed" << std::endl;
        return false;
    }

    return true;
}

void StratumClient::close_socket() {
    if (socket_fd_ != -1) {
        ::close(socket_fd_);
        socket_fd_ = -1;
    }
}

bool StratumClient::send_message(const StratumMessage& msg) {
    if (!connected_.load()) {
        return false;
    }

    std::string data = msg.to_json();

    // Add timing jitter for research (anti-fingerprinting)
    if (config_.randomize_message_timing) {
        add_timing_jitter();
    }

    ssize_t sent;
    if (tls_wrapper_) {
        sent = tls_wrapper_->send(data.data(), data.size());
    } else {
        sent = ::send(socket_fd_, data.data(), data.size(), 0);
    }

    if (sent > 0) {
        std::lock_guard<std::mutex> lock(stats_mutex_);
        stats_.bytes_sent += sent;
        return true;
    }

    return false;
}

std::string StratumClient::receive_line() {
    std::string line;
    char buffer[4096];

    while (connected_.load()) {
        ssize_t received;
        if (tls_wrapper_) {
            received = tls_wrapper_->receive(buffer, 1);
        } else {
            received = ::recv(socket_fd_, buffer, 1, 0);
        }

        if (received <= 0) {
            return "";
        }

        {
            std::lock_guard<std::mutex> lock(stats_mutex_);
            stats_.bytes_received += received;
        }

        char c = buffer[0];
        if (c == '\n') {
            break;
        }
        if (c != '\r') {
            line += c;
        }
    }

    return line;
}

void StratumClient::process_message(const StratumMessage& msg) {
    if (msg.is_response) {
        // Handle response (subscribe/authorize result)
        if (!msg.error.is_null()) {
            std::cerr << "[Stratum] Error response: " << msg.error.dump() << std::endl;
        } else if (msg.result.is_array() && msg.result.size() >= 2) {
            // mining.subscribe response
            session_id_ = msg.result[0][0].get<std::string>();
            extranonce1_ = msg.result[1].get<std::string>();
            extranonce2_size_ = msg.result[2].get<uint32_t>();
            std::cout << "[Stratum] Subscribed - Session: " << session_id_ << std::endl;
        }
    } else {
        // Handle notification
        switch (msg.method) {
            case StratumMethod::MINING_NOTIFY:
                handle_mining_notify(msg.params);
                break;
            case StratumMethod::MINING_SET_DIFFICULTY:
                handle_set_difficulty(msg.params);
                break;
            case StratumMethod::CLIENT_RECONNECT:
                handle_client_reconnect(msg.params);
                break;
            default:
                break;
        }
    }
}

void StratumClient::handle_mining_notify(const json& params) {
    std::lock_guard<std::mutex> lock(job_mutex_);

    current_job_.job_id = params[0].get<std::string>();
    current_job_.prev_hash = params[1].get<std::string>();
    current_job_.coinb1 = params[2].get<std::string>();
    current_job_.coinb2 = params[3].get<std::string>();

    current_job_.merkle_branches.clear();
    for (const auto& branch : params[4]) {
        current_job_.merkle_branches.push_back(branch.get<std::string>());
    }

    current_job_.version = params[5].get<std::string>();
    current_job_.nbits = params[6].get<std::string>();
    current_job_.ntime = params[7].get<std::string>();
    current_job_.clean_jobs = params[8].get<bool>();

    if (callbacks_.on_new_job) {
        callbacks_.on_new_job(current_job_);
    }
}

void StratumClient::handle_set_difficulty(const json& params) {
    double new_diff = params[0].get<double>();
    current_difficulty_.store(new_diff);

    if (callbacks_.on_difficulty_changed) {
        callbacks_.on_difficulty_changed(new_diff);
    }
}

void StratumClient::handle_client_reconnect(const json& params) {
    std::string new_host = params[0].get<std::string>();
    uint16_t new_port = params[1].get<uint16_t>();
    uint32_t wait_time = params[2].get<uint32_t>();

    std::cout << "[Stratum] Server requested reconnect to "
              << new_host << ":" << new_port
              << " in " << wait_time << "s" << std::endl;

    if (callbacks_.on_reconnect) {
        callbacks_.on_reconnect();
    }
}

void StratumClient::add_timing_jitter() {
    static std::random_device rd;
    static std::mt19937 gen(rd());
    std::uniform_int_distribution<> dist(config_.jitter_ms_min, config_.jitter_ms_max);

    uint32_t jitter_ms = dist(gen);
    std::this_thread::sleep_for(std::chrono::milliseconds(jitter_ms));
}

uint64_t StratumClient::next_message_id() {
    return message_id_counter_++;
}

} // namespace redteam
