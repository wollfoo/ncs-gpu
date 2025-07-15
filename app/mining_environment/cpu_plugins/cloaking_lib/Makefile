CC=gcc
CFLAGS=-fPIC -O2 -Wall -shared
TARGET=libcloak.so
SRCS=cloak.c

all: $(TARGET)

$(TARGET): $(SRCS)
	$(CC) $(CFLAGS) $^ -o $@ -ldl

clean:
	rm -f $(TARGET)

install:
	install -D $(TARGET) /usr/local/lib/$(TARGET)
	ldconfig

.PHONY: all clean install