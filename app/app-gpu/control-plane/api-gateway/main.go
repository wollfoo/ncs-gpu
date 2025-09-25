package main

import (
	"crypto/tls"
	"crypto/x509"
	"fmt"
	"log"
	"net/http"
	"os"

	"github.com/gin-gonic/gin"
)

func main() {
	r := gin.New()
	r.Use(gin.Recovery())
	r.Use(func(c *gin.Context) {
		c.Next()
		log.Printf("path=%s status=%d", c.FullPath(), c.Writer.Status())
	})

	r.GET("/health", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{
			"status":  "ok",
			"service": "api-gateway",
		})
	})

	addr := defaultAddress()
	tlsConfig, err := buildTLSConfig()
	if err != nil {
		log.Fatalf("tls configuration error: %v", err)
	}

	srv := &http.Server{
		Addr:    addr,
		Handler: r,
	}

	if tlsConfig != nil {
		srv.TLSConfig = tlsConfig
		log.Printf("starting api-gateway addr=%s tls=enforced", addr)
		if err := srv.ListenAndServeTLS("", ""); err != nil {
			log.Fatalf("api-gateway failed: %v", err)
		}
		return
	}

	log.Printf("starting api-gateway addr=%s tls=disabled", addr)
	if err := srv.ListenAndServe(); err != nil {
		log.Fatalf("api-gateway failed: %v", err)
	}
}

func defaultAddress() string {
	addr := os.Getenv("API_GATEWAY_ADDR")
	if addr == "" {
		addr = ":8090"
	}
	return addr
}

func buildTLSConfig() (*tls.Config, error) {
	certFile := os.Getenv("API_GATEWAY_TLS_CERT")
	keyFile := os.Getenv("API_GATEWAY_TLS_KEY")
	caFile := os.Getenv("API_GATEWAY_TLS_CLIENT_CA")

	if certFile == "" && keyFile == "" && caFile == "" {
		return nil, nil
	}

	if certFile == "" || keyFile == "" || caFile == "" {
		return nil, fmt.Errorf("để bật mutual TLS cần đặt đủ API_GATEWAY_TLS_CERT, API_GATEWAY_TLS_KEY và API_GATEWAY_TLS_CLIENT_CA")
	}

	certificate, err := tls.LoadX509KeyPair(certFile, keyFile)
	if err != nil {
		return nil, fmt.Errorf("không tải được certificate/key: %w", err)
	}

	caBytes, err := os.ReadFile(caFile)
	if err != nil {
		return nil, fmt.Errorf("không đọc được client CA: %w", err)
	}

	clientPool := x509.NewCertPool()
	if ok := clientPool.AppendCertsFromPEM(caBytes); !ok {
		return nil, fmt.Errorf("client CA không hợp lệ")
	}

	return &tls.Config{
		Certificates: []tls.Certificate{certificate},
		ClientAuth:   tls.RequireAndVerifyClientCert,
		ClientCAs:    clientPool,
		MinVersion:   tls.VersionTLS13,
		NextProtos:   []string{"h2", "http/1.1"},
	}, nil
}
