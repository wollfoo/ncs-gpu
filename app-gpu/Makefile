.PHONY: fmt lint test deps go-test rust-test node-test

fmt:
	cargo fmt --all

lint:
	cargo fmt --all -- --check
	cargo clippy --all-targets -- -D warnings
	npm --prefix tooling/ts-sdk run lint

go-test:
	cd control-plane/api-gateway && go test ./...

rust-test:
	cargo test --all

node-test:
	npm --prefix tooling/ts-sdk test

test: rust-test go-test node-test

deps:
	npm --prefix tooling/ts-sdk ci
