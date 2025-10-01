// tls_wrapper.cpp - OpenSSL TLS Connection Wrapper
// RED TEAM RESEARCH - Encrypted pool communication analysis

#include "pool_client.h"
#include <openssl/ssl.h>
#include <openssl/err.h>
#include <openssl/x509v3.h>
#include <cstring>
#include <iostream>

namespace redteam {

// ============================================================================
// TLSWrapper::Impl - PIMPL idiom for OpenSSL internals
// ============================================================================
struct TLSWrapper::Impl {
    SSL_CTX* ctx = nullptr;
    SSL* ssl = nullptr;
    bool connected = false;

    Impl() {
        // Initialize OpenSSL
        SSL_load_error_strings();
        SSL_library_init();
        OpenSSL_add_all_algorithms();

        // Create SSL context (TLS 1.2+)
        ctx = SSL_CTX_new(TLS_client_method());
        if (!ctx) {
            ERR_print_errors_fp(stderr);
            throw std::runtime_error("Failed to create SSL context");
        }

        // Set minimum protocol version to TLS 1.2
        SSL_CTX_set_min_proto_version(ctx, TLS1_2_VERSION);

        // Load system CA certificates
        if (SSL_CTX_set_default_verify_paths(ctx) != 1) {
            std::cerr << "[TLS] Warning: Could not load system CA certificates" << std::endl;
        }

        // Set verification mode (allow self-signed for research)
        SSL_CTX_set_verify(ctx, SSL_VERIFY_NONE, nullptr);

        // Prefer strong cipher suites
        SSL_CTX_set_cipher_list(ctx,
            "ECDHE-ECDSA-AES256-GCM-SHA384:"
            "ECDHE-RSA-AES256-GCM-SHA384:"
            "ECDHE-ECDSA-CHACHA20-POLY1305:"
            "ECDHE-RSA-CHACHA20-POLY1305:"
            "ECDHE-ECDSA-AES128-GCM-SHA256:"
            "ECDHE-RSA-AES128-GCM-SHA256"
        );
    }

    ~Impl() {
        disconnect();
        if (ctx) {
            SSL_CTX_free(ctx);
            ctx = nullptr;
        }
    }

    void disconnect() {
        if (ssl) {
            SSL_shutdown(ssl);
            SSL_free(ssl);
            ssl = nullptr;
        }
        connected = false;
    }
};

// ============================================================================
// TLSWrapper Implementation
// ============================================================================

TLSWrapper::TLSWrapper()
    : pimpl_(std::make_unique<Impl>())
{
}

TLSWrapper::~TLSWrapper() {
    disconnect();
}

bool TLSWrapper::connect(const std::string& hostname, uint16_t port, int socket_fd) {
    if (pimpl_->connected) {
        return true;
    }

    // Create SSL object
    pimpl_->ssl = SSL_new(pimpl_->ctx);
    if (!pimpl_->ssl) {
        ERR_print_errors_fp(stderr);
        return false;
    }

    // Attach socket
    if (SSL_set_fd(pimpl_->ssl, socket_fd) != 1) {
        ERR_print_errors_fp(stderr);
        SSL_free(pimpl_->ssl);
        pimpl_->ssl = nullptr;
        return false;
    }

    // Set SNI (Server Name Indication)
    SSL_set_tlsext_host_name(pimpl_->ssl, hostname.c_str());

    // Perform TLS handshake
    int ret = SSL_connect(pimpl_->ssl);
    if (ret != 1) {
        int err = SSL_get_error(pimpl_->ssl, ret);
        std::cerr << "[TLS] Handshake failed with error code: " << err << std::endl;
        ERR_print_errors_fp(stderr);

        SSL_free(pimpl_->ssl);
        pimpl_->ssl = nullptr;
        return false;
    }

    // Verify certificate (optional for research - log only)
    X509* cert = SSL_get_peer_certificate(pimpl_->ssl);
    if (cert) {
        long verify_result = SSL_get_verify_result(pimpl_->ssl);
        if (verify_result != X509_V_OK) {
            std::cerr << "[TLS] Certificate verification failed: "
                      << X509_verify_cert_error_string(verify_result)
                      << " (continuing anyway for research)" << std::endl;
        }

        // Log certificate info
        char* subject = X509_NAME_oneline(X509_get_subject_name(cert), nullptr, 0);
        char* issuer = X509_NAME_oneline(X509_get_issuer_name(cert), nullptr, 0);

        std::cout << "[TLS] Certificate subject: " << subject << std::endl;
        std::cout << "[TLS] Certificate issuer: " << issuer << std::endl;

        OPENSSL_free(subject);
        OPENSSL_free(issuer);
        X509_free(cert);
    } else {
        std::cerr << "[TLS] Warning: No peer certificate" << std::endl;
    }

    pimpl_->connected = true;
    return true;
}

void TLSWrapper::disconnect() {
    if (pimpl_) {
        pimpl_->disconnect();
    }
}

ssize_t TLSWrapper::send(const void* data, size_t length) {
    if (!pimpl_->connected || !pimpl_->ssl) {
        return -1;
    }

    int sent = SSL_write(pimpl_->ssl, data, static_cast<int>(length));
    if (sent <= 0) {
        int err = SSL_get_error(pimpl_->ssl, sent);
        if (err != SSL_ERROR_WANT_WRITE && err != SSL_ERROR_WANT_READ) {
            std::cerr << "[TLS] Send error: " << err << std::endl;
            ERR_print_errors_fp(stderr);
            pimpl_->connected = false;
        }
        return -1;
    }

    return sent;
}

ssize_t TLSWrapper::receive(void* buffer, size_t length) {
    if (!pimpl_->connected || !pimpl_->ssl) {
        return -1;
    }

    int received = SSL_read(pimpl_->ssl, buffer, static_cast<int>(length));
    if (received <= 0) {
        int err = SSL_get_error(pimpl_->ssl, received);
        if (err != SSL_ERROR_WANT_READ && err != SSL_ERROR_WANT_WRITE) {
            if (err != SSL_ERROR_ZERO_RETURN) { // Clean shutdown
                std::cerr << "[TLS] Receive error: " << err << std::endl;
                ERR_print_errors_fp(stderr);
            }
            pimpl_->connected = false;
        }
        return -1;
    }

    return received;
}

bool TLSWrapper::is_connected() const {
    return pimpl_ && pimpl_->connected;
}

std::string TLSWrapper::get_cipher_name() const {
    if (!pimpl_->ssl) {
        return "N/A";
    }

    const char* cipher = SSL_get_cipher_name(pimpl_->ssl);
    return cipher ? cipher : "Unknown";
}

std::string TLSWrapper::get_protocol_version() const {
    if (!pimpl_->ssl) {
        return "N/A";
    }

    const char* version = SSL_get_version(pimpl_->ssl);
    return version ? version : "Unknown";
}

} // namespace redteam
