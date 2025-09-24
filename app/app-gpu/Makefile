SHELL := /bin/bash

CARGO := cargo
GO := go
DOCKER := docker

.PHONY: all build lint test bench fmt fmt-go fmt-rs audit sbom up down

all: build

build: fmt lint
	$(CARGO) build --workspace --release
	cd cmd/controller && $(GO) build ./...

fmt:	fmt-rs fmt-go

fmt-rs:
	rustfmt --edition 2021 $(shell find . -name '*.rs')

fmt-go:
	cd cmd/controller && $(GO) fmt ./...

lint:
	$(CARGO) clippy --workspace --all-targets -- -D warnings
	cd cmd/controller && golangci-lint run ./...

unit-test:
	$(CARGO) test --workspace --lib
	cd cmd/controller && $(GO) test ./...

integration-test:
	docker compose -f docker-compose.yml -f tests/integration/docker-compose.override.yml up --build --abort-on-container-exit
	docker compose down -v

bench:
	$(CARGO) bench --package tests-rust

sbom:
	syft packages . -o spdx-json > security/sbom.json
	syft attest . -o json > security/sbom.att.json

audit:
	$(CARGO) audit
	cd cmd/controller && gosec ./...

up:
	docker compose up -d

down:
	docker compose down -v
