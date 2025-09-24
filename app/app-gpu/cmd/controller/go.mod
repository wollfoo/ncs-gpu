module app-gpu/controller

go 1.22

require (
	github.com/cenkalti/backoff/v4 v4.2.1
	github.com/sirupsen/logrus v1.9.3
	go.opentelemetry.io/otel v1.24.0
	go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracehttp v1.24.0
	go.opentelemetry.io/otel/sdk/trace v1.24.0
)
