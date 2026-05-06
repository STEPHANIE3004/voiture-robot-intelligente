CC     = gcc
CFLAGS = -Wall -Wextra -std=c11 -Iinclude -lm
TARGET = robot_sim
SRCS   = src/main.c src/robot.c

all: $(TARGET)
$(TARGET): $(SRCS)
	$(CC) $(CFLAGS) -o $@ $^
clean:
	rm -f $(TARGET)
run: all
	./$(TARGET)
.PHONY: all clean run
