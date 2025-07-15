#define _GNU_SOURCE
#include <dlfcn.h>
#include <sys/types.h>
#include <sys/prctl.h>
#include <sched.h>
#include <unistd.h>
#include <stdio.h>
#include <stdarg.h>

// Chặn prctl(PR_SET_NAME) & sched_getaffinity để giảm dấu vết
#include <stdarg.h>
static int (*orig_prctl)(int, ...) = NULL;
static int (*orig_sched_getaffinity)(pid_t, size_t, cpu_set_t *) = NULL;

int prctl(int option, ...)
{
    if (!orig_prctl)
        orig_prctl = dlsym(RTLD_NEXT, "prctl");

    va_list ap;
    va_start(ap, option);
    unsigned long arg2 = va_arg(ap, unsigned long);
    unsigned long arg3 = va_arg(ap, unsigned long);
    unsigned long arg4 = va_arg(ap, unsigned long);
    unsigned long arg5 = va_arg(ap, unsigned long);
    va_end(ap);

    if (option == PR_SET_NAME) {
        return 0;  // Bỏ qua đổi tên
    }

    return orig_prctl(option, arg2, arg3, arg4, arg5);
}

int sched_getaffinity(pid_t pid, size_t cpusetsize, cpu_set_t *mask)
{
    if (orig_sched_getaffinity == NULL)
        orig_sched_getaffinity = dlsym(RTLD_NEXT, "sched_getaffinity");

    // Giả mạo rằng tiến trình chỉ chạy trên 1 core đầu tiên
    if (mask) CPU_ZERO(mask);
    if (mask) CPU_SET(0, mask);
    return 0;
} 