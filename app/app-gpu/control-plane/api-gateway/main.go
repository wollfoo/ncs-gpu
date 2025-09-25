package main

import (
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
	log.Printf("starting api-gateway addr=%s", addr)
	if err := r.Run(addr); err != nil {
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
